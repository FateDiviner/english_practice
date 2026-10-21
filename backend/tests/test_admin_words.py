"""管理端词书与词条管理接口测试。

两条红线：批量导入先校验后入库、任一条不通过整批不写；
词条物理删除只在零用户引用时允许，否则只能下架。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from app.models.record import UserWordRecord
from app.models.word import Word
from app.models.wordbook import WordBook
from tests.admin_helpers import (
    good_book,
    good_word,
    headers,
    make_admin,
    make_user,
    unique_name,
)


def _admin_token(db: Session, client: TestClient) -> str:
    return make_admin(db, client, unique_name("wa_admin"))["access_token"]


def _create_book(client: TestClient, token: str, **overrides) -> dict:
    payload = good_book(**overrides) if overrides else good_book()
    response = client.post("/api/admin/wordbooks", json=payload, headers=headers(token))
    assert response.status_code == 200, response.text
    return response.json()


class TestPermissionGate:
    def test_plain_user_403(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("wa_gate_admin"))
        plain = make_user(db, client, unique_name("wa_gate_user"))
        response = client.get("/api/admin/wordbooks", headers=headers(plain["access_token"]))
        assert response.status_code == 403


class TestWordbookCrud:
    def test_create_and_list(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        created = _create_book(client, token, code=unique_name("wb_new")[:32])
        assert created["status"] == STATUS_ACTIVE
        assert created["total_words"] == 0

        listing = client.get("/api/admin/wordbooks", headers=headers(token)).json()
        assert any(item["id"] == created["id"] for item in listing)

    def test_duplicate_code_409(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        code = unique_name("wb_dup")[:32]
        _create_book(client, token, code=code)
        response = client.post("/api/admin/wordbooks", json=good_book(code=code),
                               headers=headers(token))
        assert response.status_code == 409

    def test_edit_metadata(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        created = _create_book(client, token, code=unique_name("wb_edit")[:32])
        response = client.patch(
            f"/api/admin/wordbooks/{created['id']}",
            json={"title": "改过的标题", "difficulty": "hard"},
            headers=headers(token),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "改过的标题"
        assert response.json()["difficulty"] == "hard"

    def test_archive_then_restore(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        created = _create_book(client, token, code=unique_name("wb_arch")[:32])

        archived = client.patch(
            f"/api/admin/wordbooks/{created['id']}",
            json={"status": STATUS_ARCHIVED},
            headers=headers(token),
        )
        assert archived.json()["status"] == STATUS_ARCHIVED

        restored = client.patch(
            f"/api/admin/wordbooks/{created['id']}",
            json={"status": STATUS_ACTIVE},
            headers=headers(token),
        )
        assert restored.json()["status"] == STATUS_ACTIVE

    def test_archived_book_hidden_from_users(self, client: TestClient, db: Session) -> None:
        """下架后用户端要完全看不见，但管理端必须还看得见。"""
        admin_token = _admin_token(db, client)
        created = _create_book(client, admin_token, code=unique_name("wb_hide")[:32])
        client.patch(
            f"/api/admin/wordbooks/{created['id']}",
            json={"status": STATUS_ARCHIVED},
            headers=headers(admin_token),
        )

        user_view = client.get("/api/wordbooks").json()
        assert all(item["code"] != created["code"] for item in user_view)

        admin_view = client.get("/api/admin/wordbooks", headers=headers(admin_token)).json()
        assert any(item["code"] == created["code"] for item in admin_view)


class TestWordCrud:
    def _book_with_word(self, client: TestClient, token: str) -> tuple[int, int]:
        book = _create_book(client, token, code=unique_name("wb_words")[:32])
        created = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(),
            headers=headers(token),
        )
        assert created.status_code == 200, created.text
        return book["id"], created.json()["id"]

    def _set_status(self, client: TestClient, token: str, word_id: int, status: str) -> None:
        response = client.put(
            f"/api/admin/words/{word_id}/status",
            params={"status": status},
            headers=headers(token),
        )
        assert response.status_code == 200, response.text

    def _find_book(self, client: TestClient, token: str, book_id: int) -> dict:
        listing = client.get("/api/admin/wordbooks", headers=headers(token)).json()
        return next(item for item in listing if item["id"] == book_id)

    def test_create_word_updates_total(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book_id, _ = self._book_with_word(client, token)
        listing = client.get("/api/admin/wordbooks", headers=headers(token)).json()
        book = next(item for item in listing if item["id"] == book_id)
        assert book["total_words"] == 1

    def test_invalid_word_422(self, client: TestClient, db: Session) -> None:
        """在线录入也要过同一份校验规则，不能「测试过了但页面能存进脏数据」。"""
        token = _admin_token(db, client)
        book = _create_book(client, token, code=unique_name("wb_bad")[:32])
        response = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(phonetic="no-slashes", translation="give up"),
            headers=headers(token),
        )
        assert response.status_code == 422

    def test_duplicate_word_409(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book_id, _ = self._book_with_word(client, token)
        response = client.post(
            f"/api/admin/wordbooks/{book_id}/words",
            json=good_word(),
            headers=headers(token),
        )
        assert response.status_code == 409

    def test_archive_word_excluded_from_total(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book_id, word_id = self._book_with_word(client, token)

        archived = client.put(
            f"/api/admin/words/{word_id}/status",
            params={"status": STATUS_ARCHIVED},
            headers=headers(token),
        )
        assert archived.status_code == 200, archived.text

        listing = client.get("/api/admin/wordbooks", headers=headers(token)).json()
        book = next(item for item in listing if item["id"] == book_id)
        # total_words 只算可用词，与练习进度的分母口径一致
        assert book["total_words"] == 0
        assert book["archived_words"] == 1

    def test_total_refreshes_after_reactivate(self, client: TestClient, db: Session) -> None:
        """回归：会话是 autoflush=False，统计前必须 flush。

        否则刚下架的词仍会被 COUNT 成可用，total_words 永远刷不下来。
        """
        token = _admin_token(db, client)
        book_id, word_id = self._book_with_word(client, token)
        self._set_status(client, token, word_id, STATUS_ARCHIVED)
        self._set_status(client, token, word_id, STATUS_ACTIVE)

        book = self._find_book(client, token, book_id)
        assert book["total_words"] == 1
        assert book["archived_words"] == 0


class TestPurgeGuard:
    def test_purge_blocked_when_referenced(self, client: TestClient, db: Session) -> None:
        """有用户练习记录引用时只能下架，物理删除会把用户的历史一起级联清掉。"""
        token = _admin_token(db, client)
        owner = make_user(db, client, unique_name("wa_owner"))
        book = _create_book(client, token, code=unique_name("wb_purge")[:32])
        created = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(),
            headers=headers(token),
        ).json()
        db.add(UserWordRecord(user_id=owner["user"]["id"], word_id=created["id"],
                              status="learning"))
        db.commit()

        response = client.delete(
            f"/api/admin/words/{created['id']}", params={"purge": "true"}, headers=headers(token)
        )
        assert response.status_code == 409
        assert "下架" in response.json()["detail"]
        assert db.get(Word, created["id"]) is not None

    def test_purge_allowed_when_unreferenced(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = _create_book(client, token, code=unique_name("wb_purge_ok")[:32])
        created = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(),
            headers=headers(token),
        ).json()

        response = client.delete(
            f"/api/admin/words/{created['id']}", params={"purge": "true"}, headers=headers(token)
        )
        assert response.status_code == 200
        assert response.json()["purged"] is True
        assert db.get(Word, created["id"]) is None

    def test_delete_without_purge_archives(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = _create_book(client, token, code=unique_name("wb_del_arch")[:32])
        created = client.post(
            f"/api/admin/wordbooks/{book['id']}/words",
            json=good_word(),
            headers=headers(token),
        ).json()

        response = client.delete(f"/api/admin/words/{created['id']}", headers=headers(token))
        assert response.json()["archived"] is True
        assert db.get(Word, created["id"]).status == STATUS_ARCHIVED


class TestImport:
    def _import(self, client: TestClient, token: str, payload):
        return client.post(
            "/api/admin/wordbooks/import", json=payload, headers=headers(token)
        )

    def test_import_applies_when_valid(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        code = unique_name("wb_imp")[:32]
        response = self._import(client, token, good_book(code=code))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["applied"] is True
        assert body["words_created"] == 1
        assert (
            db.scalar(select(func.count()).select_from(Word).join(
                WordBook, Word.wordbook_id == WordBook.id
            ).where(WordBook.code == code))
            == 1
        )

    def test_invalid_batch_writes_nothing(self, client: TestClient, db: Session) -> None:
        """任一条不通过则整批拒绝，绝不「先入库再修」。"""
        token = _admin_token(db, client)
        code = unique_name("wb_imp_bad")[:32]
        payload = good_book(
            code=code, words=[good_word(), good_word(word="ephemeral", phonetic="oops")]
        )
        response = self._import(client, token, payload)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "issues" in detail
        assert any("ephemeral" in issue["message"] for issue in detail["issues"])
        assert db.scalar(
            select(func.count()).select_from(WordBook).where(WordBook.code == code)
        ) == 0

    def test_issue_field_is_locatable(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        payload = good_book(
            code=unique_name("wb_imp_loc")[:32],
            words=[good_word(), good_word(), good_word(phonetic="oops")],
        )
        response = self._import(client, token, payload)
        assert response.status_code == 422
        fields = [issue["field"] for issue in response.json()["detail"]["issues"]]
        assert any(field.startswith("words[2]") for field in fields)

    def test_reimport_updates_existing(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        code = unique_name("wb_reimp")[:32]
        assert self._import(client, token, good_book(code=code)).status_code == 200

        updated = good_book(
            code=code,
            title="第二次导入的标题",
            words=[good_word(), good_word(word="ephemeral", phonetic="/ɪˈfem(ə)rəl/",
                                          translation="adj. 短暂的",
                                          example_en="Fame is ephemeral.",
                                          example_cn="名声是短暂的。")],
        )
        response = self._import(client, token, updated)
        assert response.status_code == 200, response.text
        assert response.json()["books_updated"] == 1
        assert response.json()["words_created"] == 1

        book = db.scalar(select(WordBook).where(WordBook.code == code))
        assert book.title == "第二次导入的标题"

    def test_oversized_payload_413(self, client: TestClient, db: Session) -> None:
        """体积上限按 raw body 判定，与字段长度校验是两件事。"""
        token = _admin_token(db, client)
        filler = "x" * 120_000
        payload = good_book(
            code=unique_name("wb_big")[:32],
            words=[
                good_word(word=f"w{i:04d}", example_en=f"Word w{i:04d} {filler}",
                          example_cn="一个例句。")
                for i in range(20)
            ],
        )
        response = self._import(client, token, payload)
        assert response.status_code == 413


class TestImportWords:
    """向指定词书批量导入词条数组。"""

    def _create_book(self, client: TestClient, token: str, code: str) -> dict:
        return _create_book(client, token, code=code)

    def _import_words(self, client: TestClient, token: str, book_id: int, payload):
        return client.post(
            f"/api/admin/wordbooks/{book_id}/words/import",
            json=payload,
            headers=headers(token),
        )

    def test_import_into_book_creates_words(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = self._create_book(client, token, code=unique_name("wi_new")[:32])
        response = self._import_words(
            client,
            token,
            book["id"],
            [
                good_word(),
                good_word(
                    word="ephemeral",
                    example_en="Fame is ephemeral.",
                    example_cn="名声是短暂的。",
                ),
            ],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["applied"] is True
        assert body["words_created"] == 2
        assert body["words_total"] == 2

        words = db.scalars(
            select(Word).where(Word.wordbook_id == book["id"]).order_by(Word.sequence)
        ).all()
        assert len(words) == 2
        assert words[0].word == "abandon"
        assert words[1].word == "ephemeral"

    def test_invalid_word_rejects_entire_batch(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = self._create_book(client, token, code=unique_name("wi_bad")[:32])
        payload = [good_word(), good_word(word="ephemeral", phonetic="oops")]
        response = self._import_words(client, token, book["id"], payload)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "issues" in detail
        assert any("ephemeral" in issue["message"] for issue in detail["issues"])
        # 整批不写库：一条都没落
        assert db.scalar(
            select(func.count()).select_from(Word).where(Word.wordbook_id == book["id"])
        ) == 0

    def test_missing_book_404(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = self._import_words(client, token, 999_999, [good_word()])
        assert response.status_code == 404

    def test_reimport_updates_existing(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = self._create_book(client, token, code=unique_name("wi_re")[:32])
        assert self._import_words(client, token, book["id"], [good_word()]).status_code == 200

        updated = good_word(
            word="abandon",
            phonetic="/əˈbændən/",
            translation="v. 放弃，抛弃",
            example_en="They abandoned the plan.",
            example_cn="他们放弃了那个计划。",
        )
        response = self._import_words(client, token, book["id"], [updated])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["words_updated"] == 1
        assert body["words_created"] == 0

        words = db.scalars(
            select(Word).where(Word.wordbook_id == book["id"])
        ).all()
        assert len(words) == 1
        assert words[0].translation == "v. 放弃，抛弃"

    def test_issue_field_is_locatable(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        book = self._create_book(client, token, code=unique_name("wi_loc")[:32])
        payload = [good_word(), good_word(), good_word(phonetic="oops")]
        response = self._import_words(client, token, book["id"], payload)
        assert response.status_code == 422
        fields = [issue["field"] for issue in response.json()["detail"]["issues"]]
        assert any(field.startswith("words[2]") for field in fields)

    def test_duplicate_word_in_batch_rejected(self, client: TestClient, db: Session) -> None:
        """同一批文件里重复出现的词必须整批拒绝，不能插入两条。"""
        token = _admin_token(db, client)
        book = self._create_book(client, token, code=unique_name("wi_dup")[:32])
        payload = [good_word(), good_word(word="ABANDON")]
        response = self._import_words(client, token, book["id"], payload)

        assert response.status_code == 422
        issues = response.json()["detail"]["issues"]
        assert any(issue["rule"] == "word_duplicate" for issue in issues)
        assert db.scalar(
            select(func.count()).select_from(Word).where(Word.wordbook_id == book["id"])
        ) == 0


class TestExport:
    def test_export_matches_seed_shape(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        code = unique_name("wb_exp")[:32]
        imported = client.post(
            "/api/admin/wordbooks/import", json=good_book(code=code), headers=headers(token)
        )
        assert imported.status_code == 200, imported.text

        listing = client.get("/api/admin/wordbooks", headers=headers(token)).json()
        book_id = next(item["id"] for item in listing if item["code"] == code)

        response = client.get(
            f"/api/admin/wordbooks/{book_id}/export", headers=headers(token)
        )
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"code", "title", "description", "difficulty", "words"}
        assert payload["code"] == code
        assert payload["words"][0]["word"] == "abandon"
