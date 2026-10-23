from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_NOT_FOUND,
    AppError,
)
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.user_wordbook import UserWordbook
from app.models.word import Word
from app.models.word_progress import WordProgress


@dataclass(frozen=True)
class SessionFinishResult:
    session_id: int
    total: int
    correct: int
    accuracy: float
    duration_seconds: int
    finished_at: datetime


@dataclass(frozen=True)
class SessionDetailResult:
    session_id: int
    mode: str
    total: int
    correct: int
    accuracy: float
    duration_seconds: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    records: list[PracticeRecord]


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(correct / total * 100, 2)


def _duration_seconds(started_at: datetime, finished_at: datetime) -> int:
    return max(0, int((finished_at - started_at).total_seconds()))


def _finish_result(practice_session: PracticeSession) -> SessionFinishResult:
    finished_at = practice_session.finished_at or datetime.now(UTC).replace(tzinfo=None)
    return SessionFinishResult(
        session_id=practice_session.id,
        total=practice_session.total_count,
        correct=practice_session.correct_count,
        accuracy=_accuracy(practice_session.correct_count, practice_session.total_count),
        duration_seconds=_duration_seconds(practice_session.started_at, finished_at),
        finished_at=finished_at,
    )


async def _get_session_for_user(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    lock: bool = False,
) -> PracticeSession:
    query = select(PracticeSession).where(PracticeSession.id == session_id)
    if lock:
        query = query.with_for_update()
    practice_session = await session.scalar(query)
    if practice_session is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "练习会话不存在")
    if practice_session.user_id != user_id:
        raise AppError(403, ERROR_CODE_FORBIDDEN, "无权访问该练习会话")
    return practice_session


async def _update_user_wordbook(
    session: AsyncSession,
    user_id: int,
    wordbook_id: int,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    user_wordbook = await session.scalar(
        select(UserWordbook)
        .where(
            UserWordbook.user_id == user_id,
            UserWordbook.wordbook_id == wordbook_id,
        )
        .with_for_update(),
    )
    if user_wordbook is None:
        user_wordbook = UserWordbook(
            user_id=user_id,
            wordbook_id=wordbook_id,
            status="learning",
            started_at=started_at,
            last_practiced_at=finished_at,
        )
        session.add(user_wordbook)
    else:
        user_wordbook.last_practiced_at = finished_at
        if user_wordbook.started_at is None:
            user_wordbook.started_at = started_at

    word_ids = select(Word.id).where(Word.wordbook_id == wordbook_id)
    total_words = (
        await session.scalar(
            select(func.count(Word.id)).where(Word.wordbook_id == wordbook_id),
        )
        or 0
    )
    mastered_words = (
        await session.scalar(
            select(func.count(WordProgress.id)).where(
                WordProgress.user_id == user_id,
                WordProgress.word_id.in_(word_ids),
                WordProgress.mastery_level >= 2,
            ),
        )
        or 0
    )
    if total_words > 0 and mastered_words == total_words:
        user_wordbook.status = "completed"


async def finish_session(
    session: AsyncSession,
    user_id: int,
    session_id: int,
) -> SessionFinishResult:
    """结束练习会话；重复 finish 返回现有汇总且不改变 finished_at。"""
    practice_session = await _get_session_for_user(session, user_id, session_id, lock=True)
    if practice_session.status == "finished":
        return _finish_result(practice_session)

    finished_at = datetime.now(UTC).replace(tzinfo=None)
    practice_session.status = "finished"
    practice_session.finished_at = finished_at
    if practice_session.mode == "normal" and practice_session.wordbook_id is not None:
        await _update_user_wordbook(
            session,
            user_id,
            practice_session.wordbook_id,
            practice_session.started_at,
            finished_at,
        )
    await session.commit()
    return _finish_result(practice_session)


async def get_session_detail(
    session: AsyncSession,
    user_id: int,
    session_id: int,
) -> SessionDetailResult:
    """返回会话汇总和全部作答记录。"""
    practice_session = await _get_session_for_user(session, user_id, session_id)
    record_result = await session.execute(
        select(PracticeRecord)
        .where(PracticeRecord.session_id == session_id)
        .order_by(PracticeRecord.id.asc()),
    )
    records = list(record_result.scalars().all())
    finished_at = practice_session.finished_at or datetime.now(UTC).replace(tzinfo=None)
    return SessionDetailResult(
        session_id=practice_session.id,
        mode=practice_session.mode,
        total=practice_session.total_count,
        correct=practice_session.correct_count,
        accuracy=_accuracy(practice_session.correct_count, practice_session.total_count),
        duration_seconds=_duration_seconds(practice_session.started_at, finished_at),
        status=practice_session.status,
        started_at=practice_session.started_at,
        finished_at=practice_session.finished_at,
        records=records,
    )
