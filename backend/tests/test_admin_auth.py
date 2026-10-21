"""角色模型、管理员鉴权与列回填的测试。

注册口会让首个注册用户成为管理员，因此本文件不依赖注册顺序，
一律用 _as_admin / _as_user 显式落定角色，避免用例之间互相干扰。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.constants import ROLE_ADMIN, ROLE_USER, USER_STATUS_ACTIVE, USER_STATUS_BANNED
from app.db import Base, SessionLocal, _ensure_columns
from app.models.user import User
from app.services import auth_service
from scripts.promote_admin import promote


def _register(client: TestClient, username: str, password: str = "secret123") -> dict:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _as_admin(db: Session, client: TestClient, username: str) -> dict:
    """注册一个账号并强制落成管理员，返回响应体。"""
    data = _register(client, username)
    user = db.get(User, data["user"]["id"])
    user.role = ROLE_ADMIN
    db.commit()
    return data


def _as_user(db: Session, client: TestClient, username: str) -> dict:
    """注册一个账号并强制落成普通用户，返回响应体。"""
    data = _register(client, username)
    user = db.get(User, data["user"]["id"])
    user.role = ROLE_USER
    db.commit()
    return data


def _clear_admins(db: Session) -> None:
    """把现有管理员全部临时降级，模拟「全新安装、库中无管理员」。

    不依赖用例执行顺序：无论本文件是否第一个跑、是否单独跑，结论都成立。
    """
    for admin in db.scalars(select(User).where(User.role == ROLE_ADMIN)).all():
        admin.role = ROLE_USER
    db.commit()


class TestFirstAdminBootstrap:
    def test_first_registration_becomes_admin(self, client: TestClient, db: Session) -> None:
        _clear_admins(db)
        assert not auth_service.has_admin(db)
        data = _register(client, "pioneer_one")
        assert data["user"]["role"] == ROLE_ADMIN

    def test_second_registration_is_plain_user(
        self, client: TestClient, db: Session
    ) -> None:
        _as_admin(db, client, "pioneer_two_admin")
        data = _register(client, "follower_two")
        assert data["user"]["role"] == ROLE_USER

    def test_guest_never_becomes_admin(self, client: TestClient, db: Session) -> None:
        _as_admin(db, client, "pioneer_three_admin")
        response = client.post("/api/auth/guest")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user"]["role"] == ROLE_USER
        assert body["user"]["is_guest"] is True

    def test_has_admin_ignores_guests(self, client: TestClient, db: Session) -> None:
        """只剩管理员游客时仍应判定为无管理员，否则系统会卡死在无人可管理。"""
        _clear_admins(db)
        guest = auth_service.create_guest(db)
        db.commit()
        assert guest.role == ROLE_USER
        assert not auth_service.has_admin(db)


class TestRequireAdmin:
    def test_admin_passes(self, client: TestClient, db: Session) -> None:
        data = _as_admin(db, client, "gate_admin_ok")
        user = db.get(User, data["user"]["id"])
        assert require_admin(user) is not None

    def test_plain_user_rejected(self, client: TestClient, db: Session) -> None:
        data = _as_user(db, client, "gate_user_no")
        user = db.get(User, data["user"]["id"])
        with pytest.raises(HTTPException) as excinfo:
            require_admin(user)
        assert excinfo.value.status_code == 403
        assert "管理员" in excinfo.value.detail

    def test_guest_rejected(self, client: TestClient, db: Session) -> None:
        response = client.post("/api/auth/guest")
        guest_id = response.json()["user"]["id"]
        user = db.get(User, guest_id)
        with pytest.raises(HTTPException) as excinfo:
            require_admin(user)
        assert excinfo.value.status_code == 403


class TestBannedUser:
    def test_banned_user_cannot_use_token(self, client: TestClient, db: Session) -> None:
        """封禁要让已有令牌立刻失效：JWT 无状态，靠每请求查库兜住。"""
        data = _as_user(db, client, "ban_target_one")
        token = data["access_token"]

        assert client.get("/api/auth/me", headers=_headers(token)).status_code == 200

        user = db.get(User, data["user"]["id"])
        user.status = USER_STATUS_BANNED
        db.commit()

        response = client.get("/api/auth/me", headers=_headers(token))
        assert response.status_code == 403
        assert "封禁" in response.json()["detail"]

    def test_active_user_unaffected(self, client: TestClient, db: Session) -> None:
        data = _as_user(db, client, "ban_target_two")
        user = db.get(User, data["user"]["id"])
        user.status = USER_STATUS_ACTIVE
        db.commit()
        response = client.get("/api/auth/me", headers=_headers(data["access_token"]))
        assert response.status_code == 200


class TestUserInfoExposesRole:
    def test_me_returns_role_and_status(self, client: TestClient, db: Session) -> None:
        data = _as_admin(db, client, "me_role_admin")
        response = client.get("/api/auth/me", headers=_headers(data["access_token"]))
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == ROLE_ADMIN
        assert body["status"] == USER_STATUS_ACTIVE

    def test_password_hash_never_leaked(self, client: TestClient, db: Session) -> None:
        data = _as_user(db, client, "me_no_leak")
        response = client.get("/api/auth/me", headers=_headers(data["access_token"]))
        assert "password_hash" not in response.json()


class TestPromoteScript:
    def test_promote_missing_user(self, db: Session) -> None:
        changed, message = promote("definitely_missing_user_xyz")
        assert changed is False
        assert "不存在" in message

    def test_promote_guest_rejected(self, client: TestClient) -> None:
        response = client.post("/api/auth/guest")
        guest_name = response.json()["user"]["username"]
        changed, message = promote(guest_name)
        assert changed is False
        assert "游客" in message

    def test_promote_plain_user(self, client: TestClient, db: Session) -> None:
        data = _as_user(db, client, "promote_target_ok")
        changed, message = promote(data["user"]["username"])
        assert changed is True
        assert "已提升" in message
        db.expire_all()
        assert db.get(User, data["user"]["id"]).role == ROLE_ADMIN

    def test_promote_admin_is_noop(self, client: TestClient, db: Session) -> None:
        data = _as_admin(db, client, "promote_admin_noop")
        changed, message = promote(data["user"]["username"])
        assert changed is False
        assert "已经是管理员" in message


class TestEnsureColumns:
    """列回填是本轮命门：没有它，老库的 users 表永远拿不到 role 列。"""

    def _legacy_engine(self, tmp_path):
        """造一个 v1.5 形态的旧库：有表，但没有 role / status 列。

        SQLite 不允许 DROP 被索引引用的列，因此先摘掉索引再删列。
        """
        url = f"sqlite:///{tmp_path}/legacy.db"
        engine = create_engine(url)
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            for index in ("ix_users_role", "ix_users_status", "ix_wordbooks_status", "ix_words_status"):
                conn.execute(text(f"DROP INDEX IF EXISTS {index}"))
            conn.execute(text("ALTER TABLE users DROP COLUMN role"))
            conn.execute(text("ALTER TABLE users DROP COLUMN status"))
            conn.execute(text("ALTER TABLE wordbooks DROP COLUMN status"))
            conn.execute(text("ALTER TABLE words DROP COLUMN status"))
        return engine

    def test_backfills_missing_columns(self, tmp_path) -> None:
        engine = self._legacy_engine(tmp_path)
        before = {c["name"] for c in inspect(engine).get_columns("users")}
        assert "role" not in before

        applied = _ensure_columns(engine)

        # 4 个缺失列 + 4 个缺失索引
        assert applied == 8
        after = {c["name"] for c in inspect(engine).get_columns("users")}
        assert {"role", "status"} <= after
        assert "status" in {c["name"] for c in inspect(engine).get_columns("wordbooks")}
        assert "status" in {c["name"] for c in inspect(engine).get_columns("words")}

    def test_is_idempotent(self, tmp_path) -> None:
        engine = self._legacy_engine(tmp_path)
        assert _ensure_columns(engine) == 8
        assert _ensure_columns(engine) == 0

    def test_backfilled_column_defaults(self, tmp_path) -> None:
        """补出来的列要带默认值，否则老数据行会因为 NOT NULL 直接报错。"""
        engine = self._legacy_engine(tmp_path)
        _ensure_columns(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, password_hash, is_guest, "
                    "consecutive_days) VALUES ('legacy_u', 'x', 0, 0)"
                )
            )
            row = conn.execute(text("SELECT role, status FROM users")).first()
        assert row is not None
        assert row[0] == ROLE_USER
        assert row[1] == USER_STATUS_ACTIVE

    def test_text_column_never_gets_full_index(self, tmp_path) -> None:
        """MySQL 对 TEXT 列建整列索引会报 error 1170。

        旧库补 metadata 列时若顺手 CREATE INDEX，MySQL 上 init_db 直接崩溃
        （后端启动失败就是这么来的）。对这类列必须只补列、不建索引。
        """
        url = f"sqlite:///{tmp_path}/mysql_like.db"
        engine = create_engine(url)
        # 不建 metadata 列，模拟「老库缺列」；SQLite 对 TEXT 索引宽容，
        # 但我们要验证的是 _ensure_columns 不会去建这个索引，行为与方言无关
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE chat_messages ("
                    "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
                    "role VARCHAR(16) NOT NULL, content TEXT NOT NULL, "
                    "created_at DATETIME NOT NULL)"
                )
            )
        indexes_before = {i["name"] for i in inspect(engine).get_indexes("chat_messages")}
        assert "ix_chat_messages_metadata" not in indexes_before

        applied = _ensure_columns(engine)

        columns = {c["name"] for c in inspect(engine).get_columns("chat_messages")}
        assert "metadata" in columns, "metadata 列必须被补上"
        indexes_after = {i["name"] for i in inspect(engine).get_indexes("chat_messages")}
        assert "ix_chat_messages_metadata" not in indexes_after, (
            "TEXT 列不能建整列索引，否则 MySQL 启动直接 1170"
        )
        # 只补了 1 个列，索引被跳过，因而不再 +1
        assert applied == 1

    def test_fresh_create_does_not_index_text_metadata(self, tmp_path) -> None:
        """全新建表也不能给 TEXT metadata 建索引。

        这条路径同样会撞 MySQL error 1170：ORM 模型在 create_all 阶段
        就为每个 index=True 生成索引，所以必须从模型源头去掉该索引声明。
        """
        url = f"sqlite:///{tmp_path}/fresh.db"
        engine = create_engine(url)
        Base.metadata.create_all(bind=engine)

        indexes = {i["name"] for i in inspect(engine).get_indexes("chat_messages")}
        assert "ix_chat_messages_metadata" not in indexes
        columns = {c["name"] for c in inspect(engine).get_columns("chat_messages")}
        assert "metadata" in columns, "列仍在，只是不带索引"

class TestDbSessionIsolation:
    def test_session_local_opens(self) -> None:
        with SessionLocal() as session:
            assert session is not None
