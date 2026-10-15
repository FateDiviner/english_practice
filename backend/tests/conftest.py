"""测试夹具：隔离数据库与全局状态。

必须在导入任何 app.* 模块之前设置 DATABASE_URL，
因为 app.db 在导入时即创建引擎。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="ep_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
# 未配置真实模型时走 Mock 流；测试中关闭打字机延迟以提速
os.environ.setdefault("AI_BASE_URL", "")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("AI_MODEL", "")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai import client as ai_client  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import practice_service  # noqa: E402
from scripts.init_db import seed_wordbooks  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """建表并导入内置词书，整个测试会话共用一套数据。"""
    init_db()
    seed_wordbooks()


@pytest.fixture(autouse=True)
def _fast_mock_stream(monkeypatch: pytest.MonkeyPatch):
    """Mock 流式回复不加延迟，避免测试被逐字 sleep 拖慢。"""
    monkeypatch.setattr(ai_client, "MOCK_DELAY_MS", 0)
    yield


@pytest.fixture(autouse=True)
def _clean_sessions():
    """每个用例之间清空进程内练习会话。"""
    practice_service.clear_sessions()
    yield
    practice_service.clear_sessions()


@pytest.fixture()
def db():
    """提供独立数据库会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    """HTTP 客户端（自动管理上下文以触发 lifespan 初始化）。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    """已完成注册登录的客户端，附带合法 Authorization 头。"""
    username = f"tester_{os.getpid()}_{id(client)}"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
