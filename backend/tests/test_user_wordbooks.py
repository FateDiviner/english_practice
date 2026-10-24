from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wordbook import Wordbook
from httpx import AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


def make_suffix(label: str) -> str:
    return f"pytest_uw_{label}_{uuid4().hex[:10]}"


async def clean_user_wordbook_data() -> None:
    async with async_session_factory() as session:
        user_ids = select(User.id).where(User.username.like("pytest_uw_user_%"))
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_uw_wb_%"))
        word_ids = select(Word.id).where(Word.wordbook_id.in_(wordbook_ids))
        await session.execute(
            delete(WordProgress).where(
                (WordProgress.user_id.in_(user_ids)) | (WordProgress.word_id.in_(word_ids))
            )
        )
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_uw_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_uw_admin_%")))
        await session.execute(delete(User).where(User.username.like("pytest_uw_user_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_user_wordbooks() -> AsyncIterator[None]:
    await clean_user_wordbook_data()
    yield
    await clean_user_wordbook_data()


async def admin_headers(client: AsyncClient, label: str) -> dict[str, str]:
    username = f"pytest_uw_admin_{label}_{uuid4().hex[:10]}"
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def user_headers(client: AsyncClient, label: str) -> dict[str, str]:
    username = f"pytest_uw_user_{label}_{uuid4().hex[:10]}"
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


async def user_identity(
    client: AsyncClient, label: str
) -> tuple[dict[str, str], int]:
    headers = await user_headers(client, label)
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["data"]["id"]


async def set_progress(user_id: int, word_id: int, mastery_level: int) -> None:
    async with async_session_factory() as session:
        session.add(
            WordProgress(
                user_id=user_id,
                word_id=word_id,
                mastery_level=mastery_level,
            )
        )
        await session.commit()


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
            "name": f"pytest_uw_wb_{label}_{uuid4().hex[:10]}",
            "description": f"{label} description",
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
        json={"spelling": spelling, "meaning_cn": spelling, "sort_order": 1},
    )
    assert response.status_code == 201
    return response.json()["data"]


async def test_user_wordbooks_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/v1/wordbooks")

    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_user_only_sees_published_wordbooks(client: AsyncClient) -> None:
    admin = await admin_headers(client, "visibility")
    published = await create_wordbook(client, admin, "published", "published")
    draft = await create_wordbook(client, admin, "draft", "draft")
    archived = await create_wordbook(client, admin, "archived", "archived")
    user = await user_headers(client, "visibility")

    response = await client.get("/api/v1/wordbooks?page=1&page_size=100", headers=user)

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    ids = {item["id"] for item in items}
    assert published["id"] in ids
    assert draft["id"] not in ids
    assert archived["id"] not in ids
    published_item = next(item for item in items if item["id"] == published["id"])
    assert published_item["my_progress"] == {"mastered": 0, "total": 0}


async def test_non_published_wordbook_detail_returns_40401(client: AsyncClient) -> None:
    admin = await admin_headers(client, "detail")
    draft = await create_wordbook(client, admin, "draft_detail", "draft")
    archived = await create_wordbook(client, admin, "archived_detail", "archived")
    user = await user_headers(client, "detail")

    for wordbook_id in (draft["id"], archived["id"], 999999999):
        response = await client.get(f"/api/v1/wordbooks/{wordbook_id}", headers=user)
        assert response.status_code == 404
        assert response.json()["code"] == 40401


async def test_wordbook_list_pagination(client: AsyncClient) -> None:
    admin = await admin_headers(client, "pagination")
    first = await create_wordbook(client, admin, "page_first", "published")
    second = await create_wordbook(client, admin, "page_second", "published")
    user = await user_headers(client, "pagination")

    response = await client.get("/api/v1/wordbooks?page=1&page_size=1", headers=user)

    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["items"]) == 1
    assert body["total"] >= 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["items"][0]["id"] in {first["id"], second["id"]}


async def test_wordbook_list_returns_user_mastered_progress(client: AsyncClient) -> None:
    admin = await admin_headers(client, "progress")
    wordbook = await create_wordbook(client, admin, "progress", "published")
    alpha = await create_word(client, admin, wordbook["id"], "alpha")
    beta = await create_word(client, admin, wordbook["id"], "beta")
    gamma = await create_word(client, admin, wordbook["id"], "gamma")
    user, user_id = await user_identity(client, "progress")
    await set_progress(user_id, alpha["id"], 2)
    await set_progress(user_id, beta["id"], 2)
    await set_progress(user_id, gamma["id"], 1)

    other, other_id = await user_identity(client, "progress_other")
    await set_progress(other_id, gamma["id"], 2)

    response = await client.get("/api/v1/wordbooks?page=1&page_size=100", headers=user)
    assert response.status_code == 200
    item = next(
        entry
        for entry in response.json()["data"]["items"]
        if entry["id"] == wordbook["id"]
    )
    assert item["my_progress"] == {"mastered": 2, "total": 3}

    other_response = await client.get(
        "/api/v1/wordbooks?page=1&page_size=100", headers=other
    )
    other_item = next(
        entry
        for entry in other_response.json()["data"]["items"]
        if entry["id"] == wordbook["id"]
    )
    assert other_item["my_progress"] == {"mastered": 1, "total": 3}


async def test_wordbook_words_return_mastery_and_filter(client: AsyncClient) -> None:
    admin = await admin_headers(client, "words_mastery")
    wordbook = await create_wordbook(client, admin, "words_mastery", "published")
    alpha = await create_word(client, admin, wordbook["id"], "alpha")
    beta = await create_word(client, admin, wordbook["id"], "beta")
    gamma = await create_word(client, admin, wordbook["id"], "gamma")
    user, user_id = await user_identity(client, "words_mastery")
    await set_progress(user_id, alpha["id"], 2)
    await set_progress(user_id, beta["id"], 1)
    assert gamma["spelling"] == "gamma"

    response = await client.get(
        f"/api/v1/wordbooks/{wordbook['id']}/words?page=1&page_size=10",
        headers=user,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    levels = {item["spelling"]: item["mastery_level"] for item in body["items"]}
    assert levels == {"alpha": 2, "beta": 1, "gamma": 0}
    assert body["total"] == 3

    mastered = await client.get(
        f"/api/v1/wordbooks/{wordbook['id']}/words?page=1&page_size=10&mastery=2",
        headers=user,
    )
    assert mastered.status_code == 200
    mastered_body = mastered.json()["data"]
    assert mastered_body["total"] == 1
    assert mastered_body["items"][0]["spelling"] == "alpha"

    new_words = await client.get(
        f"/api/v1/wordbooks/{wordbook['id']}/words?page=1&page_size=10&mastery=0",
        headers=user,
    )
    assert new_words.json()["data"]["total"] == 1
    assert new_words.json()["data"]["items"][0]["spelling"] == "gamma"

    paginated = await client.get(
        f"/api/v1/wordbooks/{wordbook['id']}/words?page=1&page_size=2",
        headers=user,
    )
    assert paginated.json()["data"]["total"] == 3
    assert len(paginated.json()["data"]["items"]) == 2
