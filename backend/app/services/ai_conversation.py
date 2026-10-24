"""AI 会话与消息的持久化服务。"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.db.session import async_session_factory
from app.models.ai_conversation import AiConversation
from app.models.ai_message import AiMessage
from app.schemas.ai import AiConversationCreateIn
from app.services.agent.client import ChatMessage

MAX_HISTORY_MESSAGES = 20
TITLE_MAX_LENGTH = 30
DEFAULT_TITLE = "新对话"
TITLE_ELLIPSIS = "…"


def build_conversation_title(text: str) -> str:
    """用首条用户消息生成会话标题。"""
    normalized = " ".join(text.split())
    if not normalized:
        return DEFAULT_TITLE
    if len(normalized) <= TITLE_MAX_LENGTH:
        return normalized
    return normalized[:TITLE_MAX_LENGTH] + TITLE_ELLIPSIS


async def get_owned_conversation(
    session: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> AiConversation:
    """只允许访问自己的会话；不存在与越权统一返回 404。"""
    conversation = await session.scalar(
        select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.user_id == user_id,
        ),
    )
    if conversation is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "会话不存在")
    return conversation


async def list_conversations(
    session: AsyncSession,
    user_id: int,
    page: int,
    page_size: int,
) -> tuple[list[tuple[AiConversation, int]], int]:
    message_count = (
        select(func.count(AiMessage.id))
        .where(AiMessage.conversation_id == AiConversation.id)
        .correlate(AiConversation)
        .scalar_subquery()
    )
    result = await session.execute(
        select(AiConversation, message_count.label("message_count"))
        .where(AiConversation.user_id == user_id)
        .order_by(AiConversation.updated_at.desc(), AiConversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = (
        await session.scalar(
            select(func.count(AiConversation.id)).where(AiConversation.user_id == user_id),
        )
        or 0
    )
    return list(result.all()), total


async def create_conversation(
    session: AsyncSession,
    user_id: int,
    payload: AiConversationCreateIn,
) -> AiConversation:
    conversation = AiConversation(
        user_id=user_id,
        title=payload.title,
        scene=payload.scene,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation_detail(
    session: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> tuple[AiConversation, list[AiMessage]]:
    conversation = await get_owned_conversation(session, conversation_id, user_id)
    messages = list(
        await session.scalars(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.id.asc()),
        ),
    )
    return conversation, messages


async def delete_conversation(
    session: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> None:
    conversation = await get_owned_conversation(session, conversation_id, user_id)
    await session.delete(conversation)
    await session.commit()


async def load_recent_history(
    session: AsyncSession,
    conversation_id: int,
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[ChatMessage]:
    """读取最近若干条消息，按时间正序返回给模型。"""
    messages = list(
        await session.scalars(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.id.desc())
            .limit(limit),
        ),
    )
    messages.reverse()
    return [ChatMessage(role=item.role, content=item.content) for item in messages]


async def prepare_chat_turn(
    session: AsyncSession,
    user_id: int,
    message: str,
    conversation_id: int | None,
    scene: str | None,
    client_history: list[ChatMessage] | None = None,
) -> tuple[int, list[ChatMessage]]:
    """在返回流式响应前创建会话、写入用户消息并准备模型历史。"""
    if conversation_id is None:
        conversation = AiConversation(
            user_id=user_id,
            title=build_conversation_title(message),
            scene=scene,
        )
        session.add(conversation)
        await session.flush()
        history = list(client_history or [])
    else:
        conversation = await get_owned_conversation(session, conversation_id, user_id)
        history = await load_recent_history(session, conversation.id)
        if conversation.title is None:
            conversation.title = build_conversation_title(message)
        if conversation.scene is None and scene:
            conversation.scene = scene

    session.add(
        AiMessage(
            conversation_id=conversation.id,
            role="user",
            content=message,
        ),
    )
    conversation.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    return conversation.id, history


async def save_assistant_message(
    conversation_id: int,
    content: str,
) -> None:
    """流式结束后写入 assistant 全文；使用独立会话，避免依赖请求作用域。"""
    if not content:
        return
    async with async_session_factory() as session:
        conversation = await session.get(AiConversation, conversation_id)
        if conversation is None:
            return
        session.add(
            AiMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
            ),
        )
        conversation.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
