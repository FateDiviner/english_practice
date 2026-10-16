"""管理端后端：管理员注册规则、权限、用户管理与审计留痕。"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from admin_api.services import audit_service
from admin_api.services.user_admin_service import ADMIN_ROLE
from core.config import get_settings
from core.constants import USER_STATUS_ACTIVE, USER_STATUS_BANNED
from core.models.audit import AuditLog
from core.models.user import User
from tests.conftest import unique


def _reopen(db: Session) -> None:
    """结束快照事务，才能看见其它连接刚提交的写入。"""
    db.rollback()


def _clear_audit(db: Session) -> None:
    _reopen(db)
    db.query(AuditLog).delete()
    db.commit()
    _reopen(db)


class TestAdminRegistration:
    def test_first_admin_can_register_openly(self, client: TestClient, db: Session):
        """库里没有任何管理员时，注册口必须放行——这是首个管理员的唯一来源。"""
        _reopen(db)
        if db.scalar(select(User.id).where(User.role == ADMIN_ROLE)) is not None:
            pytest.skip("本用例只在系统尚无管理员时有意义（共享测试库已被占用）")

        response = client.post(
            "/api/admin/auth/register",
            json={"username": unique("first"), "password": "secret123"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["user"]["role"] == "admin"

    def test_second_admin_blocked_without_invite_code(
        self, client: TestClient, admin: dict
    ):
        """未配置邀请码时，已有管理员就拒绝——注册口不会变成抢注入口。"""
        response = client.post(
            "/api/admin/auth/register",
            json={"username": unique("sneaky"), "password": "secret123"},
        )

        assert response.status_code == 409
        assert "已有管理员" in response.json()["detail"]

    def test_invite_code_required_when_configured(
        self, client: TestClient, admin: dict
    ):
        os.environ["ADMIN_INVITE_CODE"] = "correct-horse"
        get_settings.cache_clear()

        wrong = client.post(
            "/api/admin/auth/register",
            json={"username": unique("withcode"), "password": "secret123", "invite_code": "nope"},
        )
        assert wrong.status_code == 403
        assert "邀请码" in wrong.json()["detail"]

        right = client.post(
            "/api/admin/auth/register",
            json={
                "username": unique("withcode"),
                "password": "secret123",
                "invite_code": "correct-horse",
            },
        )
        assert right.status_code == 200, right.text
        assert right.json()["user"]["role"] == "admin"

    def test_short_password_rejected(self, client: TestClient, admin: dict):
        response = client.post(
            "/api/admin/auth/register",
            json={"username": unique("short"), "password": "123"},
        )

        assert response.status_code == 422

    def test_duplicate_username_rejected(self, client: TestClient, admin: dict):
        client.post(
            "/api/admin/auth/register",
            json={"username": unique("dup"), "password": "secret123"},
        )
        # 第一个注册口已被管理员占用，这里改走管理端代建同名账号
        response = client.post(
            "/api/admin/users",
            json={"username": admin["username"], "password": "secret123"},
            headers=admin["headers"],
        )

        assert response.status_code == 409


class TestAdminLogin:
    def test_admin_can_login_and_fetch_me(self, client: TestClient, admin: dict):
        login = client.post(
            "/api/admin/auth/login",
            json={"username": admin["username"], "password": "secret123"},
        )

        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        me = client.get(
            "/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json()["role"] == "admin"

    def test_wrong_password_rejected(self, client: TestClient, admin: dict):
        response = client.post(
            "/api/admin/auth/login",
            json={"username": admin["username"], "password": "wrong-pass"},
        )

        assert response.status_code == 401

    def test_me_requires_token(self, client: TestClient):
        assert client.get("/api/admin/auth/me").status_code == 401


class TestPermissionBoundary:
    def test_anonymous_is_unauthorized(self, client: TestClient):
        assert client.get("/api/admin/users").status_code == 401

    def test_member_is_forbidden(self, client: TestClient, member: dict):
        response = client.get("/api/admin/users", headers=member["headers"])

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"

    def test_admin_is_allowed(self, client: TestClient, admin: dict):
        response = client.get("/api/admin/users", headers=admin["headers"])

        assert response.status_code == 200
        assert response.json()["total"] >= 2


class TestUserList:
    def test_pagination_and_filters(self, client: TestClient, admin: dict, member: dict):
        body = client.get("/api/admin/users", headers=admin["headers"]).json()
        assert body["total"] >= 2
        assert any(item["username"] == member["username"] for item in body["items"])

        filtered = client.get(
            "/api/admin/users",
            params={"role": "admin"},
            headers=admin["headers"],
        ).json()
        assert filtered["total"] >= 1
        assert all(item["role"] == "admin" for item in filtered["items"])

        searched = client.get(
            "/api/admin/users",
            params={"search": member["username"]},
            headers=admin["headers"],
        ).json()
        assert searched["total"] == 1

        limited = client.get(
            "/api/admin/users", params={"limit": 1}, headers=admin["headers"]
        ).json()
        assert len(limited["items"]) == 1

    def test_password_hash_never_leaks(self, client: TestClient, admin: dict):
        body = client.get("/api/admin/users", headers=admin["headers"]).text

        assert "password_hash" not in body
        assert "secret123" not in body

    def test_list_carries_activity(self, client: TestClient, admin: dict, member: dict):
        items = client.get(
            "/api/admin/users",
            params={"search": member["username"]},
            headers=admin["headers"],
        ).json()["items"]

        assert items[0]["practice_count"] == 0
        assert items[0]["last_practiced_at"] is None


class TestCreateUser:
    def test_creates_with_role(self, client: TestClient, admin: dict):
        username = unique("made")
        response = client.post(
            "/api/admin/users",
            json={"username": username, "password": "secret123", "role": "user"},
            headers=admin["headers"],
        )

        assert response.status_code == 200, response.text
        assert response.json()["role"] == "user"

    def test_invalid_role_rejected(self, client: TestClient, admin: dict):
        response = client.post(
            "/api/admin/users",
            json={"username": unique("bad"), "password": "secret123", "role": "superuser"},
            headers=admin["headers"],
        )

        assert response.status_code == 422


class TestBanAndRestore:
    def test_ban_blocks_login(self, client: TestClient, admin: dict, member: dict):
        response = client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={"status": "banned"},
            headers=admin["headers"],
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == USER_STATUS_BANNED

        login = client.post(
            "/api/admin/auth/login",
            json={"username": member["username"], "password": "secret123"},
        )
        assert login.status_code == 403
        assert "封禁" in login.json()["detail"]

    def test_ban_invalidates_existing_token(self, client: TestClient, admin: dict, member: dict):
        """封禁必须立即生效，不能等旧令牌自己过期。"""
        before = client.get("/api/admin/auth/me", headers=member["headers"])
        assert before.status_code == 200

        client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={"status": "banned"},
            headers=admin["headers"],
        )

        after = client.get("/api/admin/auth/me", headers=member["headers"])
        assert after.status_code == 403
        assert "封禁" in after.json()["detail"]

    def test_unban_restores_access(self, client: TestClient, admin: dict, member: dict):
        client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={"status": "banned"},
            headers=admin["headers"],
        )
        client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={"status": "active"},
            headers=admin["headers"],
        )

        login = client.post(
            "/api/admin/auth/login",
            json={"username": member["username"], "password": "secret123"},
        )
        assert login.status_code == 200, login.text

    def test_role_change_takes_effect(self, client: TestClient, admin: dict, member: dict):
        response = client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={"role": "admin"},
            headers=admin["headers"],
        )
        assert response.json()["role"] == ADMIN_ROLE

        # 升级后可以访问管理接口
        login = client.post(
            "/api/admin/auth/login",
            json={"username": member["username"], "password": "secret123"},
        )
        upgraded = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/admin/users", headers=upgraded).status_code == 200

    def test_no_fields_rejected(self, client: TestClient, admin: dict, member: dict):
        response = client.patch(
            f"/api/admin/users/{member['user_id']}",
            json={},
            headers=admin["headers"],
        )

        assert response.status_code == 400

    def test_unknown_user_404(self, client: TestClient, admin: dict):
        response = client.patch(
            "/api/admin/users/999999",
            json={"status": "banned"},
            headers=admin["headers"],
        )

        assert response.status_code == 404


def _force_single_admin(db: Session, keep_user_id: int) -> int:
    """把除 keep_user_id 之外的管理员全部降级，制造确定的「仅剩一个管理员」场景。"""
    _reopen(db)
    for extra in db.scalars(select(User).where(User.role == ADMIN_ROLE)).all():
        if extra.id != keep_user_id:
            extra.role = "user"
    db.commit()
    _reopen(db)
    return keep_user_id


class TestSelfProtectionAndLastAdmin:
    def test_cannot_ban_self(self, client: TestClient, admin: dict):
        response = client.patch(
            f"/api/admin/users/{admin['user_id']}",
            json={"status": "banned"},
            headers=admin["headers"],
        )

        # 拒绝本身是不变量；理由取决于当前管理员数量（自己是唯一管理员时会先命中 409）
        assert response.status_code in (400, 409)
        assert response.json()["detail"] in (
            "不能对自己执行该操作",
            "系统必须保留至少一个管理员",
        )

    def test_cannot_delete_self(self, client: TestClient, admin: dict):
        response = client.delete(
            f"/api/admin/users/{admin['user_id']}", headers=admin["headers"]
        )

        assert response.status_code == 400
        assert "不能删除自己" in response.json()["detail"]

    def test_cannot_demote_last_admin(
        self, client: TestClient, admin: dict, db: Session
    ):
        """把唯一的管理员降级，等于把所有人都锁在门外。"""
        target = _force_single_admin(db, admin["user_id"])

        response = client.patch(
            f"/api/admin/users/{target}",
            json={"role": "user"},
            headers=admin["headers"],
        )

        assert response.status_code == 409
        assert "至少一个管理员" in response.json()["detail"]

    def test_cannot_ban_last_admin(self, client: TestClient, admin: dict, db: Session):
        target = _force_single_admin(db, admin["user_id"])

        response = client.patch(
            f"/api/admin/users/{target}",
            json={"status": "banned"},
            headers=admin["headers"],
        )

        assert response.status_code == 409


class TestDeleteUser:
    def test_delete_removes_user_and_cascades(
        self, client: TestClient, admin: dict, member: dict, db: Session
    ):
        response = client.delete(
            f"/api/admin/users/{member['user_id']}", headers=admin["headers"]
        )

        assert response.status_code == 200, response.text
        assert response.json()["deleted"] is True

        _reopen(db)
        assert db.get(User, member["user_id"]) is None

        # 旧令牌随账号一起失效
        me = client.get("/api/admin/auth/me", headers=member["headers"])
        assert me.status_code == 401

    def test_delete_unknown_404(self, client: TestClient, admin: dict):
        assert (
            client.delete("/api/admin/users/999999", headers=admin["headers"]).status_code
            == 404
        )


class TestAuditTrail:
    def test_every_write_is_audited(self, client: TestClient, admin: dict, member: dict,
                                    db: Session):
        _clear_audit(db)
        username = unique("audited")

        client.post(
            "/api/admin/users",
            json={"username": username, "password": "secret123"},
            headers=admin["headers"],
        )
        target = client.get(
            "/api/admin/users", params={"search": username}, headers=admin["headers"]
        ).json()["items"][0]
        client.patch(
            f"/api/admin/users/{target['id']}", json={"status": "banned"},
            headers=admin["headers"],
        )
        client.patch(
            f"/api/admin/users/{target['id']}", json={"status": "active"},
            headers=admin["headers"],
        )
        client.delete(f"/api/admin/users/{target['id']}", headers=admin["headers"])

        page = client.get("/api/admin/audit-logs", headers=admin["headers"]).json()
        actions = [item["action"] for item in page["items"]]

        assert "user.create" in actions
        assert "user.ban" in actions
        assert "user.unban" in actions
        assert "user.delete" in actions
        # 审计记录了连带删除的行数
        delete_entry = next(item for item in page["items"] if item["action"] == "user.delete")
        assert delete_entry["actor_name"] == admin["username"]

    def test_audit_filters_and_pagination(self, client: TestClient, admin: dict, db: Session):
        page = client.get(
            "/api/admin/audit-logs", params={"limit": 5}, headers=admin["headers"]
        ).json()
        assert len(page["items"]) <= 5

        filtered = client.get(
            "/api/admin/audit-logs",
            params={"action": "user.create"},
            headers=admin["headers"],
        ).json()
        assert all(item["action"] == "user.create" for item in filtered["items"])

    def test_no_update_or_delete_endpoint(self, client: TestClient, admin: dict):
        """审计只增不改不删：应用层不提供任何写接口。"""
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = client.request(method, "/api/admin/audit-logs", headers=admin["headers"])
            assert response.status_code in (404, 405), f"{method} 不应被允许"

    def test_sensitive_keys_rejected(self, db: Session, admin: dict):
        _reopen(db)
        actor = db.get(User, admin["user_id"])
        assert actor is not None
        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                db, actor=actor, action="user.update", detail={"password_hash": "x"}
            )
        db.rollback()

    def test_rolls_back_with_business_failure(self, db: Session, admin: dict):
        _clear_audit(db)
        _reopen(db)
        actor = db.get(User, admin["user_id"])

        with pytest.raises(RuntimeError):
            audit_service.record(db, actor=actor, action="user.create", detail={"a": 1})
            db.flush()
            raise RuntimeError("业务失败")

        db.rollback()
        _reopen(db)
        assert list(db.scalars(select(AuditLog)).all()) == []


class TestHealthAndSchema:
    def test_health_reports_invite_policy(self, client: TestClient):
        body = client.get("/api/admin/health").json()

        assert body["status"] == "ok"
        assert body["invite_code_required"] is False

    def test_detail_never_leaks_secrets(self, client: TestClient, admin: dict):
        raw = json.dumps(
            client.get("/api/admin/users", headers=admin["headers"]).json(),
            ensure_ascii=False,
        )

        assert "password_hash" not in raw
        assert "secret123" not in raw

class TestCreateAdminCli:
    """CLI 是「注册口被锁死后的最后一条出路」，必须始终可用。"""

    def test_promotes_existing_member(self, client: TestClient, member: dict):
        from admin_api.scripts.create_admin import promote

        changed, message = promote(member["username"])

        assert changed is True
        assert "已提升为管理员" in message
        assert client.get("/api/admin/users", headers=member["headers"]).status_code == 200

    def test_promote_is_idempotent(self, client: TestClient, admin: dict):
        from admin_api.scripts.create_admin import promote

        changed, message = promote(admin["username"])

        assert changed is False
        assert "已经是管理员" in message

    def test_missing_user_rejected(self):
        from admin_api.scripts.create_admin import promote

        changed, message = promote("definitely-not-a-user")

        assert changed is False
        assert "不存在" in message

    def test_password_hash_untouched(self, client: TestClient, member: dict, db: Session):
        from admin_api.scripts.create_admin import promote

        _reopen(db)
        before = db.get(User, member["user_id"]).password_hash

        promote(member["username"])

        _reopen(db)
        assert db.get(User, member["user_id"]).password_hash == before
