from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.exception_handlers import ERROR_CODE_NOT_IMPLEMENTED, AppError
from app.schemas.ai import AiPlaceholderOut
from app.schemas.common import ApiResponse

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user)],
)


async def _raise_not_implemented() -> ApiResponse[AiPlaceholderOut]:
    raise AppError(501, ERROR_CODE_NOT_IMPLEMENTED, "not implemented")


@router.post("/chat", response_model=ApiResponse[AiPlaceholderOut])
async def ai_chat_placeholder() -> ApiResponse[AiPlaceholderOut]:
    return await _raise_not_implemented()


@router.get("/sessions", response_model=ApiResponse[AiPlaceholderOut])
async def ai_sessions_placeholder() -> ApiResponse[AiPlaceholderOut]:
    return await _raise_not_implemented()


@router.post("/sessions", response_model=ApiResponse[AiPlaceholderOut])
async def ai_create_session_placeholder() -> ApiResponse[AiPlaceholderOut]:
    return await _raise_not_implemented()
