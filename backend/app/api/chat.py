"""AI 伴学对话路由：SSE 流式输出、历史读取与清空。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.client import AIError, stream_chat
from app.ai.corrections import feedback_from_json, feedback_to_json, parse_feedback
from app.ai.prompts import build_messages
from app.api.deps import get_current_user
from core.db import SessionLocal, get_db
from core.models.chat import ChatMessage
from core.models.user import User
from app.schemas.chat import ChatSendRequest, MessageOut

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


@router.get("/messages", response_model=list[MessageOut])
def list_messages(user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> list[MessageOut]:
    """拉取当前用户最近的对话历史。"""
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY)
    ).all()
    out: list[MessageOut] = []
    for row in reversed(list(rows)):
        # feedback 列入库的是 JSON 字符串，直接 model_validate 会被强转成
        # FeedbackBlock 并抛 ValidationError，导致只要历史里出现过一条带纠错
        # 区块的回复，整个历史接口就 500；必须显式还原
        out.append(
            MessageOut(
                id=row.id,
                role=row.role,
                content=row.content,
                feedback=feedback_from_json(row.feedback),
                created_at=row.created_at,
            )
        )
    return out


@router.delete("/messages")
def clear_messages(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    """清空当前用户的对话历史。"""
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
    db.commit()
    return {"cleared": True}


@router.post("/send")
async def send(payload: ChatSendRequest, user: User = Depends(get_current_user)) -> StreamingResponse:
    """发送消息并以 SSE 逐字流式返回 AI 回复。"""
    user_id = user.id
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息内容不能为空")

    async def event_stream() -> AsyncIterator[str]:
        # 会话内先落库用户消息，保证刷新后仍能看到自己的发言
        with SessionLocal() as db:
            db.add(ChatMessage(user_id=user_id, role="user", content=content))
            history_rows = db.scalars(
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id)
                .order_by(ChatMessage.id.desc())
                .limit(MAX_HISTORY - 1)
            ).all()
            history = [
                {"role": row.role, "content": row.content}
                for row in reversed(list(history_rows))
                if row.role in ("user", "assistant")
            ]
            db.commit()

        yield _sse({"type": "start"})

        messages = build_messages(
            history=history,
            user_input=content,
            preset=payload.preset,
            context=payload.context,
        )

        buffer: list[str] = []
        try:
            async for delta in stream_chat(messages, user_input=content, preset=payload.preset):
                buffer.append(delta)
                yield _sse({"type": "delta", "delta": delta})
        except AIError as exc:
            # 断网 / 超时：推送给前端以便展示优雅提示并支持一键重试
            yield _sse({"type": "error", "message": exc.message, "retryable": exc.retryable})
            return

        full_text = "".join(buffer)
        body, block = parse_feedback(full_text)
        with SessionLocal() as db:
            record = ChatMessage(
                user_id=user_id,
                role="assistant",
                content=body or full_text,
                feedback=feedback_to_json(block),
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
                "created_at": created_at,
            }
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
