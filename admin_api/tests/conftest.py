"""管理端测试夹具：独立数据库与可预期的邀请码策略。

必须在导入 core.* 之前设置环境变量——core.config 在模块导入时就固定了
.env 的解析结果，晚一步设置就再也读不到。
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="ep_admin_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'admin_test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key-for-admin-pytest-only"
# 默认关闭邀请码，测「首个管理员」规则；需要测邀请码时由用例自行改写缓存
os.environ["ADMIN_INVITE_CODE"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.config import get_settings  # noqa: E402
from core.db import SessionLocal, init_db  # noqa: E402
from core.services.auth_service import create_user  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """建表；管理端与用户端共用 core.db，因此幂等补列在这里同样生效。"""
    init_db()


def unique(prefix: str) -> str:
    """用户名必须随机：用 id(obj) 生成会随对象地址复用而撞名 409。"""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


# 首个管理员只允许注册一次，之后所有用例都用同一套凭据登录复用
_ADMIN_CREDENTIALS: dict[str, str | None] = {"username": None, "password": "secret123"}
ADMIN_ROLE = "admin"


@pytest.fixture()
def admin(client: TestClient) -> dict:
    """系统里的第一个管理员。

    首次调用走公开注册口创建（这本身就验证了「首个管理员可开放注册」），
    之后改为登录复用——否则注册口的 409 规则会让每个用例都挂在 setup 上。
    """
    creds = _ADMIN_CREDENTIALS

    def _login(username: str) -> dict:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": username, "password": creds["password"]},
        )
        assert response.status_code == 200, response.text
        return response.json()

    if creds["username"] is not None:
        payload = _login(creds["username"])
    else:
        username = unique("root")
        response = client.post(
            "/api/admin/auth/register",
            json={"username": username, "password": creds["password"]},
        )
        if response.status_code == 200:
            payload = response.json()
        else:
            # 注册口已被占位（首个管理员规则生效）：直接落库造一个再登录。
            # 否则依赖本夹具的用例会因为执行顺序不同而随机挂在 setup 上。
            with SessionLocal() as session:
                user = create_user(session, username, creds["password"])
                user.role = ADMIN_ROLE
                session.commit()
            payload = _login(username)
        creds["username"] = username

    return {
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        "username": payload["user"]["username"],
        "user_id": payload["user"]["id"],
    }


@pytest.fixture()
def member(client: TestClient, admin: dict) -> dict:
    """由管理员代建的普通用户，返回其登录令牌。"""
    username = unique("user")
    created = client.post(
        "/api/admin/users",
        json={"username": username, "password": "secret123", "role": "user"},
        headers=admin["headers"],
    )
    assert created.status_code == 200, created.text

    login = client.post(
        "/api/admin/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "username": username,
        "user_id": login.json()["user"]["id"],
    }


@pytest.fixture(autouse=True)
def _reset_invite_code():
    """用例改过邀请码后必须还原，否则会污染后续用例。"""
    yield
    get_settings.cache_clear()
    os.environ["ADMIN_INVITE_CODE"] = ""
