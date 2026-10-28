from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


async def clean_word_data() -> None:
    async with async_session_factory() as session:
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_word_wb_%"))
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_word_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_word_admin_%")))
        await session.execute(delete(User).where(User.username.like("pytest_word_user_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_words() -> AsyncIterator[None]:
    await clean_word_data()
    yield
    await clean_word_data()


async def create_admin_headers(client: AsyncClient, label: str) -> dict[str, str]:
    username = f"pytest_word_admin_{label}_{uuid4().hex[:10]}"
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)

    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def create_wordbook(client: AsyncClient, headers: dict[str, str], label: str) -> int:
    response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=headers,
        json={"name": f"pytest_word_wb_{label}_{uuid4().hex[:10]}", "status": "published"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


async def create_word(
    client: AsyncClient,
    headers: dict[str, str],
    wordbook_id: int,
    spelling: str,
    **extra: object,
) -> dict:
    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=headers,
        json={"spelling": spelling, "sort_order": 1, **extra},
    )
    assert response.status_code == 201
    return response.json()["data"]


async def test_create_word_success(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "create")
    wordbook_id = await create_wordbook(client, headers, "create")

    word = await create_word(
        client,
        headers,
        wordbook_id,
        "hello",
        phonetic_uk="/həˈləʊ/",
        meaning_cn="你好",
        part_of_speech="int.",
    )

    assert word["wordbook_id"] == wordbook_id
    assert word["spelling"] == "hello"
    assert word["sort_order"] == 1


async def test_duplicate_spelling_in_same_wordbook_returns_40901(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "duplicate")
    wordbook_id = await create_wordbook(client, headers, "duplicate")
    await create_word(client, headers, wordbook_id, "hello")

    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=headers,
        json={"spelling": "hello"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == 40901


async def test_same_spelling_in_different_wordbooks_succeeds(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "different")
    first_id = await create_wordbook(client, headers, "first")
    second_id = await create_wordbook(client, headers, "second")

    first = await create_word(client, headers, first_id, "same")
    second = await create_word(client, headers, second_id, "same")

    assert first["id"] != second["id"]
    assert first["wordbook_id"] != second["wordbook_id"]


async def test_update_word_fields(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "update")
    wordbook_id = await create_wordbook(client, headers, "update")
    word = await create_word(client, headers, wordbook_id, "hello")

    response = await client.put(
        f"/api/v1/admin/words/{word['id']}",
        headers=headers,
        json={
            "spelling": "hello world",
            "meaning_cn": "你好世界",
            "example_en": "Hello world.",
            "sort_order": 9,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["spelling"] == "hello world"
    assert body["meaning_cn"] == "你好世界"
    assert body["example_en"] == "Hello world."
    assert body["sort_order"] == 9


async def test_delete_word_success(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "delete")
    wordbook_id = await create_wordbook(client, headers, "delete")
    word = await create_word(client, headers, wordbook_id, "delete-me")

    response = await client.delete(f"/api/v1/admin/words/{word['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}
    async with async_session_factory() as session:
        stored = await session.scalar(select(Word).where(Word.id == word["id"]))
        assert stored is None


async def test_wordbook_not_found_returns_40401(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "missing_book")

    response = await client.post(
        "/api/v1/admin/wordbooks/999999999/words",
        headers=headers,
        json={"spelling": "missing"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == 40401


async def test_normal_user_cannot_access_admin_words(client: AsyncClient) -> None:
    username = f"pytest_word_user_{uuid4().hex[:10]}"
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
        "/api/v1/admin/wordbooks/1/words",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == 40301


async def test_list_words_with_keyword_and_pagination(client: AsyncClient) -> None:
    headers = await create_admin_headers(client, "search")
    wordbook_id = await create_wordbook(client, headers, "search")
    await create_word(client, headers, wordbook_id, "alpha")
    await create_word(client, headers, wordbook_id, "alphabet")
    await create_word(client, headers, wordbook_id, "beta")

    response = await client.get(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words?page=1&page_size=20&keyword=alpha",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 2
    assert [item["spelling"] for item in body["items"]] == ["alpha", "alphabet"]
    assert body["page"] == 1
    assert body["page_size"] == 20
