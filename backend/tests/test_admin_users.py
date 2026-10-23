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
from sqlalchemy import delete, or_, select

PREFIX = "pytest_admin_user_"
ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"
NEW_PASSWORD = "NewUserPass123!"


def make_name(label: str) -> str:
    return f"{PREFIX}{label}_{uuid4().hex[:10]}"


async def clean_test_data() -> None:
    async with async_session_factory() as session:
        user_ids = list(
            await session.scalars(select(User.id).where(User.username.like(f"{PREFIX}%")))
        )
        wordbook_ids = list(
            await session.scalars(select(Wordbook.id).where(Wordbook.name.like(f"{PREFIX}%")))
        )
        session_ids = list(
            await session.scalars(
                select(PracticeSession.id).where(
                    or_(
                        PracticeSession.user_id.in_(user_ids),
                        PracticeSession.wordbook_id.in_(wordbook_ids),
                    )
                )
            )
        )
        if user_ids:
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
                delete(PracticeSession).where(PracticeSession.id.in_(session_ids))
            )
        if wordbook_ids:
            await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
            await session.execute(delete(Wordbook).where(Wordbook.id.in_(wordbook_ids)))
        if user_ids:
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_admin_users() -> AsyncIterator[None]:
    await clean_test_data()
    yield
    await clean_test_data()


async def create_admin_headers(client: AsyncClient, label: str) -> tuple[dict[str, str], int]:
    username = make_name(f"admin_{label}")
    async with async_session_factory() as session:
        result = await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}, result.user_id


async def register_user(client: AsyncClient, label: str) -> dict:
    username = make_name(label)
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": USER_PASSWORD},
    )
    assert response.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    return {
        "id": response.json()["data"]["id"],
        "username": username,
        "headers": {"Authorization": f"Bearer {login.json()['data']['access_token']}"},
    }


async def create_practice_data(
    client: AsyncClient,
    admin: dict[str, str],
    user: dict,
) -> None:
    wordbook_response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=admin,
        json={"name": make_name("wb"), "status": "published"},
    )
    wordbook_id = wordbook_response.json()["data"]["id"]
    word_response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=admin,
        json={"spelling": "alpha", "meaning_cn": "阿尔法"},
    )
    assert word_response.status_code == 201
    session_response = await client.post(
        "/api/v1/practice/sessions",
        headers=user["headers"],
        json={"wordbook_id": wordbook_id, "mode": "normal", "count": 10, "strict_mode": True},
    )
    session_data = session_response.json()["data"]
    answer = await client.post(
        f"/api/v1/practice/sessions/{session_data['session_id']}/answer",
        headers=user["headers"],
        json={"word_id": word_response.json()["data"]["id"], "user_input": "alpha"},
    )
    assert answer.status_code == 200


async def test_admin_user_permissions(client: AsyncClient) -> None:
    unauthenticated = await client.get("/api/v1/admin/users")
    user = await register_user(client, "permission")
    forbidden = await client.get("/api/v1/admin/users", headers=user["headers"])

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == 40101
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == 40301


async def test_list_users_keyword_status_and_pagination(client: AsyncClient) -> None:
    admin, _ = await create_admin_headers(client, "list")
    first = await register_user(client, "list_first")
    await register_user(client, "list_second")
    await register_user(client, "list_third")

    page = await client.get(
        "/api/v1/admin/users?page=1&page_size=2",
        headers=admin,
    )
    search = await client.get(
        f"/api/v1/admin/users?keyword={first['username']}",
        headers=admin,
    )

    assert page.status_code == 200
    assert len(page.json()["data"]["items"]) == 2
    assert page.json()["data"]["total"] >= 3
    assert search.status_code == 200
    assert search.json()["data"]["total"] == 1
    assert search.json()["data"]["items"][0]["id"] == first["id"]


async def test_disable_user_revokes_token_and_filters_status(client: AsyncClient) -> None:
    admin, admin_id = await create_admin_headers(client, "status")
    user = await register_user(client, "status_target")

    self_disable = await client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        headers=admin,
        json={"status": "disabled"},
    )
    disabled = await client.patch(
        f"/api/v1/admin/users/{user['id']}/status",
        headers=admin,
        json={"status": "disabled"},
    )
    existing_token = await client.get("/api/v1/auth/me", headers=user["headers"])
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": user["username"], "password": USER_PASSWORD},
    )
    filtered = await client.get(
        f"/api/v1/admin/users?keyword={user['username']}&status=disabled",
        headers=admin,
    )

    assert self_disable.status_code == 400
    assert self_disable.json()["code"] == 40001
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == "disabled"
    assert existing_token.status_code == 401
    assert existing_token.json()["code"] == 40101
    assert login.status_code == 403
    assert login.json()["code"] == 40301
    assert filtered.json()["data"]["total"] == 1


async def test_reset_password_and_validation(client: AsyncClient) -> None:
    admin, _ = await create_admin_headers(client, "reset")
    user = await register_user(client, "reset_target")

    short = await client.post(
        f"/api/v1/admin/users/{user['id']}/reset-password",
        headers=admin,
        json={"new_password": "short"},
    )
    reset = await client.post(
        f"/api/v1/admin/users/{user['id']}/reset-password",
        headers=admin,
        json={"new_password": NEW_PASSWORD},
    )
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"account": user["username"], "password": USER_PASSWORD},
    )
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"account": user["username"], "password": NEW_PASSWORD},
    )
    missing = await client.post(
        "/api/v1/admin/users/999999999/reset-password",
        headers=admin,
        json={"new_password": NEW_PASSWORD},
    )

    assert short.status_code == 422
    assert short.json()["code"] == 42201
    assert reset.status_code == 200
    assert reset.json()["data"] == {"reset": True}
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert missing.status_code == 404
    assert missing.json()["code"] == 40401


async def test_user_stats_match_personal_stats(client: AsyncClient) -> None:
    admin, _ = await create_admin_headers(client, "stats")
    user = await register_user(client, "stats_target")
    await create_practice_data(client, admin, user)

    personal = await client.get("/api/v1/stats/overview", headers=user["headers"])
    admin_view = await client.get(
        f"/api/v1/admin/users/{user['id']}/stats",
        headers=admin,
    )
    missing = await client.get("/api/v1/admin/users/999999999/stats", headers=admin)

    assert admin_view.status_code == 200
    assert admin_view.json()["data"] == personal.json()["data"]
    assert admin_view.json()["data"]["total_practiced"] == 1
    assert missing.status_code == 404
    assert missing.json()["code"] == 40401
