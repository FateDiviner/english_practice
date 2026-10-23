from collections.abc import AsyncIterator
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
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


def make_name(label: str) -> str:
    return f"pytest_answer_{label}_{uuid4().hex[:10]}"


async def clean_answer_data() -> None:
    async with async_session_factory() as session:
        user_ids = select(User.id).where(User.username.like("pytest_answer_%"))
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_answer_wb_%"))
        session_ids = select(PracticeSession.id).where(PracticeSession.user_id.in_(user_ids))
        await session.execute(delete(WrongWord).where(WrongWord.user_id.in_(user_ids)))
        await session.execute(delete(WordProgress).where(WordProgress.user_id.in_(user_ids)))
        await session.execute(delete(UserWordbook).where(UserWordbook.user_id.in_(user_ids)))
        await session.execute(
            delete(PracticeRecord).where(PracticeRecord.session_id.in_(session_ids))
        )
        await session.execute(
            delete(SessionQuestion).where(SessionQuestion.session_id.in_(session_ids))
        )
        await session.execute(delete(PracticeSession).where(PracticeSession.user_id.in_(user_ids)))
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_answer_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_answer_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_answers() -> AsyncIterator[None]:
    await clean_answer_data()
    yield
    await clean_answer_data()


async def create_admin(client: AsyncClient, label: str) -> dict[str, str]:
    username = make_name(f"admin_{label}")
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def create_user(client: AsyncClient, label: str) -> tuple[dict[str, str], int]:
    username = make_name(f"user_{label}")
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": USER_PASSWORD},
    )
    assert response.status_code == 201
    user_id = response.json()["data"]["id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}, user_id


async def create_wordbook(client: AsyncClient, admin: dict[str, str], label: str) -> int:
    response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=admin,
        json={"name": f"pytest_answer_wb_{label}_{uuid4().hex[:10]}", "status": "published"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


async def create_word(
    client: AsyncClient,
    admin: dict[str, str],
    wordbook_id: int,
    spelling: str,
) -> dict:
    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=admin,
        json={
            "spelling": spelling,
            "meaning_cn": f"释义 {spelling}",
            "example_en": f"Example for {spelling}.",
            "example_cn": f"{spelling} 的例句。",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def create_practice_session(
    client: AsyncClient,
    user: dict[str, str],
    wordbook_id: int,
    strict_mode: bool = True,
) -> dict:
    response = await client.post(
        "/api/v1/practice/sessions",
        headers=user,
        json={
            "wordbook_id": wordbook_id,
            "mode": "normal",
            "count": 10,
            "strict_mode": strict_mode,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


async def build_context(
    client: AsyncClient,
    label: str,
    words: list[str],
) -> dict:
    admin = await create_admin(client, label)
    user, user_id = await create_user(client, label)
    wordbook_id = await create_wordbook(client, admin, label)
    word_records = [await create_word(client, admin, wordbook_id, spelling) for spelling in words]
    session_data = await create_practice_session(client, user, wordbook_id)
    return {
        "admin": admin,
        "user": user,
        "user_id": user_id,
        "wordbook_id": wordbook_id,
        "words": word_records,
        "session": session_data,
    }


async def answer(
    client: AsyncClient,
    user: dict[str, str],
    session_id: int,
    word_id: int,
    user_input: str,
) -> dict:
    response = await client.post(
        f"/api/v1/practice/sessions/{session_id}/answer",
        headers=user,
        json={"word_id": word_id, "user_input": user_input, "used_hint": False},
    )
    return response
