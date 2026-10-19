"""测试夹具：隔离数据库与全局状态。

必须在导入任何 app.* 模块之前设置 DATABASE_URL，
因为 app.db 在导入时即创建引擎。

数据库选择：
- 默认使用临时 SQLite，零配置即可跑完整套测试。
- 设置 ``RUN_MYSQL_TESTS=1`` 则改跑真实 MySQL：
  连接串由 user/backend/.env 的 DATABASE_URL 自动改写库名为 ``<库名>_test``，
  凭证只在进程内读取，绝不出现在命令行或日志里；
  且强制要求目标库名含 "test"，防止 drop_all 误清生产数据。
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_USE_EXTERNAL_DB = os.environ.pop("RUN_MYSQL_TESTS", "") == "1"

if _USE_EXTERNAL_DB:
    from core.config import get_settings as _get_settings  # 需在改写前读取 .env

    from sqlalchemy.engine import make_url as _make_url

    _source = _get_settings().database_url
    _url = _make_url(_source)
    # 交由 SQLAlchemy 解析与回填，避免手工切串在 mysql+pymysql:// 这类
    # 含双斜杠与方言前缀的 URL 上丢字符
    _test_name = (
        _url.database if (_url.database or "").endswith("_test")
        else (_url.database or "english_practice") + "_test"
    )
    if "test" not in _test_name:
        raise RuntimeError(
            f"测试库名 {_test_name!r} 必须包含 'test'，以免清空真实数据"
        )
    # 仅写入进程环境变量，不打印、不进入命令行参数
    os.environ["DATABASE_URL"] = _url.set(database=_test_name).render_as_string(
        hide_password=False
    )
    # get_settings 带 lru_cache，若不清理，后续 app.db 会继续用改写前的连接串
    _get_settings.cache_clear()
else:
    _TMP_DIR = tempfile.mkdtemp(prefix="ep_test_")
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"

# 测试一律强制走 Mock 流式（不可用 setdefault：.env 中的真实密钥会生效，
# 既让断言变得不确定，也可能消耗 API 额度）。真实模型走 scripts/ai_smoke.py。
os.environ["AI_BASE_URL"] = ""
os.environ["AI_API_KEY"] = ""
os.environ["AI_MODEL"] = ""
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai import client as ai_client  # noqa: E402
from core.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import practice_service  # noqa: E402
from scripts.init_db import seed_wordbooks  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """建表并导入内置词书，整个测试会话共用一套数据。

    外部库（MySQL）会先清空重建，保证每次运行从零开始。
    """
    if _USE_EXTERNAL_DB:
        from core.db import Base, engine

        # 硬断言：.env 一旦读不到会静默回退成 SQLite，「MySQL 上全绿」就是假的。
        # 这类回退必须当场炸掉，而不是让整套外部库验证变成摆设。
        assert engine.dialect.name == "mysql", (
            f"RUN_MYSQL_TESTS=1 但实际连的是 {engine.dialect.name}，.env 未被读取"
        )
        Base.metadata.drop_all(bind=engine)
        print("\n[测试库] 已清空外部数据库后重建表结构")
    init_db()
    seed_wordbooks()
    if _USE_EXTERNAL_DB:
        from sqlalchemy import func, select

        from core.models.word import Word

        with SessionLocal() as session:
            total = session.scalar(select(func.count(Word.id)))
        print(f"[测试库] 导入完成，共 {total} 词\n")


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
    username = f"tester_{os.getpid()}_{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
