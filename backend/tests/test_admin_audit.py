"""管理端审计留痕测试。

审计只增不改不删：写操作与业务写入同事务提交，操作人被删后日志仍要可读。
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ROLE_ADMIN, STATUS_ARCHIVED
from app.models.audit import AuditLog
from app.models.user import User
from app.services import audit_service
from tests.admin_helpers import (
    good_book,
    good_word,
    headers,
    make_admin,
    make_user,
    unique_name,
)


def _admin_token(db: Session, client: TestClient) -> str:
    return make_admin(db, client, unique_name("au_admin"))["access_token"]


def _actions(db: Session, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


class TestWriteOperationsAreLogged:
    def test_user_create_logged(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        name = unique_name("au_created")
        client.post(
            "/api/admin/users",
            json={"username": name, "password": "secret123"},
            headers=headers(token),
        )
        entries = _actions(db, "user.create")
        assert entries, "创建用户必须留痕"
        assert any(name in (entry.detail or "") for entry in entries)

    def test_wordbook_import_logged(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        code = unique_name("wb_audit")[:32]
        client.post(
            "/api/admin/wordbooks/import",
            json=good_book(code=code),
            headers=headers(token),
        )
        entries = _actions(db, "wordbook.import")
        assert entries
        assert any(code in (entry.detail or "") for entry in entries)

    def test_word_archive_logged(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = client.post(
            "/api/admin/wordbooks", json=good_book(code=unique_name("wb_arch")[:32]),
            headers=headers(token),
        ).json()
        word = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(),
            headers=headers(token),
        ).json()
        client.put(
            f"/api/admin/words/{word['id']}/status",
            params={"status": STATUS_ARCHIVED},
            headers=headers(token),
        )
        assert _actions(db, "word.archive")

    def test_affected_rows_recorded_on_delete(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        victim = make_user(db, client, unique_name("au_victim"))
        from app.models.chat import ChatMessage

        db.add(ChatMessage(user_id=victim["user"]["id"], role="user", content="hi"))
        db.commit()

        client.delete(f"/api/admin/users/{victim['user']['id']}", headers=headers(token))
        entries = _actions(db, "user.delete")
        assert entries
        assert entries[-1].affected_rows >= 1


class TestSensitiveFieldsBlocked:
    """这些字段一旦进 detail 就等于把凭据写进了日志。"""

    @pytest.mark.parametrize(
        "key",
        ["password", "password_hash", "token", "access_token", "secret", "api_key",
         "authorization", "content", "messages"],
    )
    def test_rejected(self, key: str) -> None:
        with pytest.raises(audit_service.AuditError):
            audit_service._assert_no_secrets({key: "x"})

    def test_case_insensitive(self) -> None:
        with pytest.raises(audit_service.AuditError):
            audit_service._assert_no_secrets({"PassWord": "x"})

    def test_benign_detail_allowed(self) -> None:
        audit_service._assert_no_secrets({"username": "abc", "role": "admin"})


class TestActorDeletion:
    def test_log_survives_actor_deletion(self, client: TestClient, db: Session) -> None:
        """操作人被删后日志仍要可读：外键置空而非级联删除，姓名走快照。"""
        token = _admin_token(db, client)
        doomed_name = unique_name("au_doomed")
        doomed = make_admin(db, client, doomed_name)
        doomed_id = doomed["user"]["id"]

        book = client.post(
            "/api/admin/wordbooks",
            json=good_book(code=unique_name("wb_doomed")[:32]),
            headers=headers(doomed["access_token"]),
        )
        assert book.status_code == 200, book.text

        # 让另一个管理员来删他，否则会撞上「不能删自己」
        deleter = make_admin(db, client, unique_name("au_deleter"))
        response = client.delete(
            f"/api/admin/users/{doomed_id}", headers=headers(deleter["access_token"])
        )
        assert response.status_code == 200, response.text

        assert db.get(User, doomed_id) is None
        db.expire_all()
        entries = [
            entry
            for entry in db.scalars(select(AuditLog)).all()
            if entry.actor_name == doomed_name
        ]
        assert entries, "操作人被删后审计仍应存在"
        # 外键被置空，但姓名快照还在，日志依旧认得出是谁
        assert all(entry.actor_id is None for entry in entries)
        assert all(entry.actor_name == doomed_name for entry in entries)


class TestAuditIsReadOnly:
    def test_no_write_routes_exposed(self, client: TestClient, db: Session) -> None:
        """审计只增不改不删，应用层不提供任何修改或删除审计的接口。"""
        token = _admin_token(db, client)
        for method, path in (
            ("POST", "/api/admin/audit-logs"),
            ("DELETE", "/api/admin/audit-logs/1"),
            ("PATCH", "/api/admin/audit-logs/1"),
        ):
            response = client.request(method, path, headers=headers(token))
            assert response.status_code in (404, 405), f"{method} {path} 不应存在"

    def test_list_requires_admin(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("au_gate"))
        plain = make_user(db, client, unique_name("au_plain"))
        response = client.get("/api/admin/audit-logs", headers=headers(plain["access_token"]))
        assert response.status_code == 403

    def test_detail_is_valid_json(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        client.post(
            "/api/admin/wordbooks",
            json=good_book(code=unique_name("wb_json")[:32]),
            headers=headers(token),
        )
        page = client.get("/api/admin/audit-logs", headers=headers(token)).json()
        assert page["items"]
        for item in page["items"]:
            if item["detail"]:
                parsed = json.loads(item["detail"])
                assert isinstance(parsed, dict)
                assert "password" not in parsed
