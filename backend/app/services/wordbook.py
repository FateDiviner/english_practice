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
from app.schemas.wordbook import WordbookCreateIn, WordbookUpdateIn


async def create_wordbook(
    session: AsyncSession,
    payload: WordbookCreateIn,
    created_by: int,
) -> Wordbook:
    """创建词书，状态默认由 schema 设置为 draft。"""
    wordbook = Wordbook(
        name=payload.name,
        description=payload.description,
        level=payload.level,
        status=payload.status,
        created_by=created_by,
    )
    session.add(wordbook)
    await session.commit()
    await session.refresh(wordbook)
    return wordbook


async def get_wordbook(session: AsyncSession, wordbook_id: int) -> Wordbook | None:
    """按主键查询词书。"""
    return await session.get(Wordbook, wordbook_id)


async def list_wordbooks(
    session: AsyncSession,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Wordbook, int]], int]:
    """分页查询词书并附带词数；聚合通过标量子查询完成。"""
    word_count = (
        select(func.count(Word.id))
        .where(Word.wordbook_id == Wordbook.id)
        .correlate(Wordbook)
        .scalar_subquery()
    )
    result = await session.execute(
        select(Wordbook, word_count.label("word_count"))
        .order_by(Wordbook.created_at.desc(), Wordbook.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = await session.scalar(select(func.count()).select_from(Wordbook)) or 0
    return list(result.all()), total


async def update_wordbook(
    session: AsyncSession,
    wordbook_id: int,
    payload: WordbookUpdateIn,
) -> Wordbook:
    """更新词书可编辑字段，name 不允许被显式清空。"""
    wordbook = await get_wordbook(session, wordbook_id)
    if wordbook is None:
        raise AppError(404, 404, "词书不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "词书名称不能为空")
    if "status" in updates and updates["status"] is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "词书状态不能为空")

    for field, value in updates.items():
        setattr(wordbook, field, value)

    await session.commit()
    await session.refresh(wordbook)
    return wordbook


async def delete_wordbook(
    session: AsyncSession,
    wordbook_id: int,
) -> None:
    """仅允许删除空词书；存在单词时必须先清空。"""
    wordbook = await get_wordbook(session, wordbook_id)
    if wordbook is None:
        raise AppError(404, 404, "词书不存在")

    word_count = await session.scalar(
        select(func.count(Word.id)).where(Word.wordbook_id == wordbook_id),
    )
    if word_count:
        raise AppError(409, ERROR_CODE_CONFLICT, "请先清空词书内单词")

    try:
        await session.delete(wordbook)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, ERROR_CODE_CONFLICT, "词书存在关联数据，无法删除") from exc


async def get_published_wordbook(session: AsyncSession, wordbook_id: int) -> Wordbook:
    """只允许读取 published 词书。"""
    wordbook = await get_wordbook(session, wordbook_id)
    if wordbook is None or wordbook.status != "published":
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")
    return wordbook


async def list_published_wordbooks(
    session: AsyncSession,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Wordbook, int]], int]:
    """分页查询 published 词书并附带单词数。"""
    word_count = (
        select(func.count(Word.id))
        .where(Word.wordbook_id == Wordbook.id)
        .correlate(Wordbook)
        .scalar_subquery()
    )
    conditions = [Wordbook.status == "published"]
    result = await session.execute(
        select(Wordbook, word_count.label("word_count"))
        .where(*conditions)
        .order_by(Wordbook.created_at.desc(), Wordbook.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = (
        await session.scalar(
            select(func.count(Wordbook.id)).where(*conditions),
        )
        or 0
    )
    return list(result.all()), total


async def get_published_wordbook_detail(
    session: AsyncSession,
    wordbook_id: int,
) -> tuple[Wordbook, int]:
    """返回 published 词书详情及单词数。"""
    wordbook = await get_published_wordbook(session, wordbook_id)
    word_count = (
        await session.scalar(
            select(func.count(Word.id)).where(Word.wordbook_id == wordbook.id),
        )
        or 0
    )
    return wordbook, word_count


async def list_published_words(
    session: AsyncSession,
    wordbook_id: int,
    page: int,
    page_size: int,
    mastery: int | None = None,
) -> tuple[list[Word], int]:
    """分页查询 published 词书中的单词；mastery 暂未实现，仅接收参数。"""
    await get_published_wordbook(session, wordbook_id)
    # word_progress 尚未建表，mastery 过滤暂时忽略，响应统一返回 null。
    _ = mastery
    conditions = [Word.wordbook_id == wordbook_id]
    result = await session.execute(
        select(Word)
        .where(*conditions)
        .order_by(Word.sort_order.asc(), Word.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = await session.scalar(select(func.count(Word.id)).where(*conditions)) or 0
    return list(result.scalars().all()), total
