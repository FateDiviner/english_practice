"""今日复习队列：统计口径、选词范围与拼写防泄漏。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.record import UserWordRecord
from app.models.word import Word
from app.models.wordbook import WordBook
from app.services import scheduler


def _utcnow() -> datetime:
    """与调度器同口径：UTC 且不带时区信息。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today_end(now: datetime) -> datetime:
    return now.replace(hour=23, minute=59, second=59, microsecond=999999)


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


def _take_words(db: Session, book_id: int, count: int) -> list[Word]:
    words = list(
        db.scalars(
            select(Word)
            .where(Word.wordbook_id == book_id)
            .order_by(Word.id)
            .limit(count)
        ).all()
    )
    assert len(words) == count, "内置词书单词数不足，无法构造用例"
    return words


def _seed_record(
    db: Session,
    user_id: int,
    word: Word,
    *,
    due_at: datetime | None,
    status: str = scheduler.STATUS_LEARNING,
    wrong_count: int = 0,
    right_count: int = 0,
) -> UserWordRecord:
    record = UserWordRecord(
        user_id=user_id,
        word_id=word.id,
        status=status,
        wrong_count=wrong_count,
        right_count=right_count,
        ease_stage=1,
        last_practiced=_utcnow(),
        next_review_at=due_at,
    )
    db.add(record)
    db.commit()
    return record


class TestBuildReviewQueue:
    def test_fresh_user_queue_is_empty(self, db: Session, user_id: int, book: WordBook):
        queue = scheduler.build_review_queue(db, user_id, book.id)

        assert queue["wordbook_id"] == book.id
        assert queue["total"] == 0
        assert queue["overdue"] == 0
        assert queue["due_today"] == 0
        assert queue["upcoming_7d"] == 0
        assert queue["preview"] == []

    def test_buckets_are_counted_separately(self, db: Session, user_id: int, book: WordBook):
        words = _take_words(db, book.id, 3)
        now = _utcnow()
        today_end = _today_end(now)

        _seed_record(db, user_id, words[0], due_at=now - timedelta(hours=3))
        _seed_record(db, user_id, words[1], due_at=today_end - timedelta(minutes=5))
        _seed_record(db, user_id, words[2], due_at=today_end + timedelta(days=2))

        queue = scheduler.build_review_queue(db, user_id, book.id)

        assert queue["overdue"] == 1
        assert queue["due_today"] == 1
        assert queue["upcoming_7d"] == 1
        # 未来到期只作提示，绝不计入"今日待复习"
        assert queue["total"] == 2

    def test_null_next_review_counts_as_overdue(self, db: Session, user_id: int, book: WordBook):
        word = _take_words(db, book.id, 1)[0]
        _seed_record(db, user_id, word, due_at=None)

        queue = scheduler.build_review_queue(db, user_id, book.id)

        assert queue["overdue"] == 1
        assert queue["total"] == 1

    def test_preview_never_contains_spelling(self, db: Session, user_id: int, book: WordBook):
        word = _take_words(db, book.id, 1)[0]
        _seed_record(db, user_id, word, due_at=_utcnow() - timedelta(hours=1))

        queue = scheduler.build_review_queue(db, user_id, book.id)

        assert len(queue["preview"]) == 1
        item = queue["preview"][0]
        assert "word" not in item
        # 预览一眼扫过就等于背过，任何字段都不许带回原词拼写
        assert word.word not in json.dumps(queue, ensure_ascii=False)
        assert item["translation"] == word.translation
        assert item["phonetic"] == word.phonetic

    def test_preview_sorted_by_lateness(self, db: Session, user_id: int, book: WordBook):
        words = _take_words(db, book.id, 3)
        now = _utcnow()
        # 第一个词逾期最久，理应排在最前
        _seed_record(db, user_id, words[0], due_at=now - timedelta(days=2))
        _seed_record(db, user_id, words[1], due_at=now - timedelta(minutes=10))
        _seed_record(db, user_id, words[2], due_at=now - timedelta(hours=5))

        queue = scheduler.build_review_queue(db, user_id, book.id)

        preview_ids = [item["word_id"] for item in queue["preview"]]
        assert preview_ids == [words[0].id, words[2].id, words[1].id]

    def test_preview_respects_limit(self, db: Session, user_id: int, book: WordBook):
        words = _take_words(db, book.id, 3)
        now = _utcnow()
        for word in words:
            _seed_record(db, user_id, word, due_at=now - timedelta(hours=1))

        queue = scheduler.build_review_queue(db, user_id, book.id, preview_limit=2)

        assert queue["total"] == 3
        assert len(queue["preview"]) == 2


