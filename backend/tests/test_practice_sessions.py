from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wordbook import Wordbook
from app.models.wrong_word import WrongWord
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


def make_prefix(label: str) -> str:
    return f"pytest_practice_{label}_{uuid4().hex[:10]}"


async def clean_practice_data() -> None:
    async with async_session_factory() as session:
        user_ids = select(User.id).where(User.username.like("pytest_practice_%"))
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_practice_wb_%"))
        await session.execute(delete(WrongWord).where(WrongWord.user_id.in_(user_ids)))
        await session.execute(delete(WordProgress).where(WordProgress.user_id.in_(user_ids)))
        await session.execute(delete(PracticeSession).where(PracticeSession.user_id.in_(user_ids)))
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_practice_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_practice_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_practice() -> AsyncIterator[None]:
    await clean_practice_data()
    yield
    await clean_practice_data()


async def create_admin_headers(client: AsyncClient, label: str) -> dict[str, str]:
    username = f"pytest_practice_admin_{label}_{uuid4().hex[:10]}"
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def create_user(client: AsyncClient, label: str) -> dict[str, str]:
    username = f"pytest_practice_user_{label}_{uuid4().hex[:10]}"
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": USER_PASSWORD},
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    return {"Authorization": f"Bearer {login_response.json()['data']['access_token']}"}


async def create_wordbook(
    client: AsyncClient,
    headers: dict[str, str],
    label: str,
    status_value: str,
) -> dict:
    response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=headers,
        json={
            "name": f"pytest_practice_wb_{label}_{uuid4().hex[:10]}",
            "description": f"{label} wordbook",
            "level": "CET4",
            "status": status_value,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def create_word(
    client: AsyncClient, headers: dict[str, str], wordbook_id: int, spelling: str
) -> dict:
    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=headers,
        json={
            "spelling": spelling,
            "phonetic_uk": f"/{spelling}/",
            "meaning_cn": f"释义 {spelling}",
            "part_of_speech": "n.",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def test_create_session_requires_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/practice/sessions",
        json={"mode": "normal", "wordbook_id": 1, "count": 10},
    )

    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_normal_session_returns_questions_without_spelling(client: AsyncClient) -> None:
    admin = await create_admin_headers(client, "normal")
    user = await create_user(client, "normal")
    wordbook = await create_wordbook(client, admin, "normal", "published")
    await create_word(client, admin, wordbook["id"], "alpha")
    await create_word(client, admin, wordbook["id"], "beta")
    await create_word(client, admin, wordbook["id"], "gamma")

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={
            "wordbook_id": wordbook["id"],
            "mode": "normal",
            "count": 20,
            "strict_mode": False,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 3
    assert len(body["questions"]) == 3
    assert body["notice"]
    for question in body["questions"]:
        assert set(question) == {
            "word_id",
            "phonetic_uk",
            "phonetic_us",
            "meaning_cn",
            "part_of_speech",
            "audio_url",
            "hint",
        }
        assert set(question["hint"]) == {"length"}
        assert question["hint"]["length"] > 0
    async with async_session_factory() as session:
        stored_session = await session.get(PracticeSession, body["session_id"])
        assert stored_session is not None
        assert stored_session.status == "ongoing"
        assert stored_session.total_count == 3
        assert stored_session.strict_mode is False
        question_rows = list(
            (
                await session.scalars(
                    select(SessionQuestion)
                    .where(SessionQuestion.session_id == body["session_id"])
                    .order_by(SessionQuestion.sort_order),
                )
            ).all(),
        )
        assert len(question_rows) == body["total"]
        assert [row.sort_order for row in question_rows] == list(range(body["total"]))
        assert [row.word_id for row in question_rows] == [q["word_id"] for q in body["questions"]]
        session.add(
            SessionQuestion(
                session_id=body["session_id"],
                word_id=question_rows[0].word_id,
                sort_order=99,
            ),
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_normal_session_rejects_non_published_wordbook(client: AsyncClient) -> None:
    admin = await create_admin_headers(client, "draft")
    user = await create_user(client, "draft")
    wordbook = await create_wordbook(client, admin, "draft", "draft")
    await create_word(client, admin, wordbook["id"], "alpha")

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={"wordbook_id": wordbook["id"], "mode": "normal", "count": 10},
    )

    assert response.status_code == 404
    assert response.json()["code"] == 40401


async def test_invalid_count_returns_42201(client: AsyncClient) -> None:
    user = await create_user(client, "count")

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={"mode": "normal", "wordbook_id": 1, "count": 15},
    )

    assert response.status_code == 422
    assert response.json()["code"] == 42201


async def test_empty_wordbook_returns_40001(client: AsyncClient) -> None:
    admin = await create_admin_headers(client, "empty")
    user = await create_user(client, "empty")
    wordbook = await create_wordbook(client, admin, "empty", "published")

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={"wordbook_id": wordbook["id"], "mode": "normal", "count": 10},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 40001


async def test_wrong_only_uses_only_unresolved_wrong_words(client: AsyncClient) -> None:
    admin = await create_admin_headers(client, "wrong")
    user = await create_user(client, "wrong")
    wordbook = await create_wordbook(client, admin, "wrong", "published")
    first_word = await create_word(client, admin, wordbook["id"], "alpha")
    second_word = await create_word(client, admin, wordbook["id"], "beta")
    third_word = await create_word(client, admin, wordbook["id"], "gamma")

    async with async_session_factory() as session:
        user_record = await session.scalar(
            select(User).where(User.email.like("pytest_practice_user_wrong_%")),
        )
        assert user_record is not None
        session.add_all(
            [
                WrongWord(user_id=user_record.id, word_id=first_word["id"], resolved=False),
                WrongWord(user_id=user_record.id, word_id=second_word["id"], resolved=True),
            ],
        )
        await session.commit()

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={"mode": "wrong_only", "wordbook_id": 999999999, "count": 10},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 1
    assert body["questions"][0]["word_id"] == first_word["id"]
    assert body["questions"][0]["word_id"] != second_word["id"]
    assert body["questions"][0]["word_id"] != third_word["id"]
    assert body["notice"]


async def test_wrong_only_empty_returns_40001(client: AsyncClient) -> None:
    user = await create_user(client, "wrong_empty")

    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={"mode": "wrong_only", "count": 10},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 40001
    assert "错词本为空" in response.json()["message"]
