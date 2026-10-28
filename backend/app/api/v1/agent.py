import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langsmith import tracing_context
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.agent import AgentChatIn
from app.services.agent.client import ChatMessage
from app.services.agent.service import AgentService, format_sse, get_agent_service
from app.services.ai_conversation import prepare_chat_turn, save_assistant_message

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(get_current_user)],
)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _stream_chat(
    service: AgentService,
    payload: AgentChatIn,
    history: list[ChatMessage],
    conversation_id: int,
    user_id: int,
) -> AsyncIterator[str]:
    """转发 Agent 事件并按需累计回复文本。"""
    chunks: list[str] = []
    metadata = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "scene": payload.scene or "",
    }
    try:
        with tracing_context(metadata=metadata):
            async for event, data in service.stream_events(
                payload.message,
                scene=payload.scene,
                history=history,
            ):
                if event == "meta":
                    data = {**data, "conversation_id": conversation_id}
                elif event == "delta":
                    chunks.append(data.get("content", ""))
                yield format_sse(event, data)
    except Exception:
        logger.exception("Agent 对话生成失败")
        yield format_sse("error", {"message": "对话生成失败，请稍后再试"})
    finally:
        content = "".join(chunks)
        if content:
            await _persist_reply(conversation_id, content)


async def _persist_reply(conversation_id: int, content: str) -> None:
    """请求作用域可能已关闭，保存回复使用独立数据库会话。"""
    try:
        task = asyncio.create_task(save_assistant_message(conversation_id, content))
        await asyncio.shield(task)
    except Exception:
        logger.exception("保存 AI 回复失败")


@router.post("/chat")
async def agent_chat(
    payload: AgentChatIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """智能伴学对话：Router 识别意图 -> Skill 分发 -> SSE 流式返回。"""
    service = get_agent_service()
    client_history = [ChatMessage(role=item.role, content=item.content) for item in payload.history]
    conversation_id, history = await prepare_chat_turn(
        session,
        user_id=current_user.id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        scene=payload.scene,
        client_history=client_history,
    )
    stream = _stream_chat(
        service,
        payload,
        history,
        conversation_id,
        current_user.id,
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)
