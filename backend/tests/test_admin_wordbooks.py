from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, func, select

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


def make_suffix(label: str) -> str:
    return f"pytest_wb_{label}_{uuid4().hex[:10]}"


async def clean_wordbook_data() -> None:
    async with async_session_factory() as session:
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_wb_%"))
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_wb_admin_%")))
        await session.execute(delete(User).where(User.username.like("pytest_wb_user_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_wordbooks() -> AsyncIterator[None]:
    await clean_wordbook_data()
    yield
    await clean_wordbook_data()


async def create_admin_headers(client: AsyncClient, label: str) -> dict[str, str]:
    name = make_suffix(f"admin_{label}")
    identity = {"username": name, "email": f"{name}@example.com", "password": ADMIN_PASSWORD}
    async with async_session_factory() as session:
        await seed_admin(session, identity["username"], identity["email"], ADMIN_PASSWORD)

    response = await client.post(
        "/api/v1/auth/login",
        json={"account": identity["username"], "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def create_wordbook(
    client: AsyncClient,
    headers: dict[str, str],
    label: str,
    status_value: str = "draft",
) -> dict:
    response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=headers,
        json={
            "name": make_suffix(label),
            "description": "test wordbook",
            "level": "CET4",
            "status": status_value,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def add_word(wordbook_id: int, spelling: str) -> None:
    async with async_session_factory() as session:
        session.add(Word(wordbook_id=wordbook_id, spelling=spelling))
        await session.commit()


async def test_create_wordbook_success(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "create")
    wordbook = await create_wordbook(client, headers, "create")

    assert wordbook["name"].startswith("pytest_wb_create")
    assert wordbook["status"] == "draft"
    assert wordbook["created_by"]


async def test_normal_user_cannot_access_admin_wordbooks(client: AsyncClient) -> None:
    username = make_suffix("user_normal")
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": USER_PASSWORD},
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    token = login_response.json()["data"]["access_token"]

    response = await client.get(
        "/api/v1/admin/wordbooks",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == 40301


async def test_update_wordbook_status(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "update")
    wordbook = await create_wordbook(client, headers, "update")

    response = await client.put(
        f"/api/v1/admin/wordbooks/{wordbook['id']}",
        headers=headers,
        json={"status": "published"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "published"


async def test_delete_wordbook_with_words_requires_force(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "delete_conflict")
    wordbook = await create_wordbook(client, headers, "delete_conflict")
    await add_word(wordbook["id"], "conflict")

    response = await client.delete(
        f"/api/v1/admin/wordbooks/{wordbook['id']}",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == 40901


async def test_force_delete_wordbook_with_words(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "delete_force")
    wordbook = await create_wordbook(client, headers, "delete_force")
    await add_word(wordbook["id"], "force")

    response = await client.delete(
        f"/api/v1/admin/wordbooks/{wordbook['id']}?force=true",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}

    async with async_session_factory() as session:
        word_count = await session.scalar(
            select(func.count(Word.id)).where(Word.wordbook_id == wordbook["id"]),
        )
        assert word_count == 0


async def test_list_wordbooks_returns_word_count(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "list")
    wordbook = await create_wordbook(client, headers, "list")
    await add_word(wordbook["id"], "listed")

    response = await client.get(
        "/api/v1/admin/wordbooks?page=1&page_size=20",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    item = next(item for item in body["items"] if item["id"] == wordbook["id"])
    assert item["word_count"] == 1
    assert item["status"] == "draft"
    assert body["page"] == 1
    assert body["page_size"] == 20
