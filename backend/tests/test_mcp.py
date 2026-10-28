import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.exception_handlers import AppError
from app.db.session import async_session_factory
from app.mcp.auth import McpAuthMiddleware
from app.mcp.server import create_mcp_server
from app.models.import_job import ImportJob
from app.models.mcp import McpAuditLog, McpChangeRequest
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook
from app.services.mcp_change import create_change_request, store_import_upload
from httpx import ASGITransport, AsyncClient
from scripts.create_admin import seed_admin
from sqlalchemy import delete, func, select, update

from tests.practice_answer_helpers import create_user, create_wordbook

ADMIN_PASSWORD = "AdminPass123!"


async def make_admin(
    client: AsyncClient,
    label: str,
) -> tuple[dict[str, str], int]:
    username = f"pytest_answer_admin_mcp_{label}_{uuid4().hex[:10]}"
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
        admin = await session.scalar(select(User).where(User.username == username))
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}, admin.id


async def propose(admin_id: int, **kwargs) -> int:
    async with async_session_factory() as session:
        request = await create_change_request(session, admin_id=admin_id, **kwargs)
        return request.id


async def test_approve_word_create_executes_and_audits(client: AsyncClient) -> None:
    admin, admin_id = await make_admin(client, "approve")
    wordbook_id = await create_wordbook(client, admin, "mcp_approve")
    request_id = await propose(
        admin_id,
        action_type="word.create",
        payload={"wordbook_id": wordbook_id, "spelling": "apple", "meaning_cn": "苹果"},
        reason="补充示例单词",
    )

    response = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "executed"
    assert data["result"]["word_id"] > 0

    async with async_session_factory() as session:
        word = await session.scalar(
            select(Word).where(Word.wordbook_id == wordbook_id, Word.spelling == "apple"),
        )
        assert word is not None
        assert word.meaning_cn == "苹果"
        audit_count = await session.scalar(
            select(func.count(McpAuditLog.id)).where(
                McpAuditLog.admin_id == admin_id,
                McpAuditLog.tool_name == "admin_approve_change",
            ),
        )
        assert audit_count == 1


async def test_reject_keeps_data_unchanged_and_blocks_later_approval(
    client: AsyncClient,
) -> None:
    admin, admin_id = await make_admin(client, "reject")
    name = f"pytest_answer_wb_mcp_reject_{uuid4().hex[:10]}"
    request_id = await propose(
        admin_id,
        action_type="wordbook.create",
        payload={"name": name},
    )

    response = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/reject",
        headers=admin,
        json={"reason": "暂不创建"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"

    async with async_session_factory() as session:
        assert await session.scalar(select(Wordbook).where(Wordbook.name == name)) is None

    approve = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )
    assert approve.status_code == 409
    assert approve.json()["code"] == 40901


async def test_duplicate_approval_is_rejected(client: AsyncClient) -> None:
    admin, admin_id = await make_admin(client, "duplicate")
    name = f"pytest_answer_wb_mcp_duplicate_{uuid4().hex[:10]}"
    request_id = await propose(
        admin_id,
        action_type="wordbook.create",
        payload={"name": name},
    )

    first = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )
    assert second.status_code == 409
    assert second.json()["code"] == 40901


async def test_expired_request_cannot_be_approved(client: AsyncClient) -> None:
    admin, admin_id = await make_admin(client, "expired")
    request_id = await propose(
        admin_id,
        action_type="user.status",
        payload={"user_id": 999_999_999, "status": "disabled"},
    )

    async with async_session_factory() as session:
        await session.execute(
            update(McpChangeRequest)
            .where(McpChangeRequest.id == request_id)
            .values(expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)),
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )
    assert response.status_code == 409
    async with async_session_factory() as session:
        request = await session.get(McpChangeRequest, request_id)
        assert request.status == "expired"


async def test_import_approval_runs_background_job(client: AsyncClient) -> None:
    admin, admin_id = await make_admin(client, "import")
    wordbook_id = await create_wordbook(client, admin, "mcp_import")
    content = "spelling,meaning_cn\nhello,你好\nworld,世界\n".encode()

    async with async_session_factory() as session:
        upload = await store_import_upload(
            session,
            admin_id=admin_id,
            file_name="words.csv",
            content=content,
        )
        upload_id = upload.id
    request_id = await propose(
        admin_id,
        action_type="word.import",
        payload={
            "wordbook_id": wordbook_id,
            "upload_id": upload_id,
            "file_name": "words.csv",
            "mapping": {"spelling": 0, "meaning_cn": 1},
        },
    )

    response = await client.post(
        f"/api/v1/admin/mcp-changes/{request_id}/approve",
        headers=admin,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "executed"
    job_id = data["result"]["import_job_id"]

    job = None
    for _ in range(40):
        async with async_session_factory() as session:
            job = await session.get(ImportJob, job_id)
            if job is not None and job.status in ("done", "failed"):
                break
        await asyncio.sleep(0.05)

    assert job is not None
    assert job.status == "done"
    assert job.success_rows == 2

    async with async_session_factory() as session:
        word_count = await session.scalar(
            select(func.count(Word.id)).where(Word.wordbook_id == wordbook_id),
        )
        assert word_count == 2


async def test_mcp_middleware_requires_admin(client: AsyncClient) -> None:
    async def dummy_app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    transport = ASGITransport(app=McpAuthMiddleware(dummy_app))
    async with AsyncClient(transport=transport, base_url="http://testserver") as mcp_client:
        anonymous = await mcp_client.post("/mcp")
        assert anonymous.status_code == 401
        assert anonymous.headers["www-authenticate"] == "Bearer"

        user_headers, _user_id = await create_user(client, "mcp_auth")
        forbidden = await mcp_client.post("/mcp", headers=user_headers)
        assert forbidden.status_code == 403

        admin_headers, _admin_id = await make_admin(client, "auth")
        allowed = await mcp_client.post("/mcp", headers=admin_headers)
        assert allowed.status_code == 200


async def test_tool_catalog_has_no_password_reset() -> None:
    server = create_mcp_server()
    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert "propose_word_create" in names
    assert "propose_import" in names
    assert "reset_password" not in names
    assert "admin_approve_change" not in names


async def test_invalid_action_is_rejected(client: AsyncClient) -> None:
    _admin, admin_id = await make_admin(client, "invalid")

    async with async_session_factory() as session:
        with pytest.raises(AppError) as excinfo:
            await create_change_request(
                session,
                admin_id=admin_id,
                action_type="user.reset_password",
                payload={"user_id": 1},
            )
    assert "不支持的变更类型" in excinfo.value.message


@pytest.fixture(autouse=True)
async def cleanup_mcp_data() -> AsyncIterator[None]:
    async with async_session_factory() as session:
        await session.execute(delete(McpAuditLog))
        await session.execute(delete(McpChangeRequest))
        await session.commit()
    yield
    async with async_session_factory() as session:
        await session.execute(delete(McpAuditLog))
        await session.execute(delete(McpChangeRequest))
        await session.commit()
