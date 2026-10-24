from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.user import User
from app.models.user_wordbook import UserWordbook
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wordbook import Wordbook
from app.models.wrong_word import WrongWord
from app.services.profile.agents import DataExpert
from app.services.profile.blackboard import Blackboard
from app.services.profile.cache import TTLProfileCache
from app.services.profile.service import get_profile_orchestrator
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select

PREFIX = "pytest_profile_"
ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


def _name(label: str) -> str:
    return f"{PREFIX}{label}_{uuid4().hex[:10]}"


async def _clean_data() -> None:
    async with async_session_factory() as session:
        user_ids = list(
            await session.scalars(select(User.id).where(User.username.like(f"{PREFIX}%")))
        )
        wordbook_ids = list(
            await session.scalars(
                select(Wordbook.id).where(Wordbook.name.like(f"{PREFIX}%"))
            )
        )
        if not user_ids:
            await session.commit()
            return
        session_ids = list(
            await session.scalars(
                select(PracticeSession.id).where(PracticeSession.user_id.in_(user_ids))
            )
        )
        await session.execute(delete(WrongWord).where(WrongWord.user_id.in_(user_ids)))
        await session.execute(delete(WordProgress).where(WordProgress.user_id.in_(user_ids)))
        await session.execute(delete(UserWordbook).where(UserWordbook.user_id.in_(user_ids)))
        if session_ids:
            await session.execute(
                delete(PracticeRecord).where(PracticeRecord.session_id.in_(session_ids))
            )
            await session.execute(
                delete(SessionQuestion).where(SessionQuestion.session_id.in_(session_ids))
            )
        await session.execute(
            delete(PracticeSession).where(PracticeSession.user_id.in_(user_ids))
        )
        if wordbook_ids:
            await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
            await session.execute(delete(Wordbook).where(Wordbook.id.in_(wordbook_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_profile_data() -> AsyncIterator[None]:
    await _clean_data()
    get_profile_orchestrator.cache_clear()
    yield
    get_profile_orchestrator.cache_clear()
    await _clean_data()


async def _create_admin(client: AsyncClient, label: str) -> tuple[dict[str, str], int]:
    username = _name(f"admin_{label}")
    async with async_session_factory() as session:
        result = await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}, result.user_id


async def _create_user(client: AsyncClient, label: str) -> tuple[dict[str, str], int]:
    username = _name(f"user_{label}")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": USER_PASSWORD,
        },
    )
    assert response.status_code == 201
    user_id = response.json()["data"]["id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}, user_id


async def _seed_learning_data(admin_id: int, user_id: int) -> None:
    spellings = [
        "cat",
        "study",
        "strategy",
        "return",
        "rewrite",
        "remember",
        "international",
        "practice",
    ]
    now = datetime.now(UTC).replace(tzinfo=None)
    async with async_session_factory() as session:
        wordbook = Wordbook(
            name=_name("wordbook"),
            description="profile test",
            status="published",
            created_by=admin_id,
        )
        session.add(wordbook)
        await session.flush()
        words = [Word(wordbook_id=wordbook.id, spelling=item) for item in spellings]
        session.add_all(words)
        await session.flush()
        by_spelling = {item.spelling: item for item in words}

        for offset, correct in ((7, 5), (3, 6), (1, 8), (0, 9)):
            started_at = now - timedelta(days=offset, hours=2)
            session.add(
                PracticeSession(
                    user_id=user_id,
                    wordbook_id=wordbook.id,
                    mode="normal",
                    strict_mode=True,
                    total_count=10,
                    correct_count=correct,
                    status="finished",
                    started_at=started_at,
                    finished_at=started_at + timedelta(minutes=18),
                )
            )

        progress_levels = {
            "cat": 0,
            "study": 1,
            "strategy": 2,
            "return": 1,
            "rewrite": 1,
            "remember": 1,
            "international": 1,
            "practice": 2,
        }
        for spelling, mastery in progress_levels.items():
            session.add(
                WordProgress(
                    user_id=user_id,
                    word_id=by_spelling[spelling].id,
                    mastery_level=mastery,
                    correct_count=3 if mastery == 2 else 1,
                    wrong_count=0 if mastery == 2 else 2,
                    consecutive_correct=2 if mastery == 2 else 0,
                    last_result="correct" if mastery == 2 else "wrong",
                    last_practiced_at=now - timedelta(hours=1),
                )
            )

        for spelling, wrong_count, days_ago in (
            ("return", 3, 1),
            ("rewrite", 2, 2),
            ("remember", 2, 3),
            ("international", 1, 4),
        ):
            session.add(
                WrongWord(
                    user_id=user_id,
                    word_id=by_spelling[spelling].id,
                    wrong_count=wrong_count,
                    last_wrong_at=now - timedelta(days=days_ago),
                    resolved=False,
                )
            )
        await session.commit()


def _empty_blackboard() -> Blackboard:
    return Blackboard(
        user_id=1,
        username="empty_user",
        user_created_at=datetime.now(UTC).replace(tzinfo=None),
        word_progress=[],
        wrong_words=[],
        practice_sessions=[],
    )


async def test_profile_requires_admin_and_existing_user(client) -> None:
    user_headers, _ = await _create_user(client, "auth_user")
    admin_headers, _ = await _create_admin(client, "auth_admin")

    unauthenticated = await client.post("/api/v1/admin/users/1/profile")
    forbidden = await client.post("/api/v1/admin/users/1/profile", headers=user_headers)
    missing = await client.post(
        "/api/v1/admin/users/999999999/profile",
        headers=admin_headers,
    )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert missing.json()["message"] == "用户不存在"


async def test_profile_returns_structured_report_and_uses_cache(client) -> None:
    admin_headers, admin_id = await _create_admin(client, "report_admin")
    _, user_id = await _create_user(client, "report_user")
    await _seed_learning_data(admin_id, user_id)

    first = await client.post(
        f"/api/v1/admin/users/{user_id}/profile",
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["cache"]["hit"] is False
    assert first_data["agent_sequence"] == ["data", "habit", "diagnosis", "planner"]
    assert first_data["coverage"]["practice_session_count"] == 4
    assert first_data["coverage"]["wrong_word_count"] == 4
    trend = first_data["agents"]["data"]["accuracy_trend"]
    assert sum(item["session_count"] for item in trend) == 4
    assert first_data["agents"]["data"]["source"] == "heuristic"
    assert len(first_data["agents"]["diagnosis"]["focus_words"]) == 4
    assert any(
        item["kind"] == "prefix"
        for item in first_data["agents"]["diagnosis"]["error_patterns"]
    )
    assert len(first_data["agents"]["planner"]["review_plan"]) == 7
    assert len(first_data["summary"]["radar_metrics"]) == 8
    assert all(
        0 <= item["score"] <= 100
        for item in first_data["summary"]["radar_metrics"]
    )

    second = await client.post(
        f"/api/v1/admin/users/{user_id}/profile",
        headers=admin_headers,
    )
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["cache"]["hit"] is True
    assert second_data["generated_at"] == first_data["generated_at"]
    assert second_data["summary"] == first_data["summary"]


async def test_profile_handles_user_without_learning_data(client) -> None:
    admin_headers, _ = await _create_admin(client, "empty_admin")
    _, user_id = await _create_user(client, "empty_user")

    response = await client.post(
        f"/api/v1/admin/users/{user_id}/profile",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["summary"]["level"] == "insufficient_data"
    assert data["agents"]["data"]["accuracy_trend"] == []
    assert data["agents"]["planner"]["review_plan"][0]["focus_words"] == [
        "基础词汇",
        "基础词汇",
    ]


async def test_ttl_cache_runs_factory_once_for_same_key() -> None:
    cache = TTLProfileCache[int](ttl_seconds=60)
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        return 42

    first, first_hit, first_expiry = await cache.get_or_create("same", factory)
    second, second_hit, second_expiry = await cache.get_or_create("same", factory)

    assert (first, second) == (42, 42)
    assert (first_hit, second_hit) == (False, True)
    assert first_expiry == second_expiry
    assert calls == 1


async def test_invalid_llm_json_falls_back_to_deterministic_expert() -> None:
    class InvalidJsonLLM:
        async def stream(self, _messages):
            yield "这不是 JSON"

    result = await DataExpert(InvalidJsonLLM()).analyze(_empty_blackboard())

    assert result.source == "heuristic"
    assert result.metrics[0].score == 0
    assert "样本不足" in result.tags