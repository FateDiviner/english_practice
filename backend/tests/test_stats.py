from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.practice_record import PracticeRecord
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord
from httpx import AsyncClient

from tests.practice_answer_helpers import build_context, create_user


def local_today() -> date:
    return datetime.now(ZoneInfo(get_settings().APP_TIMEZONE)).date()


def local_day_utc(day: date) -> datetime:
    zone = ZoneInfo(get_settings().APP_TIMEZONE)
    local_noon = datetime.combine(day, time(hour=12), tzinfo=zone)
    return local_noon.astimezone(UTC).replace(tzinfo=None)


async def insert_record(context: dict, word_id: int, is_correct: bool, day: date) -> None:
    async with async_session_factory() as session:
        session.add(
            PracticeRecord(
                session_id=context["session"]["session_id"],
                word_id=word_id,
                user_input="answer",
                is_correct=is_correct,
                answered_at=local_day_utc(day),
            ),
        )
        await session.commit()


async def get_overview(client: AsyncClient, user: dict[str, str]) -> dict:
    response = await client.get("/api/v1/stats/overview", headers=user)
    assert response.status_code == 200
    return response.json()["data"]


async def test_stats_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stats/overview")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_overview_without_records_returns_zero(client: AsyncClient) -> None:
    user, _ = await create_user(client, "empty_stats")

    overview = await get_overview(client, user)

    assert overview == {
        "total_practiced": 0,
        "accuracy": 0.0,
        "streak_days": 0,
        "mastered_words": 0,
        "wrong_words_count": 0,
    }


async def test_overview_aggregates_user_data(client: AsyncClient) -> None:
    context = await build_context(client, "overview", ["alpha", "beta"])
    alpha_id = context["words"][0]["id"]
    beta_id = context["words"][1]["id"]
    today = local_today()
    await insert_record(context, alpha_id, True, today)
    await insert_record(context, beta_id, False, today)

    async with async_session_factory() as session:
        session.add(
            WordProgress(
                user_id=context["user_id"],
                word_id=alpha_id,
                mastery_level=2,
                correct_count=2,
                consecutive_correct=2,
            ),
        )
        session.add(
            WrongWord(
                user_id=context["user_id"],
                word_id=beta_id,
                wrong_count=1,
                last_wrong_at=local_day_utc(today),
                resolved=False,
            ),
        )
        await session.commit()

    overview = await get_overview(client, context["user"])

    assert overview["total_practiced"] == 2
    assert overview["accuracy"] == 0.5
    assert overview["streak_days"] == 1
    assert overview["mastered_words"] == 1
    assert overview["wrong_words_count"] == 1


async def test_streak_counts_today(client: AsyncClient) -> None:
    context = await build_context(client, "streak_today", ["alpha"])
    await insert_record(context, context["words"][0]["id"], True, local_today())

    overview = await get_overview(client, context["user"])
    assert overview["streak_days"] == 1


async def test_streak_uses_yesterday_when_today_has_no_record(client: AsyncClient) -> None:
    context = await build_context(client, "streak_yesterday", ["alpha"])
    yesterday = local_today() - timedelta(days=1)
    await insert_record(context, context["words"][0]["id"], True, yesterday)

    overview = await get_overview(client, context["user"])
    assert overview["streak_days"] == 1


async def test_streak_breaks_on_missing_day(client: AsyncClient) -> None:
    context = await build_context(client, "streak_broken", ["alpha", "beta"])
    today = local_today()
    await insert_record(context, context["words"][0]["id"], True, today)
    await insert_record(context, context["words"][1]["id"], True, today - timedelta(days=2))

    overview = await get_overview(client, context["user"])
    assert overview["streak_days"] == 1


async def test_daily_groups_by_app_timezone(client: AsyncClient) -> None:
    context = await build_context(client, "daily", ["alpha", "beta", "gamma"])
    today = local_today()
    day_one = today - timedelta(days=2)
    day_two = today - timedelta(days=1)
    await insert_record(context, context["words"][0]["id"], True, day_one)
    await insert_record(context, context["words"][1]["id"], True, day_one)
    await insert_record(context, context["words"][2]["id"], False, day_two)

    response = await client.get(
        f"/api/v1/stats/daily?from={day_one.isoformat()}&to={day_two.isoformat()}",
        headers=context["user"],
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == [
        {"date": day_one.isoformat(), "answered": 2, "correct": 2},
        {"date": day_two.isoformat(), "answered": 1, "correct": 0},
    ]


async def test_daily_rejects_invalid_range(client: AsyncClient) -> None:
    user, _ = await create_user(client, "daily_errors")
    today = local_today()
    reverse = await client.get(
        "/api/v1/stats/daily",
        params={"from": today.isoformat(), "to": (today - timedelta(days=1)).isoformat()},
        headers=user,
    )
    too_wide = await client.get(
        "/api/v1/stats/daily",
        params={"from": (today - timedelta(days=91)).isoformat(), "to": today.isoformat()},
        headers=user,
    )

    assert reverse.status_code == 422
    assert reverse.json()["code"] == 42201
    assert too_wide.status_code == 422
    assert too_wide.json()["code"] == 42201


async def test_other_user_records_are_not_included(client: AsyncClient) -> None:
    first = await build_context(client, "owner_stats", ["alpha"])
    second = await build_context(client, "other_stats", ["alpha"])
    today = local_today()
    await insert_record(first, first["words"][0]["id"], True, today)
    await insert_record(second, second["words"][0]["id"], True, today)

    overview = await get_overview(client, first["user"])
    assert overview["total_practiced"] == 1
    assert overview["accuracy"] == 1.0


async def test_utc_late_night_groups_into_next_shanghai_day(client: AsyncClient) -> None:
    context = await build_context(client, "utc_boundary", ["alpha"])
    async with async_session_factory() as session:
        session.add(
            PracticeRecord(
                session_id=context["session"]["session_id"],
                word_id=context["words"][0]["id"],
                user_input="alpha",
                is_correct=True,
                answered_at=datetime(2026, 10, 22, 23, 30),
            ),
        )
        await session.commit()

    daily = await client.get(
        "/api/v1/stats/daily",
        params={"from": "2026-10-22", "to": "2026-10-23"},
        headers=context["user"],
    )
    overview = await get_overview(client, context["user"])

    assert daily.status_code == 200
    assert daily.json()["data"]["items"] == [
        {"date": "2026-10-23", "answered": 1, "correct": 1},
    ]
    assert overview["streak_days"] == 1
