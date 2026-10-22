from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import delete, select

PASSWORD = "ValidPass123!"


def make_identity(label: str) -> dict[str, str]:
    suffix = uuid4().hex[:12]
    username = f"pytest_auth_{label}_{suffix}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD,
    }


async def clean_auth_users() -> None:
    async with async_session_factory() as session:
        await session.execute(delete(User).where(User.username.like("pytest_auth_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_auth_users() -> AsyncIterator[None]:
    await clean_auth_users()
    yield
    await clean_auth_users()


async def register(client: AsyncClient, identity: dict[str, str]) -> dict:
    response = await client.post("/api/v1/auth/register", json=identity)
    assert response.status_code == 201
    return response.json()["data"]


async def login(client: AsyncClient, account: str, password: str = PASSWORD) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def test_register_success(client: AsyncClient) -> None:
    identity = make_identity("register")
    response = await client.post("/api/v1/auth/register", json=identity)

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["username"] == identity["username"]
    assert body["data"]["email"] == identity["email"]
    assert body["data"]["role"] == "user"
    assert body["data"]["status"] == "active"
    assert "password" not in body["data"]
    assert "password_hash" not in body["data"]


async def test_duplicate_register_returns_409(client: AsyncClient) -> None:
    identity = make_identity("duplicate")
    await register(client, identity)
    duplicate = {**identity, "email": f"other_{identity['email']}"}

    response = await client.post("/api/v1/auth/register", json=duplicate)

    assert response.status_code == 409
    assert response.json()["code"] == 40901


async def test_username_cannot_equal_another_users_email(client: AsyncClient) -> None:
    first = make_identity("cross_first")
    first_data = await register(client, first)
    second = make_identity("cross_second")
    second["username"] = first_data["email"]

    response = await client.post("/api/v1/auth/register", json=second)

    assert response.status_code == 409
    assert response.json()["code"] == 40901


async def test_login_by_username_and_email(client: AsyncClient) -> None:
    identity = make_identity("login")
    await register(client, identity)

    username_login = await login(client, identity["username"])
    email_login = await login(client, identity["email"])

    for token_data in (username_login, email_login):
        assert token_data["token_type"] == "bearer"
        assert token_data["access_token"]
        assert token_data["user"]["username"] == identity["username"]


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    identity = make_identity("wrong_password")
    await register(client, identity)

    response = await client.post(
        "/api/v1/auth/login",
        json={"account": identity["username"], "password": "WrongPass123!"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_disabled_user_cannot_login(client: AsyncClient) -> None:
    identity = make_identity("disabled")
    user = await register(client, identity)

    async with async_session_factory() as session:
        stored_user = await session.scalar(select(User).where(User.id == user["id"]))
        assert stored_user is not None
        stored_user.status = "disabled"
        await session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"account": identity["username"], "password": PASSWORD},
    )

    assert response.status_code == 403
    assert response.json()["code"] == 40301


async def test_me_with_token_returns_current_user(client: AsyncClient) -> None:
    identity = make_identity("me")
    await register(client, identity)
    token_data = await login(client, identity["username"])

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["username"] == identity["username"]


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == 40101
