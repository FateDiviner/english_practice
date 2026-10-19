"""软删除：下架词书与词条的三分类过滤矩阵。

必须过滤（对用户隐藏）：词书列表、选词、进度分母、复习队列、开局校验。
必须保留（历史仍可见）：备份导出、错题本、练习结算。
按会话快照：进行中的会话允许答完。

这些用例会真的下架数据，因此一律使用临时词书，绝不触碰内置词书。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.orm import Session

from core.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from core.db import REQUIRED_COLUMNS, _ensure_columns, engine, init_db
from core.models.record import UserWordRecord
from core.models.session import PracticeSessionRecord
from core.models.word import Word
from core.models.wordbook import WordBook
from app.services import scheduler


@pytest.fixture()
def user_id(auth_client: TestClient) -> int:
    return int(auth_client.get("/api/auth/me").json()["id"])


def _reopen(db: Session) -> None:
    db.rollback()


@pytest.fixture()
def scratch_book(db: Session) -> WordBook:
    """临时词书：下架操作只作用于它，跑完即清。"""
    _reopen(db)
    book = WordBook(
        code=f"scratch_{uuid4().hex[:8]}",
        title="临时词书",
        description="软删除用例专用",
        difficulty="test",
        status=STATUS_ACTIVE,
    )
    db.add(book)
    db.flush()
    for index in range(4):
        db.add(
            Word(
                wordbook_id=book.id,
                word=f"scratchword{index}",
                phonetic="/skrætʃ/",
                translation=f"n. 测试词{index}",
                example_en=f"This is scratch word {index}.",
                example_cn=f"这是测试词{index}。",
                sequence=index,
                status=STATUS_ACTIVE,
            )
        )
    db.commit()
    yield book

    _reopen(db)
    word_ids = select(Word.id).where(Word.wordbook_id == book.id)
    db.execute(
        delete(PracticeSessionRecord).where(
            PracticeSessionRecord.wordbook_id == book.id
        )
    )
    db.execute(delete(UserWordRecord).where(UserWordRecord.word_id.in_(word_ids)))
    db.execute(delete(Word).where(Word.wordbook_id == book.id))
    db.execute(delete(WordBook).where(WordBook.id == book.id))
    db.commit()


def _archive_book(db: Session, book_id: int) -> None:
    _reopen(db)
    db.get(WordBook, book_id).status = STATUS_ARCHIVED
    db.commit()


def _archive_word(db: Session, word_id: int) -> None:
    _reopen(db)
    db.get(Word, word_id).status = STATUS_ARCHIVED
    db.commit()


def _take_words(db: Session, book_id: int, count: int) -> list[Word]:
    _reopen(db)
    words = list(
        db.scalars(
            select(Word)
            .where(Word.wordbook_id == book_id, Word.status == STATUS_ACTIVE)
            .order_by(Word.id)
            .limit(count)
        ).all()
    )
    assert len(words) == count
    return words


def _mark_wrong(db: Session, user_id: int, words: list[Word], wrong_count: int = 3) -> None:
    now = datetime.utcnow()
    for word in words:
        db.add(
            UserWordRecord(
                user_id=user_id,
                word_id=word.id,
                status=scheduler.STATUS_WRONG,
                wrong_count=wrong_count,
                right_count=0,
                ease_stage=0,
                last_practiced=now,
                next_review_at=now,
            )
        )
    db.commit()


class TestColumnBackfill:
    def test_legacy_schema_gets_missing_columns(self, tmp_path):
        """create_all 不给老表加列，补齐逻辑必须真的能把缺列加上。"""
        legacy = create_engine(
            f"sqlite:///{tmp_path}/legacy.db",
            connect_args={"check_same_thread": False},
        )
        with legacy.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64))"))
            conn.execute(text("CREATE TABLE words (id INTEGER PRIMARY KEY, word VARCHAR(128))"))
            conn.execute(text("CREATE TABLE wordbooks (id INTEGER PRIMARY KEY, code VARCHAR(32))"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'old_user')"))

        _ensure_columns(legacy)

        with legacy.connect() as conn:
            user_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
            word_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(words)"))}
            role = conn.execute(text("SELECT role FROM users WHERE id = 1")).scalar()

        assert "role" in user_cols
        assert "status" in word_cols
        # 老数据必须拿到默认值，而不是变成 NULL
        assert role == "user"

    def test_backfill_is_idempotent(self):
        init_db()
        init_db()

    def test_required_columns_match_models(self):
        init_db()
        inspector = inspect(engine)
        for table, columns in REQUIRED_COLUMNS.items():
            names = {column["name"] for column in inspector.get_columns(table)}
            assert set(columns) <= names, f"{table} 缺少列 {set(columns) - names}"


class TestArchivedWordBook:
    def test_archived_book_hidden_from_list(self, auth_client: TestClient, db: Session,
                                            scratch_book: WordBook):
        _archive_book(db, scratch_book.id)

        books = auth_client.get("/api/wordbooks").json()

        assert all(item["id"] != scratch_book.id for item in books)

    def test_archived_book_cannot_be_activated(self, auth_client: TestClient, db: Session,
                                               scratch_book: WordBook):
        _archive_book(db, scratch_book.id)

        response = auth_client.post(f"/api/wordbooks/{scratch_book.id}/activate")

        assert response.status_code == 409
        assert "已下架" in response.json()["detail"]

    def test_archived_book_cannot_start_practice(self, auth_client: TestClient, db: Session,
                                                 scratch_book: WordBook):
        _archive_book(db, scratch_book.id)

        response = auth_client.post(
            "/api/practice/start", json={"wordbook_id": scratch_book.id, "size": 2}
        )

        assert response.status_code == 409


class TestArchivedWord:
    def test_archived_word_never_selected(self, db: Session, user_id: int,
                                          scratch_book: WordBook):
        words = _take_words(db, scratch_book.id, 3)
        _archive_word(db, words[0].id)

        selected = scheduler.select_session_words(
            db, user_id, scratch_book.id, 50, "normal"
        )

        assert words[0].id not in [word.id for word in selected]

    def test_archived_word_excluded_from_wrong_book_mode(self, db: Session, user_id: int,
                                                         scratch_book: WordBook):
        words = _take_words(db, scratch_book.id, 2)
        _mark_wrong(db, user_id, words)
        _archive_word(db, words[1].id)

        selected = scheduler.select_session_words(
            db, user_id, scratch_book.id, 50, "wrong_book"
        )

        assert [word.id for word in selected] == [words[0].id]

    def test_archived_word_shrinks_progress_denominator(self, db: Session, user_id: int,
                                                        scratch_book: WordBook):
        words = _take_words(db, scratch_book.id, 3)
        before = scheduler.compute_progress(db, user_id, scratch_book.id)
        _archive_word(db, words[0].id)
        after = scheduler.compute_progress(db, user_id, scratch_book.id)

        assert after["total_words"] == before["total_words"] - 1

    def test_archived_word_leaves_review_queue(self, db: Session, user_id: int,
                                               scratch_book: WordBook):
        word = _take_words(db, scratch_book.id, 1)[0]
        now = datetime.utcnow()
        db.add(
            UserWordRecord(
                user_id=user_id, word_id=word.id, status=scheduler.STATUS_LEARNING,
                wrong_count=0, right_count=0, ease_stage=0,
                last_practiced=now, next_review_at=now - timedelta(hours=2),
            )
        )
        db.commit()
        assert scheduler.build_review_queue(db, user_id, scratch_book.id)["total"] == 1

        _archive_word(db, word.id)

        assert scheduler.build_review_queue(db, user_id, scratch_book.id)["total"] == 0

    def test_archived_word_still_in_wrong_book_list(self, auth_client: TestClient, db: Session,
                                                    user_id: int, scratch_book: WordBook):
        """历史错题必须保留并标注，静默消失会让用户以为数据丢了。"""
        word = _take_words(db, scratch_book.id, 1)[0]
        _mark_wrong(db, user_id, [word], wrong_count=2)
        _archive_word(db, word.id)

        items = auth_client.get("/api/practice/wrong-book").json()["items"]

        assert len(items) == 1
        assert items[0]["word"] == word.word
        assert items[0]["archived"] is True

    def test_active_wrong_book_item_is_not_marked(self, auth_client: TestClient, db: Session,
                                                  user_id: int, scratch_book: WordBook):
        word = _take_words(db, scratch_book.id, 1)[0]
        _mark_wrong(db, user_id, [word], wrong_count=1)

        items = auth_client.get("/api/practice/wrong-book").json()["items"]

        assert items[0]["archived"] is False

    def test_archived_word_still_exported(self, auth_client: TestClient, db: Session,
                                          user_id: int, scratch_book: WordBook):
        """备份必须包含下架词，否则用户导出后导不回来。"""
        word = _take_words(db, scratch_book.id, 1)[0]
        now = datetime.utcnow()
        db.add(
            UserWordRecord(
                user_id=user_id, word_id=word.id, status=scheduler.STATUS_LEARNING,
                wrong_count=0, right_count=1, ease_stage=1,
                last_practiced=now, next_review_at=now,
            )
        )
        db.commit()
        _archive_word(db, word.id)

        records = auth_client.get("/api/user/export").json()["word_records"]

        assert word.word in [item["word"] for item in records]

    def test_in_progress_session_survives_archival(self, auth_client: TestClient, db: Session,
                                                   scratch_book: WordBook):
        """用户正在做的题不能中途被抽走。"""
        start = auth_client.post(
            "/api/practice/start", json={"wordbook_id": scratch_book.id, "size": 2}
        ).json()
        first = start["clues"][0]["id"]
        _archive_word(db, first)

        response = auth_client.post(
            "/api/practice/submit",
            json={
                "session_id": start["session_id"],
                "word_id": first,
                "answer": "abandon",
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["answer"]
