from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_CONFLICT,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.models.word import Word
from app.models.wordbook import Wordbook
from app.schemas.word import WordCreateIn, WordUpdateIn


async def _ensure_wordbook_exists(session: AsyncSession, wordbook_id: int) -> None:
    wordbook = await session.get(Wordbook, wordbook_id)
    if wordbook is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")


async def get_word(session: AsyncSession, word_id: int) -> Word | None:
    """按主键查询单词。"""
    return await session.get(Word, word_id)


async def get_word_in_wordbook(
    session: AsyncSession,
    wordbook_id: int,
    spelling: str,
) -> Word | None:
    """按词书和 spelling 查询单词，用于重复校验。"""
    return await session.scalar(
        select(Word).where(
            Word.wordbook_id == wordbook_id,
            Word.spelling == spelling,
        ),
    )


async def create_word(
    session: AsyncSession,
    wordbook_id: int,
    payload: WordCreateIn,
) -> Word:
    """在指定词书中创建单词。"""
    await _ensure_wordbook_exists(session, wordbook_id)
    if await get_word_in_wordbook(session, wordbook_id, payload.spelling):
        raise AppError(409, ERROR_CODE_CONFLICT, "同词书内 spelling 已存在")

    word = Word(wordbook_id=wordbook_id, **payload.model_dump())
    session.add(word)
    try:
        await session.commit()
        await session.refresh(word)
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, ERROR_CODE_CONFLICT, "同词书内 spelling 已存在") from exc
    return word


async def update_word(
    session: AsyncSession,
    word_id: int,
    payload: WordUpdateIn,
) -> Word:
    """更新单词字段，并保护非空字段与词书内唯一约束。"""
    word = await get_word(session, word_id)
    if word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "单词不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "spelling" in updates and updates["spelling"] is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "spelling 不能为空")
    if "sort_order" in updates and updates["sort_order"] is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "sort_order 不能为空")

    new_spelling = updates.get("spelling")
    if new_spelling and new_spelling != word.spelling:
        duplicate = await get_word_in_wordbook(session, word.wordbook_id, new_spelling)
        if duplicate is not None:
            raise AppError(409, ERROR_CODE_CONFLICT, "同词书内 spelling 已存在")

    for field, value in updates.items():
        setattr(word, field, value)

    try:
        await session.commit()
        await session.refresh(word)
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, ERROR_CODE_CONFLICT, "同词书内 spelling 已存在") from exc
    return word


async def delete_word(session: AsyncSession, word_id: int) -> None:
    """删除单个单词。"""
    word = await get_word(session, word_id)
    if word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "单词不存在")

    await session.delete(word)
    await session.commit()


async def list_words(
    session: AsyncSession,
    wordbook_id: int,
    page: int,
    page_size: int,
    keyword: str | None = None,
) -> tuple[list[Word], int]:
    """按词书分页查询单词，keyword 模糊匹配 spelling。"""
    await _ensure_wordbook_exists(session, wordbook_id)
    conditions = [Word.wordbook_id == wordbook_id]
    if keyword:
        conditions.append(Word.spelling.contains(keyword))

    result = await session.execute(
        select(Word)
        .where(*conditions)
        .order_by(Word.sort_order.asc(), Word.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = await session.scalar(select(func.count(Word.id)).where(*conditions)) or 0
    return list(result.scalars().all()), total
