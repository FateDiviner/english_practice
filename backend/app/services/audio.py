from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.models.word import Word


async def get_word_audio(session: AsyncSession, word_id: int) -> tuple[str | None, str | None]:
    """返回词库音频地址；无音频时返回浏览器 TTS 兜底标记。"""
    word = await session.get(Word, word_id)
    if word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "单词不存在")

    if word.audio_url:
        return word.audio_url, None
    return None, "tts"
