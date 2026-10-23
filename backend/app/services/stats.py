from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exception_handlers import ERROR_CODE_VALIDATION, AppError
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord

MAX_DAILY_RANGE_DAYS = 90


@dataclass(frozen=True)
class OverviewResult:
    total_practiced: int
    accuracy: float
    streak_days: int
    mastered_words: int
    wrong_words_count: int


@dataclass(frozen=True)
class DailyResult:
    date: date
    answered: int
    correct: int


def _timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().APP_TIMEZONE)


def _utc_offset_string(zone: ZoneInfo) -> str:
    offset = datetime.now(zone).utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _local_date_expression(zone: ZoneInfo):
    return func.date(
        func.convert_tz(PracticeRecord.answered_at, "+00:00", _utc_offset_string(zone)),
    )


def _to_local_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _compute_streak(active_dates: set[date], today: date) -> int:
    cursor = today if today in active_dates else today - timedelta(days=1)
    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def get_overview(session: AsyncSession, user_id: int) -> OverviewResult:
    aggregate = await session.execute(
        select(
            func.count(PracticeRecord.id),
            func.coalesce(
                func.sum(case((PracticeRecord.is_correct.is_(True), 1), else_=0)),
                0,
            ),
        )
        .join(PracticeSession, PracticeRecord.session_id == PracticeSession.id)
        .where(PracticeSession.user_id == user_id),
    )
    total_practiced, correct_count = aggregate.one()
    accuracy = round(float(correct_count) / total_practiced, 2) if total_practiced else 0.0

    zone = _timezone()
    local_date = _local_date_expression(zone)
    date_rows = await session.scalars(
        select(local_date)
        .join(PracticeSession, PracticeRecord.session_id == PracticeSession.id)
        .where(PracticeSession.user_id == user_id)
        .group_by(local_date)
        .order_by(local_date.desc()),
    )
    active_dates = {_to_local_date(value) for value in date_rows.all()}
    today = datetime.now(zone).date()

    mastered_words = (
        await session.scalar(
            select(func.count(WordProgress.id)).where(
                WordProgress.user_id == user_id,
                WordProgress.mastery_level == 2,
            ),
        )
        or 0
    )
    wrong_words_count = (
        await session.scalar(
            select(func.count(WrongWord.id)).where(
                WrongWord.user_id == user_id,
                WrongWord.resolved.is_(False),
            ),
        )
        or 0
    )

    return OverviewResult(
        total_practiced=int(total_practiced),
        accuracy=accuracy,
        streak_days=_compute_streak(active_dates, today),
        mastered_words=int(mastered_words),
        wrong_words_count=int(wrong_words_count),
    )


async def get_daily(
    session: AsyncSession,
    user_id: int,
    date_from: date,
    date_to: date,
) -> list[DailyResult]:
    if date_from > date_to:
        raise AppError(422, ERROR_CODE_VALIDATION, "date_from 不能晚于 date_to")
    if (date_to - date_from).days > MAX_DAILY_RANGE_DAYS:
        raise AppError(422, ERROR_CODE_VALIDATION, "日期跨度不能超过 90 天")

    zone = _timezone()
    local_start = datetime.combine(date_from, time.min).replace(tzinfo=zone)
    local_end = datetime.combine(date_to + timedelta(days=1), time.min).replace(tzinfo=zone)
    utc_start = local_start.astimezone(UTC).replace(tzinfo=None)
    utc_end = local_end.astimezone(UTC).replace(tzinfo=None)
    local_date = _local_date_expression(zone)
    rows = await session.execute(
        select(
            local_date.label("practice_date"),
            func.count(PracticeRecord.id).label("answered"),
            func.sum(case((PracticeRecord.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .join(PracticeSession, PracticeRecord.session_id == PracticeSession.id)
        .where(
            PracticeSession.user_id == user_id,
            PracticeRecord.answered_at >= utc_start,
            PracticeRecord.answered_at < utc_end,
        )
        .group_by(local_date)
        .order_by(local_date.asc()),
    )
    return [
        DailyResult(
            date=_to_local_date(row.practice_date),
            answered=int(row.answered),
            correct=int(row.correct or 0),
        )
        for row in rows
    ]
