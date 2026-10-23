import asyncio
import io
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.import_job import ImportJob
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import Wordbook
from httpx import AsyncClient
from openpyxl import Workbook
from scripts.create_admin import seed_admin
from sqlalchemy import delete, select

PREFIX = "pytest_import_"
ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass123!"


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
        if wordbook_ids:
            await session.execute(delete(ImportJob).where(ImportJob.wordbook_id.in_(wordbook_ids)))
            await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
            await session.execute(delete(Wordbook).where(Wordbook.id.in_(wordbook_ids)))
        if user_ids:
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_imports() -> AsyncIterator[None]:
    await clean_test_data()
    yield
    await clean_test_data()


async def create_admin(client: AsyncClient, label: str) -> dict[str, str]:
    username = make_name(f"admin_{label}")
    async with async_session_factory() as session:
        await seed_admin(session, username, f"{username}@example.com", ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def create_wordbook(client: AsyncClient, admin: dict[str, str], label: str) -> int:
    response = await client.post(
        "/api/v1/admin/wordbooks",
        headers=admin,
        json={"name": make_name(label), "status": "draft"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


async def wait_for_job(client: AsyncClient, admin: dict[str, str], job_id: int) -> dict:
    for _attempt in range(50):
        response = await client.get(f"/api/v1/admin/import-jobs/{job_id}", headers=admin)
        assert response.status_code == 200
        data = response.json()["data"]
        if data["status"] in {"done", "failed"}:
            return data
        await asyncio.sleep(0.05)
    raise AssertionError("import job did not finish")


async def test_import_permissions_and_missing_resources(client: AsyncClient) -> None:
    username = make_name("user")
    registered = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": USER_PASSWORD},
    )
    assert registered.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    user_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    file = {"file": ("words.csv", b"spelling\napple\n", "text/csv")}

    unauthenticated = await client.post("/api/v1/admin/wordbooks/1/import/preview", files=file)
    forbidden = await client.post(
        "/api/v1/admin/wordbooks/1/import/preview",
        headers=user_headers,
        files=file,
    )
    missing_job = await client.get("/api/v1/admin/import-jobs/999999999", headers=user_headers)

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == 40101
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == 40301
    assert missing_job.status_code == 403


async def test_preview_csv_and_missing_wordbook(client: AsyncClient) -> None:
    admin = await create_admin(client, "preview")
    wordbook_id = await create_wordbook(client, admin, "preview")
    content = "spelling,meaning_cn\napple,苹果\nbanana,香蕉\n".encode()

    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import/preview",
        headers=admin,
        files={"file": ("words.csv", content, "text/csv")},
    )
    missing = await client.post(
        "/api/v1/admin/wordbooks/999999999/import/preview",
        headers=admin,
        files={"file": ("words.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["headers"] == ["spelling", "meaning_cn"]
    assert data["rows"] == [["apple", "苹果"], ["banana", "香蕉"]]
    assert data["total_rows"] == 2
    assert missing.status_code == 404
    assert missing.json()["code"] == 40401


async def test_preview_xlsx(client: AsyncClient) -> None:
    admin = await create_admin(client, "xlsx")
    wordbook_id = await create_wordbook(client, admin, "xlsx")
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Words"
    worksheet.append(["spelling", "meaning_cn", "sort_order"])
    worksheet.append(["apple", "苹果", 1])
    worksheet.append(["banana", "香蕉", 2])
    content = io.BytesIO()
    workbook.save(content)
    workbook.close()

    response = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import/preview",
        headers=admin,
        files={
            "file": (
                "words.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sheet_name"] == "Words"
    assert data["headers"] == ["spelling", "meaning_cn", "sort_order"]
    assert data["rows"] == [["apple", "苹果", "1"], ["banana", "香蕉", "2"]]
    assert data["total_rows"] == 2


async def test_import_partial_success_and_error_details(client: AsyncClient) -> None:
    admin = await create_admin(client, "partial")
    wordbook_id = await create_wordbook(client, admin, "partial")
    content = ("spelling,meaning_cn\nalpha,阿尔法\n,空拼写\nalpha,重复\nbeta,贝塔\n").encode()

    created = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import",
        headers=admin,
        data={"mapping": json.dumps({"spelling": "0", "meaning_cn": "1"})},
        files={"file": ("words.csv", content, "text/csv")},
    )

    assert created.status_code == 202
    job = await wait_for_job(client, admin, created.json()["data"]["import_job_id"])
    words = await client.get(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=admin,
    )

    assert job["status"] == "done"
    assert job["total_rows"] == 4
    assert job["success_rows"] == 2
    assert job["failed_rows"] == 2
    assert [item["row"] for item in job["errors"]] == [3, 4]
    assert [item["spelling"] for item in words.json()["data"]["items"]] == ["alpha", "beta"]


async def test_import_validation_and_existing_duplicate(client: AsyncClient) -> None:
    admin = await create_admin(client, "validate")
    wordbook_id = await create_wordbook(client, admin, "validate")
    existing = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/words",
        headers=admin,
        json={"spelling": "alpha"},
    )
    assert existing.status_code == 201

    invalid_mapping = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import",
        headers=admin,
        data={"mapping": json.dumps({"meaning_cn": "0"})},
        files={"file": ("words.csv", b"meaning\napple\n", "text/csv")},
    )
    unsupported = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import/preview",
        headers=admin,
        files={"file": ("words.xls", b"not-excel", "application/vnd.ms-excel")},
    )
    created = await client.post(
        f"/api/v1/admin/wordbooks/{wordbook_id}/import",
        headers=admin,
        data={"mapping": json.dumps({"spelling": "0"})},
        files={"file": ("words.csv", b"spelling\nalpha\nbeta\n", "text/csv")},
    )
    job = await wait_for_job(client, admin, created.json()["data"]["import_job_id"])

    assert invalid_mapping.status_code == 422
    assert invalid_mapping.json()["code"] == 42201
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == 42201
    assert job["success_rows"] == 1
    assert job["failed_rows"] == 1
    assert job["errors"][0]["reason"] == "同词书内 spelling 已存在"
