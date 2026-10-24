from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.ai import (
    AiConversationCreateIn,
    AiConversationDeleteOut,
    AiConversationDetailOut,
    AiConversationListItem,
    AiConversationListOut,
    AiConversationOut,
    AiMessageOut,
)
from app.schemas.common import ApiResponse
from app.services.ai_conversation import (
    create_conversation,
    delete_conversation,
    get_conversation_detail,
    list_conversations,
)

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/sessions", response_model=ApiResponse[AiConversationListOut])
async def list_sessions_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[AiConversationListOut]:
    """分页返回当前用户的对话会话。"""
    rows, total = await list_conversations(session, current_user.id, page, page_size)
    items = [
        AiConversationListItem(
            id=conversation.id,
            title=conversation.title,
            scene=conversation.scene,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=message_count,
        )
        for conversation, message_count in rows
    ]
    return ApiResponse[AiConversationListOut](
        code=0,
        message="ok",
        data=AiConversationListOut(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.post(
    "/sessions",
    response_model=ApiResponse[AiConversationOut],
    status_code=201,
)
async def create_session_endpoint(
    payload: AiConversationCreateIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AiConversationOut]:
    """新建一个空会话；标题可由首条消息自动生成。"""
    conversation = await create_conversation(session, current_user.id, payload)
    return ApiResponse[AiConversationOut](
        code=0,
        message="ok",
        data=AiConversationOut.model_validate(conversation),
    )


@router.get(
    "/sessions/{conversation_id}",
    response_model=ApiResponse[AiConversationDetailOut],
)
async def get_session_endpoint(
    conversation_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AiConversationDetailOut]:
    """返回会话详情与按时间正序排列的消息。"""
    conversation, messages = await get_conversation_detail(
        session,
        conversation_id,
        current_user.id,
    )
    return ApiResponse[AiConversationDetailOut](
        code=0,
        message="ok",
        data=AiConversationDetailOut(
            id=conversation.id,
            title=conversation.title,
            scene=conversation.scene,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[AiMessageOut.model_validate(item) for item in messages],
        ),
    )


@router.delete(
    "/sessions/{conversation_id}",
    response_model=ApiResponse[AiConversationDeleteOut],
)
async def delete_session_endpoint(
    conversation_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AiConversationDeleteOut]:
    """删除当前用户的会话，消息随外键级联删除。"""
    await delete_conversation(session, conversation_id, current_user.id)
    return ApiResponse[AiConversationDeleteOut](
        code=0,
        message="ok",
        data=AiConversationDeleteOut(deleted=True),
    )
