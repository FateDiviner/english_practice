from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook


def _to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


async def get_admin_overview(session: AsyncSession) -> dict[str, int]:
    """一次查询返回管理员概览六项指标。"""
    zone = ZoneInfo(get_settings().APP_TIMEZONE)
    today_start_local = datetime.combine(datetime.now(zone).date(), time.min).replace(tzinfo=zone)
    tomorrow_start_local = today_start_local + timedelta(days=1)
    active_start_local = today_start_local - timedelta(days=6)

    today_start = _to_utc_naive(today_start_local)
    tomorrow_start = _to_utc_naive(tomorrow_start_local)
    active_start = _to_utc_naive(active_start_local)

    total_users = select(func.count(User.id)).scalar_subquery()
    active_users = (
        select(func.count(func.distinct(PracticeSession.user_id)))
        .select_from(PracticeSession)
        .join(PracticeRecord, PracticeRecord.session_id == PracticeSession.id)
        .where(
            PracticeRecord.answered_at >= active_start,
            PracticeRecord.answered_at < tomorrow_start,
        )
        .scalar_subquery()
    )
    total_wordbooks = select(func.count(Wordbook.id)).scalar_subquery()
    total_words = select(func.count(Word.id)).scalar_subquery()
    today_sessions = (
        select(func.count(PracticeSession.id))
        .where(
            PracticeSession.started_at >= today_start,
            PracticeSession.started_at < tomorrow_start,
        )
        .scalar_subquery()
    )
    today_answers = (
        select(func.count(PracticeRecord.id))
        .where(
            PracticeRecord.answered_at >= today_start,
            PracticeRecord.answered_at < tomorrow_start,
        )
        .scalar_subquery()
    )

    result = await session.execute(
        select(
            total_users,
            active_users,
            total_wordbooks,
            total_words,
            today_sessions,
            today_answers,
        ),
    )
    row = result.one()
    return {
        "total_users": int(row[0] or 0),
        "active_users": int(row[1] or 0),
        "total_wordbooks": int(row[2] or 0),
        "total_words": int(row[3] or 0),
        "today_sessions": int(row[4] or 0),
        "today_answers": int(row[5] or 0),
    }
