"""管理端词库：查询、增改、下架、批量导入与导出。"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from core.models.record import UserWordRecord
from core.models.word import Word
from core.models.wordbook import WordBook


def _reopen(db: Session) -> None:
    db.rollback()


@pytest.fixture()
def scratch_code() -> str:
    """词书 code 必须随机，否则跨用例会撞 409。"""
    return f"scratch_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def scratch_book(client: TestClient, admin: dict, scratch_code: str, db: Session) -> dict:
    """临时词书：本组用例会下架与删除数据，绝不能碰内置词书。"""
    response = client.post(
        "/api/admin/wordbooks",
        json={
            "code": scratch_code,
            "title": "临时词书",
            "description": "词库管理用例专用",
            "difficulty": "test",
        },
        headers=admin["headers"],
    )
    assert response.status_code == 200, response.text
    book = response.json()
    yield book

    _reopen(db)
    word_ids = select(Word.id).where(Word.wordbook_id == book["id"])
    db.query(UserWordRecord).filter(UserWordRecord.word_id.in_(word_ids)).delete()
    db.query(Word).filter(Word.wordbook_id == book["id"]).delete()
    db.query(WordBook).where(WordBook.id == book["id"]).delete()
    db.commit()


@pytest.fixture(autouse=True)
def _cleanup_scratch_books(db: Session):
    """跑完清掉本文件创建的临时词书。

    词书 code 用前缀筛选而不用 LIKE：`_` 在 LIKE 里是通配符，
    `scratch_%` 会误伤 `scratchbook` 之类的名字。
    """
    yield
    _reopen(db)
    books = [
        book
        for book in db.scalars(select(WordBook)).all()
        if str(book.code).startswith("scratch_")
    ]
    if not books:
        return
    book_ids = [book.id for book in books]
    word_ids = list(
        db.scalars(select(Word.id).where(Word.wordbook_id.in_(book_ids))).all()
    )
    if word_ids:
        db.query(UserWordRecord).filter(UserWordRecord.word_id.in_(word_ids)).delete()
        db.query(Word).filter(Word.id.in_(word_ids)).delete()
    db.query(WordBook).filter(WordBook.id.in_(book_ids)).delete()
    db.commit()


def _good_word(stem: str = "alpha") -> dict:
    return {
        "word": stem,
        "phonetic": "/ˈælfə/",
        "translation": "n. 希腊语的第一个字母",
        "example_en": f"The {stem} channel carries the strongest signal.",
        "example_cn": "这个频道信号最强。",
    }


def _add_word(client: TestClient, admin: dict, book_id: int, **overrides) -> dict:
    # 换词必须连例句一起重建，否则校验器会以「例句未体现目标词」拒绝
    stem = overrides.pop("word", "alpha")
    payload = {**_good_word(stem), **overrides}
    response = client.post(
        f"/api/admin/wordbooks/{book_id}/words", json=payload, headers=admin["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestWordBookAdmin:
    def test_list_includes_scratch_and_counts(self, client: TestClient, admin: dict,
                                              scratch_book: dict):
        books = client.get("/api/admin/wordbooks", headers=admin["headers"]).json()

        target = next(item for item in books if item["id"] == scratch_book["id"])
        assert target["status"] == STATUS_ACTIVE
        assert target["total_words"] == 0
        assert target["archived_words"] == 0
        assert target["active_users"] == 0

    def test_duplicate_code_rejected(self, client: TestClient, admin: dict,
                                     scratch_book: dict, scratch_code: str):
        response = client.post(
            "/api/admin/wordbooks",
            json={"code": scratch_code, "title": "重复"},
            headers=admin["headers"],
        )

        assert response.status_code == 409

    def test_invalid_code_rejected(self, client: TestClient, admin: dict):
        response = client.post(
            "/api/admin/wordbooks",
            json={"code": "Bad Code!", "title": "x"},
            headers=admin["headers"],
        )

        assert response.status_code == 422

    def test_update_metadata_and_archive(self, client: TestClient, admin: dict,
                                         scratch_book: dict):
        updated = client.patch(
            f"/api/admin/wordbooks/{scratch_book['id']}",
            json={"title": "改过的书名", "status": "archived"},
            headers=admin["headers"],
        )

        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["title"] == "改过的书名"
        assert body["status"] == STATUS_ARCHIVED

        # 下架后仍在管理端可见，只是状态变了
        books = client.get("/api/admin/wordbooks", headers=admin["headers"]).json()
        assert any(item["id"] == scratch_book["id"] and item["status"] == "archived"
                   for item in books)

    def test_update_with_no_fields_rejected(self, client: TestClient, admin: dict,
                                            scratch_book: dict):
        response = client.patch(
            f"/api/admin/wordbooks/{scratch_book['id']}",
            json={},
            headers=admin["headers"],
        )

        assert response.status_code == 400


class TestWordAdmin:
    def test_create_word_and_counts(self, client: TestClient, admin: dict,
                                    scratch_book: dict):
        created = _add_word(client, admin, scratch_book["id"])

        assert created["word"] == "alpha"
        assert created["status"] == STATUS_ACTIVE

        page = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/words", headers=admin["headers"]
        ).json()
        assert page["total"] == 1

        book = next(
            item
            for item in client.get("/api/admin/wordbooks", headers=admin["headers"]).json()
            if item["id"] == scratch_book["id"]
        )
        assert book["total_words"] == 1

    def test_create_word_validates_like_the_shared_rules(self, client: TestClient,
                                                         admin: dict, scratch_book: dict):
        """管理端录入必须走同一份红线，否则「测试过了但页面能存脏数据」。"""
        response = client.post(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            json={**_good_word(), "phonetic": "alpha"},
            headers=admin["headers"],
        )

        assert response.status_code == 422
        assert "音标" in response.json()["detail"]

        bad_translation = client.post(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            json={**_good_word(), "translation": "放弃"},
            headers=admin["headers"],
        )
        assert bad_translation.status_code == 422

    def test_duplicate_word_rejected(self, client: TestClient, admin: dict,
                                     scratch_book: dict):
        _add_word(client, admin, scratch_book["id"])
        response = client.post(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            json=_good_word(),
            headers=admin["headers"],
        )

        assert response.status_code == 409

    def test_search_and_status_filter(self, client: TestClient, admin: dict,
                                      scratch_book: dict):
        _add_word(client, admin, scratch_book["id"], word="beta")
        _add_word(client, admin, scratch_book["id"], word="gamma")
        archived = _add_word(client, admin, scratch_book["id"], word="delta")

        client.put(
            f"/api/admin/words/{archived['id']}/status",
            params={"status": "archived"},
            headers=admin["headers"],
        )

        active = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            params={"status": "active"},
            headers=admin["headers"],
        ).json()
        assert {item["word"] for item in active["items"]} == {"beta", "gamma"}

        all_words = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            headers=admin["headers"],
        ).json()
        assert all_words["total"] == 3

        searched = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            params={"search": "bet"},
            headers=admin["headers"],
        ).json()
        assert [item["word"] for item in searched["items"]] == ["beta"]

    def test_update_word_restores_active(self, client: TestClient, admin: dict,
                                         scratch_book: dict):
        created = _add_word(client, admin, scratch_book["id"])
        client.put(
            f"/api/admin/words/{created['id']}/status",
            params={"status": "archived"},
            headers=admin["headers"],
        )

        updated = client.patch(
            f"/api/admin/words/{created['id']}",
            json={**_good_word(), "translation": "n. 修正后的释义"},
            headers=admin["headers"],
        )

        assert updated.status_code == 200, updated.text
        assert updated.json()["status"] == STATUS_ACTIVE
        assert updated.json()["translation"] == "n. 修正后的释义"

    def test_archive_word_is_default_delete_behaviour(
        self, client: TestClient, admin: dict, scratch_book: dict
    ):
        created = _add_word(client, admin, scratch_book["id"])

        response = client.delete(
            f"/api/admin/words/{created['id']}", headers=admin["headers"]
        )

        assert response.status_code == 200
        assert response.json() == {"archived": True}

        page = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/words",
            headers=admin["headers"],
        ).json()
        assert page["items"][0]["status"] == STATUS_ARCHIVED

    def test_purge_blocked_when_referenced(
        self, client: TestClient, admin: dict, scratch_book: dict, db: Session
    ):
        created = _add_word(client, admin, scratch_book["id"])
        _reopen(db)
        db.add(
            UserWordRecord(
                user_id=admin["user_id"],
                word_id=created["id"],
                status="learning",
                wrong_count=1,
                right_count=0,
                ease_stage=1,
            )
        )
        db.commit()

        response = client.delete(
            f"/api/admin/words/{created['id']}",
            params={"purge": "true"},
            headers=admin["headers"],
        )

        assert response.status_code == 409
        assert "下架" in response.json()["detail"]

    def test_purge_allowed_when_unreferenced(
        self, client: TestClient, admin: dict, scratch_book: dict, db: Session
    ):
        created = _add_word(client, admin, scratch_book["id"])

        response = client.delete(
            f"/api/admin/words/{created['id']}",
            params={"purge": "true"},
            headers=admin["headers"],
        )

        assert response.status_code == 200
        assert response.json() == {"purged": True}
        _reopen(db)
        assert db.get(Word, created["id"]) is None


class TestImportExport:
    def test_import_valid_file_creates_book_and_words(
        self, client: TestClient, admin: dict, scratch_code: str, db: Session
    ):
        payload = {
            "code": scratch_code,
            "title": "导入来的书",
            "description": "d",
            "difficulty": "test",
            "words": [_good_word("omega"), _good_word("sigma")],
        }

        response = client.post(
            "/api/admin/wordbooks/import", json=payload, headers=admin["headers"]
        )

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["applied"] is True
        assert result["books_created"] == 1
        assert result["words_created"] == 2
        assert result["issues"] == []

        _reopen(db)
        book = db.scalar(select(WordBook).where(WordBook.code == scratch_code))
        assert book is not None
        assert book.total_words == 2

    def test_reimport_is_idempotent_and_updates_content(
        self, client: TestClient, admin: dict, scratch_code: str, db: Session
    ):
        payload = {
            "code": scratch_code,
            "title": "导入来的书",
            "words": [_good_word("omega")],
        }
        first = client.post(
            "/api/admin/wordbooks/import", json=payload, headers=admin["headers"]
        ).json()
        assert first["words_created"] == 1

        payload["words"][0]["translation"] = "n. 修改过的释义"
        second = client.post(
            "/api/admin/wordbooks/import", json=payload, headers=admin["headers"]
        ).json()

        assert second["applied"] is True
        assert second["books_created"] == 0
        assert second["books_updated"] == 1
        assert second["words_created"] == 0
        assert second["words_updated"] == 1

        _reopen(db)
        book = db.scalar(select(WordBook).where(WordBook.code == scratch_code))
        assert book is not None
        # 必须限定在本用例的书里：其它用例也可能留下同名词条
        word = db.scalar(
            select(Word).where(Word.word == "omega", Word.wordbook_id == book.id)
        )
        assert word is not None
        assert word.translation == "n. 修改过的释义"

    def test_dirty_file_writes_nothing_at_all(
        self, client: TestClient, admin: dict, scratch_code: str, db: Session
    ):
        """核心约束：一条不通过就整批拒绝，绝不先入库再修。"""
        payload = {
            "code": scratch_code,
            "title": "脏数据",
            "words": [
                _good_word("clean"),
                {**_good_word("broken"), "phonetic": "broken"},
                {**_good_word("nophonetic"), "translation": "no-pos"},
            ],
        }

        response = client.post(
            "/api/admin/wordbooks/import", json=payload, headers=admin["headers"]
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "未写入任何数据" in detail["message"]
        assert len(detail["issues"]) >= 2

        # 错误必须能定位到第几条、哪个词
        fields = [issue["field"] for issue in detail["issues"]]
        assert any(field.startswith("words[1].") for field in fields)
        assert any("broken" in issue["message"] for issue in detail["issues"])

        _reopen(db)
        assert db.scalar(select(WordBook).where(WordBook.code == scratch_code)) is None
        assert db.scalar(select(Word).where(Word.word == "clean")) is None

    def test_accepts_array_of_books(self, client: TestClient, admin: dict,
                                    scratch_code: str, db: Session):
        payload = [
            {"code": scratch_code, "title": "a", "words": [_good_word()]},
            {"code": f"{scratch_code}_2", "title": "b", "words": [_good_word("beta")]},
        ]

        response = client.post(
            "/api/admin/wordbooks/import", json=payload, headers=admin["headers"]
        )

        assert response.status_code == 200, response.text
        assert response.json()["books_created"] == 2

    def test_malformed_json_rejected(self, client: TestClient, admin: dict):
        response = client.post(
            "/api/admin/wordbooks/import",
            content="not json at all",
            headers={"Authorization": admin["headers"]["Authorization"],
                     "Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_export_is_data_file_shaped_and_active_only(
        self, client: TestClient, admin: dict, scratch_book: dict
    ):
        _add_word(client, admin, scratch_book["id"], word="keep")
        archived = _add_word(client, admin, scratch_book["id"], word="drop")
        client.put(
            f"/api/admin/words/{archived['id']}/status",
            params={"status": "archived"},
            headers=admin["headers"],
        )

        exported = client.get(
            f"/api/admin/wordbooks/{scratch_book['id']}/export",
            headers=admin["headers"],
        ).json()

        # 必须与 data/*.json 同构，才能直接写回仓库
        assert set(exported) == {"code", "title", "description", "difficulty", "words"}
        assert [item["word"] for item in exported["words"]] == ["keep"]
        assert set(exported["words"][0]) == {
            "word", "phonetic", "translation", "example_en", "example_cn",
        }

    def test_export_import_roundtrip(
        self, client: TestClient, admin: dict, scratch_code: str
    ):
        source = {
            "code": scratch_code,
            "title": "往返",
            "description": "d",
            "difficulty": "t",
            "words": [_good_word("omega")],
        }
        client.post("/api/admin/wordbooks/import", json=source, headers=admin["headers"])
        book_id = next(
            item["id"]
            for item in client.get("/api/admin/wordbooks", headers=admin["headers"]).json()
            if item["code"] == scratch_code
        )

        exported = client.get(
            f"/api/admin/wordbooks/{book_id}/export", headers=admin["headers"]
        ).json()

        assert exported == json.loads(json.dumps(source, ensure_ascii=False))


class TestPermissionBoundary:
    def test_word_endpoints_require_admin(self, client: TestClient, member: dict):
        assert client.get("/api/admin/wordbooks").status_code == 401
        assert (
            client.get("/api/admin/wordbooks", headers=member["headers"]).status_code
            == 403
        )
        assert (
            client.post(
                "/api/admin/wordbooks/import", json={}, headers=member["headers"]
            ).status_code
            == 403
        )
