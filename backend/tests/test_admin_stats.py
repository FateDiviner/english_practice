from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook
from app.services.admin_stats import get_admin_overview
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.practice_answer_helpers import (
    build_context,
    create_admin,
    create_user,
)


def local_today() -> date:
    return datetime.now(ZoneInfo(get_settings().APP_TIMEZONE)).date()


def to_utc_naive(local_value: datetime) -> datetime:
    return local_value.astimezone(UTC).replace(tzinfo=None)


async def insert_record(context: dict, word_id: int, is_correct: bool) -> None:
    zone = ZoneInfo(get_settings().APP_TIMEZONE)
    local_noon = datetime.combine(local_today(), time(hour=12), tzinfo=zone)
    async with async_session_factory() as session:
        session.add(
            PracticeRecord(
                session_id=context["session"]["session_id"],
                word_id=word_id,
                user_input="answer",
                is_correct=is_correct,
                answered_at=to_utc_naive(local_noon),
            ),
        )
        await session.commit()


async def expected_overview() -> dict[str, int]:
    zone = ZoneInfo(get_settings().APP_TIMEZONE)
    today_start_local = datetime.combine(local_today(), time.min).replace(tzinfo=zone)
    tomorrow_start_local = today_start_local + timedelta(days=1)
    active_start_local = today_start_local - timedelta(days=6)
    today_start = to_utc_naive(today_start_local)
    tomorrow_start = to_utc_naive(tomorrow_start_local)
    active_start = to_utc_naive(active_start_local)

    async with async_session_factory() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_wordbooks = await session.scalar(select(func.count(Wordbook.id)))
        total_words = await session.scalar(select(func.count(Word.id)))
        active_users = await session.scalar(
            select(func.count(func.distinct(PracticeSession.user_id)))
            .select_from(PracticeSession)
            .join(PracticeRecord, PracticeRecord.session_id == PracticeSession.id)
            .where(
                PracticeRecord.answered_at >= active_start,
                PracticeRecord.answered_at < tomorrow_start,
            ),
        )
        today_sessions = await session.scalar(
            select(func.count(PracticeSession.id)).where(
                PracticeSession.started_at >= today_start,
                PracticeSession.started_at < tomorrow_start,
            ),
        )
        today_answers = await session.scalar(
            select(func.count(PracticeRecord.id)).where(
                PracticeRecord.answered_at >= today_start,
                PracticeRecord.answered_at < tomorrow_start,
            ),
        )

    return {
        "total_users": int(total_users or 0),
        "active_users": int(active_users or 0),
        "total_wordbooks": int(total_wordbooks or 0),
        "total_words": int(total_words or 0),
        "today_sessions": int(today_sessions or 0),
        "today_answers": int(today_answers or 0),
    }


class FakeResult:
    def one(self) -> tuple[int, int, int, int, int, int]:
        return (0, 0, 0, 0, 0, 0)


class FakeSession:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, _statement: object) -> FakeResult:
        self.execute_calls += 1
        return FakeResult()


async def test_admin_overview_empty_returns_zero_with_one_query() -> None:
    session = FakeSession()
    result = await get_admin_overview(session)  # type: ignore[arg-type]

    assert result == {
        "total_users": 0,
        "active_users": 0,
        "total_wordbooks": 0,
        "total_words": 0,
        "today_sessions": 0,
        "today_answers": 0,
    }
    assert session.execute_calls == 1


async def test_admin_overview_permissions(client: AsyncClient) -> None:
    unauthenticated = await client.get("/api/v1/admin/overview")
    normal_user, _ = await create_user(client, "perm")
    forbidden = await client.get("/api/v1/admin/overview", headers=normal_user)

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == 40101
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == 40301


async def test_admin_overview_metrics(client: AsyncClient) -> None:
    admin = await create_admin(client, "overview")
    context = await build_context(client, "metrics", ["alpha", "beta"])
    await insert_record(context, context["words"][0]["id"], True)
    await insert_record(context, context["words"][1]["id"], False)

    expected = await expected_overview()
    response = await client.get("/api/v1/admin/overview", headers=admin)

    assert response.status_code == 200
    assert response.json()["data"] == expected
