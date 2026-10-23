from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.models.word import Word
from app.models.wrong_word import WrongWord


async def list_wrong_words(
    session: AsyncSession,
    user_id: int,
    page: int,
    page_size: int,
    resolved: bool = False,
) -> tuple[list[tuple[WrongWord, Word]], int]:
    """分页查询当前用户的错词，默认只看未解决记录。"""
    conditions = [
        WrongWord.user_id == user_id,
        WrongWord.resolved.is_(resolved),
    ]
    result = await session.execute(
        select(WrongWord, Word)
        .join(Word, WrongWord.word_id == Word.id)
        .where(*conditions)
        .order_by(WrongWord.last_wrong_at.desc(), WrongWord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = (
        await session.scalar(
            select(func.count(WrongWord.id)).where(*conditions),
        )
        or 0
    )
    return list(result.all()), total


async def remove_wrong_word(
    session: AsyncSession,
    user_id: int,
    word_id: int,
) -> None:
    """移除当前用户自己的错词记录，不能操作他人数据。"""
    wrong_word = await session.scalar(
        select(WrongWord).where(
            WrongWord.user_id == user_id,
            WrongWord.word_id == word_id,
        ),
    )
    if wrong_word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "错词不存在")

    await session.delete(wrong_word)
    await session.commit()
