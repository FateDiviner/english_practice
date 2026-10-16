"""管理端地基：权限模型与审计留痕。"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.services import audit_service
from scripts.create_admin import promote


@pytest.fixture()
def member(client: TestClient) -> dict:
    """注册一个普通用户，返回其令牌与用户信息。"""
    response = client.post(
        "/api/auth/register",
        # id(client) 会随对象地址复用而重复，跨用例必然撞名 409
        json={"username": f"member_{uuid.uuid4().hex[:10]}", "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {
        "token": body["access_token"],
        "user_id": body["user"]["id"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


@pytest.fixture()
def admin(client: TestClient, member: dict, db: Session) -> dict:
    """把 member 提升为管理员。"""
    username = client.get("/api/auth/me", headers=member["headers"]).json()["username"]
    changed, message = promote(username)
    assert changed, message
    return member


class TestRequireAdmin:
    def test_no_token_is_unauthorized(self, client: TestClient):
        assert client.get("/api/admin/audit-logs").status_code == 401

    def test_member_is_forbidden(self, client: TestClient, member: dict):
        response = client.get("/api/admin/audit-logs", headers=member["headers"])

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"

    def test_guest_is_forbidden(self, client: TestClient):
        guest = client.post("/api/auth/guest").json()
        headers = {"Authorization": f"Bearer {guest['access_token']}"}

        assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403

    def test_admin_is_allowed(self, client: TestClient, admin: dict):
        response = client.get("/api/admin/audit-logs", headers=admin["headers"])

        assert response.status_code == 200, response.text
        assert response.json() == {"total": 0, "items": []}

    def test_member_info_carries_role(self, client: TestClient, member: dict):
        body = client.get("/api/auth/me", headers=member["headers"]).json()

        assert body["role"] == "user"


class TestCreateAdminCli:
    def test_promotes_member(self, client: TestClient, member: dict):
        username = client.get("/api/auth/me", headers=member["headers"]).json()["username"]

        changed, message = promote(username)

        assert changed is True
        assert "已提升为管理员" in message
        assert client.get("/api/admin/audit-logs", headers=member["headers"]).status_code == 200

    def test_promote_is_idempotent(self, client: TestClient, member: dict):
        username = client.get("/api/auth/me", headers=member["headers"]).json()["username"]
        promote(username)

        changed, message = promote(username)

        assert changed is False
        assert "已经是管理员" in message

    def test_missing_user_rejected(self):
        changed, message = promote("definitely-not-a-user")

        assert changed is False
        assert "不存在" in message

    def test_guest_cannot_be_promoted(self, client: TestClient):
        guest = client.post("/api/auth/guest").json()
        username = guest["user"]["username"]

        changed, message = promote(username)

        assert changed is False
        assert "游客" in message

    def test_password_hash_untouched_by_cli(self, client: TestClient, member: dict, db: Session):
        _reopen(db)
        before = db.get(User, member["user_id"]).password_hash
        username = client.get("/api/auth/me", headers=member["headers"]).json()["username"]

        promote(username)

        _reopen(db)
        assert db.get(User, member["user_id"]).password_hash == before


def _reopen(db: Session) -> None:
    """结束快照事务，才能看见其它连接刚提交的写入。"""
    db.rollback()


def _clear_audit(db: Session) -> None:
    """清空审计表，让断言只对本用例写入的数据负责。"""
    _reopen(db)
    db.query(AuditLog).delete()
    db.commit()
    _reopen(db)


class TestAuditService:
    def test_record_is_persisted_after_commit(self, client: TestClient, admin: dict, db: Session):
        _clear_audit(db)
        actor = db.get(User, admin["user_id"])
        audit_service.record(
            db, actor=actor, action="wordbook.archive", target_type="wordbook",
            target_id=1, detail={"code": "cet4"}, affected_rows=1,
        )
        db.commit()

        _reopen(db)
        rows = list(db.scalars(select(AuditLog)).all())
        assert len(rows) == 1
        assert rows[0].action == "wordbook.archive"
        assert rows[0].actor_name == actor.username
        assert json.loads(rows[0].detail) == {"code": "cet4"}
        assert rows[0].affected_rows == 1

    def test_sensitive_detail_is_rejected(self, client: TestClient, admin: dict, db: Session):
        _reopen(db)
        actor = db.get(User, admin["user_id"])

        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                db, actor=actor, action="user.update",
                detail={"password_hash": "scrambled"},
            )

    @pytest.mark.parametrize("key", ["password", "token", "api_key", "content"])
    def test_all_sensitive_keys_blocked(self, client: TestClient, admin: dict, db: Session,
                                        key: str):
        _reopen(db)
        actor = db.get(User, admin["user_id"])

        with pytest.raises(audit_service.AuditError):
            audit_service.record(db, actor=actor, action="x", detail={key: "v"})

    def test_rolls_back_together_with_business_write(
        self, client: TestClient, admin: dict, db: Session
    ):
        """业务失败时审计必须一起回滚，不能留下"写了日志但没做事"。"""
        _clear_audit(db)
        actor = db.get(User, admin["user_id"])

        with pytest.raises(RuntimeError):
            audit_service.record(
                db, actor=actor, action="word.create", detail={"word": "abandon"}
            )
            db.flush()
            raise RuntimeError("业务失败")

        db.rollback()
        _reopen(db)
        assert list(db.scalars(select(AuditLog)).all()) == []

    def test_audit_survives_actor_deletion(self, client: TestClient, admin: dict, db: Session):
        """操作人被删除后，日志仍要能读出是谁做的。"""
        _clear_audit(db)
        actor = db.get(User, admin["user_id"])
        actor_name = actor.username
        audit_service.record(db, actor=actor, action="user.delete", target_type="user",
                             target_id=42)
        db.commit()

        _reopen(db)
        target = db.get(User, admin["user_id"])
        db.delete(target)
        db.commit()

        _reopen(db)
        row = db.scalars(select(AuditLog)).first()
        assert row is not None
        assert row.actor_id is None
        assert row.actor_name == actor_name


class TestAuditApi:
    def test_pagination_and_filters(self, client: TestClient, admin: dict, db: Session):
        _clear_audit(db)
        actor = db.get(User, admin["user_id"])
        for index in range(3):
            audit_service.record(
                db, actor=actor, action=f"action.{index}", target_type="word",
                target_id=index,
            )
        audit_service.record(db, actor=actor, action="word.create", target_type="word",
                             target_id=99)
        db.commit()

        page = client.get("/api/admin/audit-logs", headers=admin["headers"]).json()
        assert page["total"] == 4

        filtered = client.get(
            "/api/admin/audit-logs",
            params={"action": "word.create"},
            headers=admin["headers"],
        ).json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["target_id"] == "99"

        limited = client.get(
            "/api/admin/audit-logs", params={"limit": 2}, headers=admin["headers"]
        ).json()
        assert len(limited["items"]) == 2

    def test_no_update_or_delete_endpoint(self, client: TestClient, admin: dict):
        """审计只增不改不删：应用层不提供任何写接口。"""
        base = "/api/admin/audit-logs"
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = client.request(method, base, headers=admin["headers"])
            assert response.status_code in (404, 405), f"{method} 不应被允许"

    def test_detail_never_leaks_secrets(self, client: TestClient, admin: dict, db: Session):
        _clear_audit(db)
        actor = db.get(User, admin["user_id"])
        audit_service.record(db, actor=actor, action="user.update",
                             detail={"username": "renamed"})
        db.commit()

        page = client.get("/api/admin/audit-logs", headers=admin["headers"]).json()

        assert "password_hash" not in json.dumps(page)
        assert AuditLogOut.model_validate(page["items"][0]).action == "user.update"
