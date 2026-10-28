import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from app.core.exception_handlers import AppError
from app.db.session import async_session_factory
from app.mcp.auth import McpAuthMiddleware, authenticate_admin
from app.models.mcp import McpAccessToken
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from tests.practice_answer_helpers import create_admin, create_user


async def create_client_token(
    client: AsyncClient,
    admin: dict[str, str],
    *,
    scopes: str = "read",
    expires_in_days: int | None = 90,
) -> dict:
    response = await client.post(
        "/api/v1/admin/mcp-tokens",
        headers=admin,
        json={
            "name": f"pytest_answer_mcp_token_{scopes}",
            "scopes": scopes,
            "expires_in_days": expires_in_days,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_create_token_returns_raw_once_and_stores_hash(client: AsyncClient) -> None:
    admin = await create_admin(client, "mcp_token_create")
    created = await create_client_token(client, admin, scopes="write")

    raw_token = created["token"]
    assert raw_token.startswith("mcp_")
    assert created["token_prefix"] == raw_token[:12]
    assert created["endpoint"].endswith("/mcp")

    listing = await client.get("/api/v1/admin/mcp-tokens", headers=admin)
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert "token" not in items[0]
    assert items[0]["token_prefix"] == raw_token[:12]

    async with async_session_factory() as session:
        token = await session.scalar(
            select(McpAccessToken).where(McpAccessToken.id == created["id"]),
        )
        assert token is not None
        assert token.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        assert token.token_hash != raw_token


async def test_client_token_authenticates_middleware(client: AsyncClient) -> None:
    admin = await create_admin(client, "mcp_token_auth")
    created = await create_client_token(client, admin, scopes="read")

    async def dummy_app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    transport = ASGITransport(app=McpAuthMiddleware(dummy_app))
    async with AsyncClient(transport=transport, base_url="http://testserver") as mcp_client:
        allowed = await mcp_client.post("/mcp", headers=bearer(created["token"]))
        assert allowed.status_code == 200

        missing = await mcp_client.post("/mcp")
        assert missing.status_code == 401

        revoked = await client.post(
            f"/api/v1/admin/mcp-tokens/{created['id']}/revoke",
            headers=admin,
        )
        assert revoked.status_code == 200

        denied = await mcp_client.post("/mcp", headers=bearer(created["token"]))
        assert denied.status_code == 401


async def test_token_scope_controls_write_permission(client: AsyncClient) -> None:
    admin = await create_admin(client, "mcp_token_scope")
    read_token = await create_client_token(client, admin, scopes="read")
    write_token = await create_client_token(client, admin, scopes="write")

    read_principal = await authenticate_admin(bearer(read_token["token"]))
    write_principal = await authenticate_admin(bearer(write_token["token"]))

    assert read_principal.can_write is False
    assert write_principal.can_write is True
    assert read_principal.id == write_principal.id


async def test_expired_and_revoked_tokens_are_rejected(client: AsyncClient) -> None:
    admin = await create_admin(client, "mcp_token_expiry")
    expired = await create_client_token(client, admin, scopes="read")
    revoked = await create_client_token(client, admin, scopes="read")

    async with async_session_factory() as session:
        await session.execute(
            update(McpAccessToken)
            .where(McpAccessToken.id == expired["id"])
            .values(expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)),
        )
        await session.commit()

    with pytest.raises(AppError) as expired_error:
        await authenticate_admin(bearer(expired["token"]))
    assert expired_error.value.status_code == 401

    response = await client.post(
        f"/api/v1/admin/mcp-tokens/{revoked['id']}/revoke",
        headers=admin,
    )
    assert response.status_code == 200
    second = await client.post(
        f"/api/v1/admin/mcp-tokens/{revoked['id']}/revoke",
        headers=admin,
    )
    assert second.status_code == 409

    with pytest.raises(AppError) as revoked_error:
        await authenticate_admin(bearer(revoked["token"]))
    assert revoked_error.value.status_code == 401


async def test_token_management_requires_admin(client: AsyncClient) -> None:
    user_headers, _user_id = await create_user(client, "mcp_token_user")
    response = await client.post(
        "/api/v1/admin/mcp-tokens",
        headers=user_headers,
        json={"name": "nope", "scopes": "read"},
    )
    assert response.status_code == 403

    listing = await client.get("/api/v1/admin/mcp-tokens", headers=user_headers)
    assert listing.status_code == 403
