from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exception_handlers import (
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_UNAVAILABLE,
    AppError,
)
from app.db.session import get_session
from app.models.user import User
from app.models.word import Word
from app.schemas.audio import AudioOut
from app.schemas.common import ApiResponse
from app.services.audio import get_word_audio
from app.services.tts import TtsUnavailableError, synthesize_word_audio

router = APIRouter(tags=["audio"], dependencies=[Depends(get_current_user)])


@router.get("/words/{word_id}/audio", response_model=ApiResponse[AudioOut])
async def get_word_audio_endpoint(
    word_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[AudioOut]:
    """返回单词音频地址或浏览器 TTS 兜底标记。"""
    audio_url, fallback, tts_text = await get_word_audio(session, word_id)
    return ApiResponse[AudioOut](
        code=0,
        message="ok",
        data=AudioOut(audio_url=audio_url, tts_text=tts_text, fallback=fallback),
    )


@router.get("/words/{word_id}/audio/file")
async def get_word_audio_file_endpoint(
    word_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    accent: Literal["us", "uk"] = "us",
) -> FileResponse:
    """用系统语音合成单词读音，返回 WAV 文件。"""
    word = await session.get(Word, word_id)
    if word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "单词不存在")

    try:
        path = await synthesize_word_audio(word.spelling, accent)
    except TtsUnavailableError as exc:
        raise AppError(503, ERROR_CODE_UNAVAILABLE, "系统语音不可用") from exc

    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Cache-Control": "private, max-age=86400"},
    )
