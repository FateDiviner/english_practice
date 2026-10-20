"""管理端用户管理接口测试。

重点在三条硬约束：不能对自己动手、必须保留至少一个管理员、
删除前先把影响面统计出来写进审计。
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import ROLE_ADMIN, ROLE_USER, USER_STATUS_BANNED
from app.models.chat import ChatMessage
from app.models.record import UserWordRecord
from app.models.session import PracticeSessionRecord
from app.models.user import User
from tests.admin_helpers import (
    demote_other_admins,
    headers,
    make_admin,
    make_user,
    unique_name,
)


def _setup(db: Session, client: TestClient) -> tuple[str, str]:
    """建一个管理员和一个普通用户，返回 (管理员 token, 普通用户 token)。"""
    admin = make_admin(db, client, unique_name("um_admin"))
    plain = make_user(db, client, unique_name("um_plain"))
    return admin["access_token"], plain["access_token"]


def _user_id(client: TestClient, token: str) -> int:
    return client.get("/api/auth/me", headers=headers(token)).json()["id"]


class TestPermissionGate:
    def test_plain_user_gets_403(self, client: TestClient, db: Session) -> None:
        _, plain_token = _setup(db, client)
        response = client.get("/api/admin/users", headers=headers(plain_token))
        assert response.status_code == 403
        assert "管理员" in response.json()["detail"]

    def test_guest_gets_403(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("um_admin_for_guest"))
        guest = client.post("/api/auth/guest").json()
        response = client.get("/api/admin/users", headers=headers(guest["access_token"]))
        assert response.status_code == 403

    def test_anonymous_gets_401(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("um_admin_for_anon"))
        response = client.get("/api/admin/users", headers={"Authorization": "Bearer bad"})
        assert response.status_code == 401


class TestListUsers:
    def test_lists_with_filters(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        target = unique_name("um_searchable")
        make_user(db, client, target)
        response = client.get(
            "/api/admin/users", params={"search": target}, headers=headers(admin_token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["username"] == target

    def test_filter_by_role(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.get(
            "/api/admin/users", params={"role": "admin"}, headers=headers(admin_token)
        )
        assert response.status_code == 200
        assert all(item["role"] == ROLE_ADMIN for item in response.json()["items"])

    def test_password_hash_never_returned(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.get("/api/admin/users", headers=headers(admin_token))
        assert response.json()["items"]
        for item in response.json()["items"]:
            assert "password_hash" not in item

    def test_pagination(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.get(
            "/api/admin/users",
            params={"limit": 1, "offset": 0},
            headers=headers(admin_token),
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) <= 1


class TestCreateUser:
    def test_creates_plain_user(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.post(
            "/api/admin/users",
            json={"username": unique_name("um_created"), "password": "secret123"},
            headers=headers(admin_token),
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == ROLE_USER

    def test_duplicate_username_409(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        payload = {"username": unique_name("um_dup"), "password": "secret123"}
        first = client.post("/api/admin/users", json=payload, headers=headers(admin_token))
        assert first.status_code == 200, first.text
        second = client.post("/api/admin/users", json=payload, headers=headers(admin_token))
        assert second.status_code == 409

    def test_password_never_echoed(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.post(
            "/api/admin/users",
            json={"username": unique_name("um_noecho"), "password": "secret123"},
            headers=headers(admin_token),
        )
        assert "password" not in response.json()
        assert "password_hash" not in response.json()


class TestUpdateUser:
    def test_ban_takes_effect_immediately(self, client: TestClient, db: Session) -> None:
        admin_token, plain_token = _setup(db, client)
        plain_id = _user_id(client, plain_token)

        response = client.patch(
            f"/api/admin/users/{plain_id}",
            json={"status": USER_STATUS_BANNED},
            headers=headers(admin_token),
        )
        assert response.status_code == 200, response.text

        # 已发出的令牌必须立刻失效
        assert client.get("/api/auth/me", headers=headers(plain_token)).status_code == 403

    def test_promote_then_demote(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        target_id = make_user(db, client, unique_name("um_role_cycle"))["user"]["id"]

        promoted = client.patch(
            f"/api/admin/users/{target_id}",
            json={"role": ROLE_ADMIN},
            headers=headers(admin_token),
        )
        assert promoted.status_code == 200, promoted.text

        demoted = client.patch(
            f"/api/admin/users/{target_id}",
            json={"role": ROLE_USER},
            headers=headers(admin_token),
        )
        assert demoted.status_code == 200, demoted.text

    def test_cannot_demote_last_admin(self, client: TestClient, db: Session) -> None:
        """唯一管理员被降级后系统将无人可管理，必须拦住。"""
        admin = make_admin(db, client, unique_name("um_last_admin"))
        demote_other_admins(db, admin["user"]["id"])
        response = client.patch(
            f"/api/admin/users/{admin['user']['id']}",
            json={"role": ROLE_USER},
            headers=headers(admin["access_token"]),
        )
        assert response.status_code == 409
        assert "至少一个管理员" in response.json()["detail"]

    def test_cannot_ban_last_admin(self, client: TestClient, db: Session) -> None:
        admin = make_admin(db, client, unique_name("um_last_admin_ban"))
        demote_other_admins(db, admin["user"]["id"])
        response = client.patch(
            f"/api/admin/users/{admin['user']['id']}",
            json={"status": USER_STATUS_BANNED},
            headers=headers(admin["access_token"]),
        )
        assert response.status_code == 409

    def test_cannot_touch_self(self, client: TestClient, db: Session) -> None:
        admin = make_admin(db, client, unique_name("um_self_guard"))
        # 先造第二个管理员，否则会先撞上「至少一个管理员」那条 409
        make_admin(db, client, unique_name("um_second_admin"))
        response = client.patch(
            f"/api/admin/users/{admin['user']['id']}",
            json={"status": USER_STATUS_BANNED},
            headers=headers(admin["access_token"]),
        )
        assert response.status_code == 400
        assert "自己" in response.json()["detail"]

    def test_empty_payload_400(self, client: TestClient, db: Session) -> None:
        admin_token, plain_token = _setup(db, client)
        response = client.patch(
            f"/api/admin/users/{_user_id(client, plain_token)}",
            json={},
            headers=headers(admin_token),
        )
        assert response.status_code == 400

    def test_missing_user_404(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.patch(
            "/api/admin/users/999999",
            json={"role": ROLE_USER},
            headers=headers(admin_token),
        )
        assert response.status_code == 404


class TestDeleteUser:
    def test_cannot_delete_self(self, client: TestClient, db: Session) -> None:
        admin = make_admin(db, client, unique_name("um_del_self"))
        make_admin(db, client, unique_name("um_del_second"))
        response = client.delete(
            f"/api/admin/users/{admin['user']['id']}",
            headers=headers(admin["access_token"]),
        )
        assert response.status_code == 400
        assert "自己" in response.json()["detail"]

    def test_cannot_delete_last_admin(self, client: TestClient, db: Session) -> None:
        """真正要保证的不变量是「系统里始终还有管理员」。

        注意：删自己会先撞上「不能删除自己」的 400，而操作者必然已是管理员，
        所以服务里那条 409 在 API 路径上不可达。这里断言不变量而非分支。
        """
        admin = make_admin(db, client, unique_name("um_del_last_admin"))
        demote_other_admins(db, admin["user"]["id"])

        response = client.delete(
            f"/api/admin/users/{admin['user']['id']}",
            headers=headers(admin["access_token"]),
        )
        assert response.status_code == 400
        assert "自己" in response.json()["detail"]

        db.expire_all()
        assert db.get(User, admin["user"]["id"]) is not None
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_ADMIN))
            >= 1
        )

    def test_deletes_with_practice_data(self, client: TestClient, db: Session) -> None:
        """删用户要连带清理练习数据，且把影响面如实报出来。"""
        admin_token, plain_token = _setup(db, client)
        plain_id = _user_id(client, plain_token)

        for _ in range(3):
            db.add(UserWordRecord(user_id=plain_id, word_id=1, status="learning"))
        db.add(
            PracticeSessionRecord(
                user_id=plain_id, wordbook_id=1, total=5, practiced_on=date(2026, 10, 20)
            )
        )
        db.add(ChatMessage(user_id=plain_id, role="user", content="hello"))
        db.commit()

        response = client.delete(f"/api/admin/users/{plain_id}", headers=headers(admin_token))
        assert response.status_code == 200, response.text
        # 3 条词条记录 + 1 次会话 + 1 条对话
        assert response.json()["affected_rows"] == 5

        assert db.get(User, plain_id) is None
        leftover = db.scalar(
            select(func.count())
            .select_from(UserWordRecord)
            .where(UserWordRecord.user_id == plain_id)
        )
        assert leftover == 0

    def test_missing_user_404(self, client: TestClient, db: Session) -> None:
        admin_token, _ = _setup(db, client)
        response = client.delete("/api/admin/users/999999", headers=headers(admin_token))
        assert response.status_code == 404
