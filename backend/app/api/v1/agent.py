from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import get_current_user
from app.schemas.agent import AgentChatIn
from app.services.agent.client import ChatMessage
from app.services.agent.service import get_agent_service

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(get_current_user)],
)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _to_chat_messages(payload: AgentChatIn) -> list[ChatMessage]:
    return [ChatMessage(role=item.role, content=item.content) for item in payload.history]


@router.post("/chat")
async def agent_chat(payload: AgentChatIn) -> StreamingResponse:
    """智能伴学对话：Router 识别意图 -> Skill 分发 -> SSE 流式返回。"""
    service = get_agent_service()
    stream = service.stream_chat(
        payload.message, scene=payload.scene, history=_to_chat_messages(payload)
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)
