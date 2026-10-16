"""学习数据备份：导出内容、合并语义与幂等性。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.record import UserWordRecord
from app.models.session import PracticeSessionRecord
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import WordBook
from app.services import backup_service, stats_service


@pytest.fixture()
def user_id(auth_client: TestClient) -> int:
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


@pytest.fixture()
def book(db: Session) -> WordBook:
    book = db.scalars(select(WordBook).order_by(WordBook.id)).first()
    assert book is not None, "内置词书应已在测试库中导入"
    return book


def _reopen(db: Session) -> None:
    """结束本会话的快照事务，才能看见 API 侧刚提交的写入。"""
    db.rollback()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sign_up(client: TestClient, username: str, guest_id: int | None = None) -> dict:
    headers = {"X-Guest-Id": str(guest_id)} if guest_id is not None else None
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _complete_group(client: TestClient, book_id: int, size: int = 3) -> None:
    start = client.post(
        "/api/practice/start", json={"wordbook_id": book_id, "size": size}
    ).json()
    for clue in start["clues"]:
        client.post(
            "/api/practice/submit",
            json={
                "session_id": start["session_id"],
                "word_id": clue["id"],
                "answer": "definitely-wrong",
            },
        )
    settle = client.post(f"/api/practice/finish?session_id={start['session_id']}")
    assert settle.status_code == 200, settle.text


class TestExport:
    def test_requires_auth(self, client: TestClient):
        assert client.get("/api/user/export").status_code == 401

    def test_fresh_account_exports_empty_envelope(self, auth_client: TestClient):
        body = auth_client.get("/api/user/export").json()

        assert body["format"] == backup_service.BACKUP_FORMAT
        assert body["version"] == backup_service.BACKUP_VERSION
        assert body["word_records"] == []
        assert body["sessions"] == []
        assert body["chat_messages"] == []
        assert body["summary"]["words"] == 0

    def test_contains_no_account_identifiers(self, auth_client: TestClient,
                                             book: WordBook):
        _complete_group(auth_client, book.id, size=2)

        body = auth_client.get("/api/user/export").json()

        # 备份要在账号之间搬运，任何账号标识都既无必要又会变成敏感数据
        assert "user_id" not in body
        assert "username" not in body
        assert "password_hash" not in json.dumps(body, ensure_ascii=False)

    def test_contains_records_sessions_and_checkin(self, auth_client: TestClient,
                                                   user_id: int, book: WordBook):
        assert auth_client.post(f"/api/wordbooks/{book.id}/activate").status_code == 200
        _complete_group(auth_client, book.id, size=3)

        body = auth_client.get("/api/user/export").json()

        assert len(body["word_records"]) == 3
        assert body["word_records"][0]["wordbook"] == book.code
        assert body["word_records"][0]["word"]
        assert len(body["sessions"]) == 1
        assert body["sessions"][0]["total"] == 3
        assert body["sessions"][0]["practiced_on"]
        assert body["consecutive_days"] == 1
        assert body["last_checkin_date"] == stats_service.today_utc().isoformat()
        assert body["active_wordbook"] == book.code

    def test_active_wordbook_exported_by_code_not_id(self, auth_client: TestClient,
                                                     book: WordBook):
        assert auth_client.post(f"/api/wordbooks/{book.id}/activate").status_code == 200
        _complete_group(auth_client, book.id, size=1)

        body = auth_client.get("/api/user/export").json()

        assert body["active_wordbook"] == book.code
        assert body["active_wordbook"].isdigit() is False


class TestImport:
    def test_rejects_wrong_format(self, auth_client: TestClient):
        payload = auth_client.get("/api/user/export").json()
        payload["format"] = "someone-elses-backup"

        response = auth_client.post("/api/user/import", json=payload)

        assert response.status_code == 422
        assert "不是本平台" in response.json()["detail"]

    def test_rejects_wrong_version(self, auth_client: TestClient):
        payload = auth_client.get("/api/user/export").json()
        payload["version"] = 99

        response = auth_client.post("/api/user/import", json=payload)

        assert response.status_code == 422
        assert "版本" in response.json()["detail"]

    def test_rejects_malformed_body(self, auth_client: TestClient):
        response = auth_client.post(
            "/api/user/import",
            content="not a backup file",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_rejects_oversized_payload(self, auth_client: TestClient, book: WordBook):
        payload = auth_client.get("/api/user/export").json()
        payload["word_records"] = [
            {"wordbook": book.code, "word": f"w{index}"}
            for index in range(2001)
        ]

        response = auth_client.post("/api/user/import", json=payload)

        assert response.status_code == 422

    def test_cross_account_roundtrip(self, auth_client: TestClient, book: WordBook):
        _complete_group(auth_client, book.id, size=3)
        backup = auth_client.get("/api/user/export").json()

        other = _sign_up(auth_client, f"restore_{book.id}_a")
        response = auth_client.post(
            "/api/user/import",
            json=backup,
            headers=_headers(other["access_token"]),
        )

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["records_new"] == 3
        assert result["records_merged"] == 0
        assert result["sessions_added"] == 1
        assert result["words_unmatched"] == 0

        restored = auth_client.get(
            "/api/user/export", headers=_headers(other["access_token"])
        ).json()
        assert len(restored["word_records"]) == 3
        assert len(restored["sessions"]) == 1
        assert restored["consecutive_days"] == 1

    def test_reimport_is_idempotent(self, auth_client: TestClient, book: WordBook):
        _complete_group(auth_client, book.id, size=2)
        backup = auth_client.get("/api/user/export").json()

        other = _sign_up(auth_client, f"restore_{book.id}_b")
        first = auth_client.post(
            "/api/user/import", json=backup, headers=_headers(other["access_token"])
        ).json()
        second = auth_client.post(
            "/api/user/import", json=backup, headers=_headers(other["access_token"])
        ).json()

        assert first["records_new"] == 2
        assert second["records_new"] == 0
        assert second["records_merged"] == 2
        assert second["sessions_added"] == 0
        assert second["sessions_skipped"] == 1

        restored = auth_client.get(
            "/api/user/export", headers=_headers(other["access_token"])
        ).json()
        assert len(restored["word_records"]) == 2
        assert len(restored["sessions"]) == 1

    def test_merge_takes_stronger_state(self, auth_client: TestClient, db: Session,
                                        user_id: int, book: WordBook):
        # 当前账号已有一条 learning 记录
        _complete_group(auth_client, book.id, size=1)
        _reopen(db)
        record = db.scalars(
            select(UserWordRecord).where(UserWordRecord.user_id == user_id)
        ).first()
        assert record is not None
        word = record.word.word
        record.status = "learning"
        record.wrong_count = 0
        record.ease_stage = 1
        db.commit()

        payload = auth_client.get("/api/user/export").json()
        payload["word_records"] = [
            {
                "wordbook": book.code,
                "word": word,
                "status": "wrong",
                "wrong_count": 5,
                "right_count": 2,
                "ease_stage": 0,
            }
        ]
        payload["sessions"] = []
        payload["chat_messages"] = []

        result = auth_client.post("/api/user/import", json=payload).json()

        assert result["records_new"] == 0
        assert result["records_merged"] == 1

        _reopen(db)
        merged = db.scalars(
            select(UserWordRecord).where(UserWordRecord.user_id == user_id)
        ).first()
        assert merged is not None
        assert merged.status == "wrong"
        assert merged.wrong_count == 5
        assert merged.right_count == 2
        # 记忆强度取较大者，不会因为导入一份旧备份而倒退
        assert merged.ease_stage == 1

    def test_unmatched_words_are_counted_not_fatal(self, auth_client: TestClient,
                                                   book: WordBook):
        _complete_group(auth_client, book.id, size=2)
        backup = auth_client.get("/api/user/export").json()
        backup["word_records"].append(
            {"wordbook": book.code, "word": "zzz-not-in-any-book", "status": "learning"}
        )
        backup["word_records"].append(
            {"wordbook": "gone-book", "word": "abandon", "status": "learning"}
        )

        other = _sign_up(auth_client, f"restore_{book.id}_c")
        result = auth_client.post(
            "/api/user/import", json=backup, headers=_headers(other["access_token"])
        ).json()

        assert result["records_new"] == 2
        assert result["words_unmatched"] == 2

    def test_streak_recomputed_from_merged_sessions(self, auth_client: TestClient,
                                                    book: WordBook):
        # 备份里带着一个 3 天前的会话，连续天数必须按日期重算而非照搬 9
        _complete_group(auth_client, book.id, size=1)
        backup = auth_client.get("/api/user/export").json()
        backup["consecutive_days"] = 9
        backup["last_checkin_date"] = stats_service.today_utc().isoformat()
        backup["sessions"] = [
            {
                "wordbook": book.code,
                "mode": "normal",
                "total": 1,
                "correct": 0,
                "wrong": 1,
                "duration_ms": 1000,
                "practiced_on": (
                    stats_service.today_utc().replace(day=1)
                ).isoformat(),
            }
        ]

        other = _sign_up(auth_client, f"restore_{book.id}_d")
        result = auth_client.post(
            "/api/user/import", json=backup, headers=_headers(other["access_token"])
        ).json()

        # 只有一天的会话：连续 1 天，而不是备份里写的 9
        assert result["consecutive_days"] == 1

    def test_rollback_on_failure_leaves_account_untouched(
        self, auth_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch,
        book: WordBook
    ):
        _complete_group(auth_client, book.id, size=1)
        backup = auth_client.get("/api/user/export").json()

        # 补一条当前账号尚未练过的词：否则导入自己的备份本就什么都不写，
        # 回滚与否在导出结果上无法区分
        _reopen(db)
        used = {item["word"] for item in backup["word_records"]}
        extra = next(
            word
            for word in db.scalars(select(Word).where(Word.wordbook_id == book.id)).all()
            if word.word not in used
        )
        backup["word_records"].append(
            {"wordbook": book.code, "word": extra.word, "status": "mastered"}
        )

        def boom(*_args, **_kwargs):
            raise RuntimeError("forced failure")

        monkeypatch.setattr(backup_service.stats_service, "recompute_streak", boom)
        # TestClient 会把未捕获异常原样抛回测试侧，拿不到 500 响应体
        with pytest.raises(RuntimeError):
            auth_client.post("/api/user/import", json=backup)

        monkeypatch.undo()
        after = auth_client.get("/api/user/export").json()
        # 整个导入必须回滚，不能留下这条新词
        assert all(item["word"] != extra.word for item in after["word_records"])

    def test_rejected_import_writes_nothing(self, auth_client: TestClient,
                                            book: WordBook):
        _complete_group(auth_client, book.id, size=2)
        backup = auth_client.get("/api/user/export").json()
        other = _sign_up(auth_client, f"restore_{book.id}_e")

        bad = json.loads(json.dumps(backup))
        bad["version"] = 99
        auth_client.post(
            "/api/user/import", json=bad, headers=_headers(other["access_token"])
        )

        restored = auth_client.get(
            "/api/user/export", headers=_headers(other["access_token"])
        ).json()
        assert restored["word_records"] == []
        assert restored["sessions"] == []


class TestGuestMigrationStillWorks:
    def test_guest_data_survives_import_flow(self, client: TestClient, book: WordBook):
        """导出导入不得影响既有的游客转正迁移路径。"""
        guest = client.post("/api/auth/guest").json()
        guest_id = int(guest["user"]["id"])
        auth = {"Authorization": f"Bearer {guest['access_token']}"}

        start = client.post(
            "/api/practice/start", json={"wordbook_id": book.id, "size": 1}, headers=auth
        ).json()
        for clue in start["clues"]:
            client.post(
                "/api/practice/submit",
                json={
                    "session_id": start["session_id"],
                    "word_id": clue["id"],
                    "answer": "wrong",
                },
                headers=auth,
            )
        client.post(f"/api/practice/finish?session_id={start['session_id']}", headers=auth)

        backup = client.get("/api/user/export", headers=auth).json()
        assert len(backup["word_records"]) == 1

        registered = _sign_up(client, f"guest_export_{guest_id}", guest_id=guest_id)
        assert registered["migrated"] is True

        restored = client.get(
            "/api/user/export", headers=_headers(registered["access_token"])
        ).json()
        assert len(restored["word_records"]) == 1
        assert restored["consecutive_days"] == 1


class TestSessionRows:
    def test_sessions_written_for_imported_backup(self, auth_client: TestClient,
                                                  db: Session, user_id: int,
                                                  book: WordBook):
        _complete_group(auth_client, book.id, size=1)
        backup = auth_client.get("/api/user/export").json()
        other = _sign_up(auth_client, f"restore_{book.id}_f")
        other_id = int(other["user"]["id"])

        auth_client.post(
            "/api/user/import", json=backup, headers=_headers(other["access_token"])
        )

        _reopen(db)
        rows = list(
            db.scalars(
                select(PracticeSessionRecord).where(
                    PracticeSessionRecord.user_id == other_id
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].wordbook_id == book.id
        assert rows[0].practiced_on == stats_service.today_utc()

    def test_import_does_not_touch_account_fields(self, auth_client: TestClient,
                                                  db: Session, user_id: int):
        """导入不得触碰密码哈希等账号字段。"""
        before = auth_client.get("/api/auth/me").json()

        auth_client.post("/api/user/import", json=auth_client.get("/api/user/export").json())

        _reopen(db)
        user = db.get(User, user_id)
        assert user is not None
        assert user.username == before["username"]
        assert user.is_guest is False