class TestReviewSessionSelection:
    def test_selects_only_due_words(self, db: Session, user_id: int, book: WordBook):
        words = _take_words(db, book.id, 4)
        now = _utcnow()
        today_end = _today_end(now)
        _seed_record(db, user_id, words[0], due_at=now - timedelta(hours=1))
        _seed_record(db, user_id, words[1], due_at=today_end - timedelta(minutes=1))
        # 未到期与从未学过的词都不得混入
        _seed_record(db, user_id, words[2], due_at=today_end + timedelta(days=10))

        selected = scheduler.select_session_words(db, user_id, book.id, 50, "review")

        assert sorted(word.id for word in selected) == sorted(
            [words[0].id, words[1].id]
        )

    def test_does_not_pad_with_new_words(self, db: Session, user_id: int, book: WordBook):
        word = _take_words(db, book.id, 1)[0]
        _seed_record(db, user_id, word, due_at=_utcnow() - timedelta(hours=1))

        selected = scheduler.select_session_words(db, user_id, book.id, 50, "review")

        # 到期词只有 1 个时就只发 1 个，"今日待复习 N"必须名副其实
        assert len(selected) == 1
        assert selected[0].id == word.id

    def test_orders_most_overdue_first(self, db: Session, user_id: int, book: WordBook):
        words = _take_words(db, book.id, 2)
        now = _utcnow()
        _seed_record(db, user_id, words[0], due_at=now - timedelta(minutes=5))
        _seed_record(db, user_id, words[1], due_at=now - timedelta(days=3))

        selected = scheduler.select_session_words(db, user_id, book.id, 50, "review")

        assert [word.id for word in selected] == [words[1].id, words[0].id]

    def test_due_wrong_words_are_included(self, db: Session, user_id: int, book: WordBook):
        word = _take_words(db, book.id, 1)[0]
        _seed_record(
            db,
            user_id,
            word,
            due_at=_utcnow() - timedelta(hours=2),
            status=scheduler.STATUS_WRONG,
            wrong_count=4,
        )

        selected = scheduler.select_session_words(db, user_id, book.id, 50, "review")

        assert [item.id for item in selected] == [word.id]

    def test_returns_empty_when_nothing_due(self, db: Session, user_id: int, book: WordBook):
        word = _take_words(db, book.id, 1)[0]
        _seed_record(
            db, user_id, word, due_at=_utcnow() + timedelta(days=30)
        )

        assert scheduler.select_session_words(db, user_id, book.id, 50, "review") == []


class TestReviewQueueApi:
    def test_requires_auth(self, client: TestClient):
        response = client.get("/api/practice/review-queue", params={"wordbook_id": 1})

        assert response.status_code == 401

    def test_returns_expected_shape(self, auth_client: TestClient, book: WordBook):
        response = auth_client.get(
            "/api/practice/review-queue", params={"wordbook_id": book.id}
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["wordbook_id"] == book.id
        assert {"total", "overdue", "due_today", "upcoming_7d", "preview"} <= set(body)
        # 新号没有任何练习记录，队列应为空而不是报错
        assert body["total"] == 0
        assert body["preview"] == []

    def test_unknown_wordbook_404(self, auth_client: TestClient):
        response = auth_client.get(
            "/api/practice/review-queue", params={"wordbook_id": 999999}
        )

        assert response.status_code == 404


class TestStartReviewMode:
    def test_starts_with_due_words(self, auth_client: TestClient, db: Session,
                                   user_id: int, book: WordBook):
        words = _take_words(db, book.id, 2)
        now = _utcnow()
        _seed_record(db, user_id, words[0], due_at=now - timedelta(hours=1))
        _seed_record(db, user_id, words[1], due_at=_today_end(now) - timedelta(minutes=1))

        response = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book.id, "size": 10, "mode": "review"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "review"
        assert body["total"] == 2
        assert len(body["clues"]) == 2

    def test_empty_queue_rejected(self, auth_client: TestClient, book: WordBook):
        response = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book.id, "size": 10, "mode": "review"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "暂无到期词，今天的复习任务已完成"

    def test_invalid_mode_rejected(self, auth_client: TestClient, book: WordBook):
        response = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book.id, "size": 10, "mode": "tomorrow"},
        )

        assert response.status_code == 422
