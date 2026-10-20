"""AI 伴学对话路由：LangGraph Agent、标准 RAG 降级、SSE 流式输出与历史持久化。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.agent import AgentToolUnsupported, stream_agent
from app.ai.client import AIError, stream_chat
from app.ai.corrections import feedback_from_json, feedback_to_json, parse_feedback
from app.ai.prompts import build_messages
from app.api.deps import get_current_user
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models.chat import ChatMessage
from app.models.user import User
from app.rag import pipeline as rag_pipeline
from app.rag.types import RagResult
from app.schemas.chat import AgentMetadata, ChatSendRequest, MessageOut

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/chat", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # 防止反向代理缓冲导致前端收不到逐字内容
    "X-Accel-Buffering": "no",
}

MAX_HISTORY = 20


def _sse(payload: dict) -> str:
    """构造一行 Server-Sent Events 数据帧。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _metadata_from_json(raw: str | None) -> AgentMetadata | None:
    """安全还原 metadata；旧记录、空值或损坏 JSON 均返回 None。"""

    if not raw:
        return None
    try:
        return AgentMetadata.model_validate_json(raw)
    except Exception:  # noqa: BLE001 - 历史脏数据不能让列表接口 500
        logger.warning("忽略无法解析的 chat_messages.metadata")
        return None


def _retrieve(content: str, history: list[dict]) -> RagResult | None:
    """跑一次标准 RAG 检索，永不抛出。

    返回 None 表示 RAG 整体关闭，此时不发送 status 帧。
    """
    if not settings.rag_enabled:
        return None
    try:
        with SessionLocal() as db:
            return rag_pipeline.run(content, db, history=history)
    except Exception:  # noqa: BLE001 - 检索失败绝不能阻断对话
        logger.exception("RAG 检索异常，降级为无上下文")
        return RagResult(skipped="检索异常")


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    """拉取当前用户最近的对话历史。"""
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY)
    ).all()
    out: list[MessageOut] = []
    for row in reversed(list(rows)):
        out.append(
            MessageOut(
                id=row.id,
                role=row.role,
                content=row.content,
                feedback=feedback_from_json(row.feedback),
                metadata=_metadata_from_json(row.agent_metadata),
                created_at=row.created_at,
            )
        )
    return out


@router.delete("/messages")
def clear_messages(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """清空当前用户的对话历史。"""
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
    db.commit()
    return {"cleared": True}


async def _run_legacy(
    *,
    content: str,
    history: list[dict[str, str]],
    preset: str | None,
    context: str | None,
    fallback: str | None = None,
) -> AsyncIterator[dict]:
    """现有的一次 RAG 检索 + 标准流式回答路径，也是 Agent 的安全降级。"""

    rag_result = _retrieve(content, history) or RagResult(skipped=None)
    if rag_result.skipped:
        yield {
            "type": "status",
            "phase": "skipped",
            "reason": rag_result.skipped,
        }
    elif rag_result.hits:
        yield {"type": "status", "phase": "retrieving"}
        yield {
            "type": "status",
            "phase": "retrieved",
            "hits": len(rag_result.hits),
            "sources": rag_result.sources,
        }

    messages = build_messages(
        history=history,
        user_input=content,
        preset=preset,
        context=context,
        rag_context=rag_result.context or None,
    )
    buffer: list[str] = []
    async for delta in stream_chat(messages, user_input=content, preset=preset):
        buffer.append(delta)
        yield {"type": "delta", "delta": delta}

    yield {
        "type": "result",
        "content": "".join(buffer),
        "metadata": {
            "mode": "chat",
            "rounds": 0,
            "tools": [],
            "sources": rag_result.sources,
            "fallback": fallback,
            "elapsed_ms": 0,
        },
    }


async def _run_agent(
    *,
    content: str,
    history: list[dict[str, str]],
    preset: str | None,
    context: str | None,
) -> AsyncIterator[dict]:
    """消费 LangGraph 自定义流；result 帧由路由层拦截，不下发给前端。"""

    async for event in stream_agent(
        history=history,
        user_input=content,
        preset=preset,
        context=context,
    ):
        yield event


@router.post("/send")
async def send(
    payload: ChatSendRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """发送消息并以 SSE 返回 Agent 状态、逐字回答与最终元数据。"""

    user_id = user.id
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息内容不能为空")

    async def event_stream() -> AsyncIterator[str]:
        with SessionLocal() as db:
            user_row = ChatMessage(user_id=user_id, role="user", content=content)
            db.add(user_row)
            history_rows = db.scalars(
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id)
                .order_by(ChatMessage.id.desc())
                .limit(MAX_HISTORY)
            ).all()
            db.commit()
            db.refresh(user_row)
            current_id = user_row.id
            history = [
                {"role": row.role, "content": row.content}
                for row in reversed(list(history_rows))
                if row.id != current_id and row.role in ("user", "assistant")
            ]

        yield _sse({"type": "start"})
        started = time.perf_counter()
        result: dict | None = None

        try:
            if settings.agent_enabled and settings.ai_enabled:
                try:
                    async for event in _run_agent(
                        content=content,
                        history=history,
                        preset=payload.preset,
                        context=payload.context,
                    ):
                        if event.get("type") == "result":
                            result = event
                        else:
                            yield _sse(event)
                except AgentToolUnsupported as exc:
                    yield _sse(
                        {
                            "type": "agent",
                            "phase": "fallback",
                            "reason": str(exc),
                        }
                    )
                    async for event in _run_legacy(
                        content=content,
                        history=history,
                        preset=payload.preset,
                        context=payload.context,
                        fallback=str(exc),
                    ):
                        if event.get("type") == "result":
                            result = event
                        else:
                            yield _sse(event)
            else:
                async for event in _run_legacy(
                    content=content,
                    history=history,
                    preset=payload.preset,
                    context=payload.context,
                ):
                    if event.get("type") == "result":
                        result = event
                    else:
                        yield _sse(event)
        except AIError as exc:
            yield _sse(
                {
                    "type": "error",
                    "message": exc.message,
                    "retryable": exc.retryable,
                }
            )
            return
        except Exception:  # noqa: BLE001 - 未预期错误也不能让 SSE 静默断开
            logger.exception("聊天生成异常")
            yield _sse(
                {
                    "type": "error",
                    "message": "回答生成失败，请稍后重试",
                    "retryable": True,
                }
            )
            return

        if result is None:
            yield _sse(
                {
                    "type": "error",
                    "message": "模型未生成回答，请稍后重试",
                    "retryable": True,
                }
            )
            return

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        metadata = AgentMetadata.model_validate(result.get("metadata") or {})
        metadata.elapsed_ms = elapsed_ms

        full_text = str(result.get("content") or "")
        body, block = parse_feedback(full_text)
        with SessionLocal() as db:
            record = ChatMessage(
                user_id=user_id,
                role="assistant",
                content=body or full_text,
                feedback=feedback_to_json(block),
                agent_metadata=metadata.model_dump_json(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            message_id = record.id
            created_at = record.created_at.isoformat()

        yield _sse(
            {
                "type": "done",
                "message_id": message_id,
                "content": body or full_text,
                "feedback": block.model_dump() if block else None,
                "sources": [source.model_dump() for source in metadata.sources],
                "metadata": metadata.model_dump(),
                "created_at": created_at,
            }
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
