from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.audio import AudioOut
from app.schemas.common import ApiResponse
from app.services.audio import get_word_audio

router = APIRouter(tags=["audio"], dependencies=[Depends(get_current_user)])


@router.get("/words/{word_id}/audio", response_model=ApiResponse[AudioOut])
async def get_word_audio_endpoint(
    word_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[AudioOut]:
    """返回单词音频地址或浏览器 TTS 兜底标记。"""
    audio_url, fallback = await get_word_audio(session, word_id)
    return ApiResponse[AudioOut](
        code=0,
        message="ok",
        data=AudioOut(audio_url=audio_url, fallback=fallback),
    )
