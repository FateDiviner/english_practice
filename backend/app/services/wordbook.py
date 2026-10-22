from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_CONFLICT, ERROR_CODE_VALIDATION, AppError
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
    force: bool = False,
) -> None:
    """删除词书；有单词时必须显式 force，并先删除关联单词。"""
    wordbook = await get_wordbook(session, wordbook_id)
    if wordbook is None:
        raise AppError(404, 404, "词书不存在")

    word_count = await session.scalar(
        select(func.count(Word.id)).where(Word.wordbook_id == wordbook_id),
    )
    if word_count and not force:
        raise AppError(409, ERROR_CODE_CONFLICT, "词书包含单词，需 force=true 删除")

    try:
        if force:
            await session.execute(delete(Word).where(Word.wordbook_id == wordbook_id))
        await session.delete(wordbook)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, ERROR_CODE_CONFLICT, "词书存在关联数据，无法删除") from exc
