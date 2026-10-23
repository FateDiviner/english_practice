import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_BAD_REQUEST,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wordbook import Wordbook
from app.models.wrong_word import WrongWord
from app.services.practice_answer import answer_question  # noqa: F401

MASTERED_MIX_DIVISOR = 5


def _split_by_mastery(
    words: list[Word],
    progress_by_word: dict[int, WordProgress],
) -> tuple[list[Word], list[Word]]:
    unmastered: list[Word] = []
    mastered: list[Word] = []
    for word in words:
        progress = progress_by_word.get(word.id)
        if progress is not None and progress.mastery_level >= 2:
            mastered.append(word)
        else:
            unmastered.append(word)
    return unmastered, mastered


def _select_words(
    words: list[Word],
    progress_by_word: dict[int, WordProgress],
    count: int,
) -> list[Word]:
    """未掌握词优先，并随机混入少量已掌握词。"""
    unmastered, mastered = _split_by_mastery(words, progress_by_word)
    randomizer = random.SystemRandom()
    randomizer.shuffle(unmastered)
    randomizer.shuffle(mastered)

    mastered_target = min(len(mastered), max(1, count // MASTERED_MIX_DIVISOR))
    unmastered_quota = count - mastered_target

    selected = list(unmastered[:unmastered_quota])
    selected.extend(mastered[:mastered_target])

    remaining = count - len(selected)
    if remaining > 0:
        leftovers = unmastered[unmastered_quota:] + mastered[mastered_target:]
        randomizer.shuffle(leftovers)
        selected.extend(leftovers[:remaining])

    randomizer.shuffle(selected)
    return selected


async def _load_progress(
    session: AsyncSession,
    user_id: int,
    word_ids: list[int],
) -> dict[int, WordProgress]:
    if not word_ids:
        return {}
    result = await session.execute(
        select(WordProgress).where(
            WordProgress.user_id == user_id,
            WordProgress.word_id.in_(word_ids),
        ),
    )
    return {progress.word_id: progress for progress in result.scalars().all()}


async def _load_normal_words(session: AsyncSession, wordbook_id: int) -> list[Word]:
    wordbook = await session.get(Wordbook, wordbook_id)
    if wordbook is None or wordbook.status != "published":
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")

    result = await session.execute(select(Word).where(Word.wordbook_id == wordbook_id))
    return list(result.scalars().all())


async def _load_wrong_words(session: AsyncSession, user_id: int) -> list[Word]:
    result = await session.execute(
        select(Word)
        .join(WrongWord, WrongWord.word_id == Word.id)
        .where(
            WrongWord.user_id == user_id,
            WrongWord.resolved.is_(False),
        ),
    )
    return list(result.scalars().all())


async def create_session(
    session: AsyncSession,
    user_id: int,
    wordbook_id: int | None,
    mode: str,
    count: int,
    strict_mode: bool,
) -> tuple[PracticeSession, list[Word], str | None]:
    """创建练习会话并选出题目，同时持久化 strict_mode。"""

    if mode == "normal":
        if wordbook_id is None:
            raise AppError(422, ERROR_CODE_VALIDATION, "normal 模式需要 wordbook_id")
        words = await _load_normal_words(session, wordbook_id)
    else:
        words = await _load_wrong_words(session, user_id)
        wordbook_id = None

    if not words:
        message = "词书暂无单词" if mode == "normal" else "错词本为空"
        raise AppError(400, ERROR_CODE_BAD_REQUEST, message)

    progress_by_word = await _load_progress(
        session,
        user_id,
        [word.id for word in words],
    )
    selected_words = _select_words(words, progress_by_word, count)
    notice = None
    if len(selected_words) < count:
        notice = f"可用单词不足，实际出题 {len(selected_words)} 道"

    practice_session = PracticeSession(
        user_id=user_id,
        wordbook_id=wordbook_id,
        mode=mode,
        strict_mode=strict_mode,
        total_count=len(selected_words),
        status="ongoing",
    )
    session.add(practice_session)
    await session.flush()
    session.add_all(
        [
            SessionQuestion(
                session_id=practice_session.id,
                word_id=word.id,
                sort_order=sort_order,
            )
            for sort_order, word in enumerate(selected_words)
        ],
    )
    await session.commit()
    await session.refresh(practice_session)
    return practice_session, selected_words, notice
