"""学习看板：练习落库、连续打卡与概览统计。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.record import UserWordRecord
from app.models.session import PracticeSessionRecord
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import WordBook
from app.services import stats_service


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _complete_group(
    client: TestClient, book_id: int, size: int = 3, mode: str = "normal"
) -> dict:
    """走完整流程练完一组（全部答错，保证结果确定）。"""
    start = client.post(
        "/api/practice/start",
        json={"wordbook_id": book_id, "size": size, "mode": mode},
    )
    assert start.status_code == 200, start.text
    session = start.json()
    for clue in session["clues"]:
        client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": clue["id"],
                "answer": "definitely-wrong",
            },
        )
    settle = client.post(f"/api/practice/finish?session_id={session['session_id']}")
    assert settle.status_code == 200, settle.text
    return settle.json()


def _reopen(db: Session) -> None:
    """结束本会话的快照事务，才能看见 API 侧刚提交的写入。

    MySQL 默认 REPEATABLE READ：测试会话在第一次查询时就固定了快照，
    之后由应用连接提交的数据在本会话里读不到（SQLite 无此现象，
    只有跑真实 MySQL 时才会暴露）。所有断言前先调用它。
    """
    db.rollback()


def _shift_checkin(db: Session, user_id: int, days_ago: int, streak: int = 5) -> None:
    _reopen(db)
    user = db.get(User, user_id)
    assert user is not None
    user.last_checkin_date = (
        stats_service.today_utc() - timedelta(days=days_ago)
    ).isoformat()
    user.consecutive_days = streak
    db.commit()


def _user(db: Session, user_id: int) -> User:
    _reopen(db)
    user = db.get(User, user_id)
    assert user is not None
    return user


class TestCheckin:
    def test_first_practice_checks_in(self, auth_client: TestClient, db: Session,
                                      user_id: int, book: WordBook):
        _complete_group(auth_client, book.id, size=2)

        user = _user(db, user_id)
        assert user.consecutive_days == 1
        assert user.last_checkin_date == stats_service.today_utc().isoformat()

    def test_checkin_happens_before_finish(self, auth_client: TestClient, db: Session,
                                           user_id: int, book: WordBook):
        # 练到一半退出也算当天练过，不能只在结算时才打卡
        start = auth_client.post(
            "/api/practice/start", json={"wordbook_id": book.id, "size": 2}
        ).json()
        auth_client.post(
            "/api/practice/submit",
            json={
                "session_id": start["session_id"],
                "word_id": start["clues"][0]["id"],
                "answer": "wrong",
            },
        )

        assert _user(db, user_id).consecutive_days == 1

    def test_same_day_is_idempotent(self, auth_client: TestClient, db: Session,
                                    user_id: int, book: WordBook):
        _complete_group(auth_client, book.id, size=2)
        _complete_group(auth_client, book.id, size=2)

        assert _user(db, user_id).consecutive_days == 1

    def test_next_day_extends_streak(self, auth_client: TestClient, db: Session,
                                     user_id: int, book: WordBook):
        _shift_checkin(db, user_id, days_ago=1, streak=5)
        _complete_group(auth_client, book.id, size=2)

        assert _user(db, user_id).consecutive_days == 6

    def test_gap_resets_streak(self, auth_client: TestClient, db: Session,
                               user_id: int, book: WordBook):
        _shift_checkin(db, user_id, days_ago=3, streak=30)
        _complete_group(auth_client, book.id, size=2)

        assert _user(db, user_id).consecutive_days == 1


class TestSessionPersistence:
    def test_finish_records_session(self, auth_client: TestClient, db: Session,
                                    user_id: int, book: WordBook):
        _complete_group(auth_client, book.id, size=3)

        _reopen(db)
        rows = list(
            db.scalars(
                select(PracticeSessionRecord).where(
                    PracticeSessionRecord.user_id == user_id
                )
            ).all()
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.total == 3
        assert row.correct_count == 0
        assert row.wrong_count == 3
        assert row.mode == "normal"
        assert row.practiced_on == stats_service.today_utc()
        assert row.duration_ms >= 0

    def test_review_mode_is_recorded(self, auth_client: TestClient, db: Session,
                                     user_id: int, book: WordBook):
        word = db.scalars(
            select(Word).where(Word.wordbook_id == book.id).order_by(Word.id).limit(1)
        ).first()
        assert word is not None
        now = _utcnow()
        db.add(
            UserWordRecord(
                user_id=user_id,
                word_id=word.id,
                status="learning",
                wrong_count=0,
                right_count=0,
                ease_stage=1,
                last_practiced=now,
                next_review_at=now - timedelta(hours=1),
            )
        )
        db.commit()

        start = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book.id, "size": 5, "mode": "review"},
        ).json()
        assert start["mode"] == "review"
        for clue in start["clues"]:
            auth_client.post(
                "/api/practice/submit",
                json={
                    "session_id": start["session_id"],
                    "word_id": clue["id"],
                    "answer": "wrong",
                },
            )
        auth_client.post(f"/api/practice/finish?session_id={start['session_id']}")

        _reopen(db)
        row = db.scalars(
            select(PracticeSessionRecord)
            .where(PracticeSessionRecord.user_id == user_id)
            .order_by(PracticeSessionRecord.id.desc())
        ).first()
        assert row is not None
        assert row.mode == "review"
        assert row.total == 1


class TestOverviewApi:
    def test_requires_auth(self, client: TestClient):
        assert client.get("/api/stats/overview").status_code == 401

    def test_fresh_user_shape(self, auth_client: TestClient):
        response = auth_client.get("/api/stats/overview")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["consecutive_days"] == 0
        assert body["checked_in_today"] is False
        assert body["today"]["words"] == 0
        assert body["today"]["accuracy"] == 0.0
        assert body["totals"]["practiced"] == 0
        assert body["recent"] == []

    def test_daily_is_zero_filled_and_ends_today(self, auth_client: TestClient):
        body = auth_client.get("/api/stats/overview").json()

        assert len(body["daily"]) == 7
        assert body["daily"][-1]["date"] == stats_service.today_utc().isoformat()
        assert body["daily"][0]["date"] == (
            stats_service.today_utc() - timedelta(days=6)
        ).isoformat()

    def test_today_and_totals_reflect_practice(self, auth_client: TestClient, db: Session,
                                               user_id: int, book: WordBook):
        _complete_group(auth_client, book.id, size=3)

        body = auth_client.get("/api/stats/overview").json()

        assert body["consecutive_days"] == 1
        assert body["checked_in_today"] is True
        assert body["today"]["words"] == 3
        assert body["today"]["sessions"] == 1
        assert body["today"]["accuracy"] == 0.0
        assert body["daily"][-1]["words"] == 3
        assert body["totals"]["practiced"] == 3
        assert body["totals"]["wrong"] == 3

    def test_recent_entries_carry_wordbook_title(self, auth_client: TestClient,
                                                 book: WordBook):
        _complete_group(auth_client, book.id, size=2)

        body = auth_client.get("/api/stats/overview").json()

        assert len(body["recent"]) == 1
        entry = body["recent"][0]
        assert entry["wordbook_id"] == book.id
        assert entry["wordbook_title"] == book.title
        assert entry["mode"] == "normal"
        assert entry["total"] == 2

    def test_recent_is_limited_to_ten(self, auth_client: TestClient, book: WordBook):
        for _ in range(12):
            _complete_group(auth_client, book.id, size=1)

        body = auth_client.get("/api/stats/overview").json()

        assert len(body["recent"]) == 10
        assert body["recent"][0]["total"] == 1

    def test_days_is_bounded(self, auth_client: TestClient):
        assert auth_client.get("/api/stats/overview", params={"days": 0}).status_code == 422
        assert auth_client.get("/api/stats/overview", params={"days": 31}).status_code == 422
        assert auth_client.get("/api/stats/overview", params={"days": 30}).status_code == 200


class TestGuestMigration:
    def test_streak_recomputed_not_maxed(self, client: TestClient, db: Session,
                                         book: WordBook):
        """游客转正必须按合并后的日期重算，不能取两个计数器的较大值。"""
        guest = client.post("/api/auth/guest").json()
        guest_id = int(guest["user"]["id"])

        # 游客 3 天前练过一次，计数器却写着 9（早已断签）
        _shift_checkin(db, guest_id, days_ago=3, streak=9)
        db.add(
            PracticeSessionRecord(
                user_id=guest_id,
                wordbook_id=book.id,
                mode="normal",
                total=2,
                correct_count=1,
                wrong_count=1,
                duration_ms=1000,
                practiced_on=stats_service.today_utc() - timedelta(days=3),
            )
        )
        db.commit()

        registered = client.post(
            "/api/auth/register",
            json={"username": f"streak_user_{guest_id}", "password": "secret123"},
            headers={"X-Guest-Id": str(guest_id)},
        )
        assert registered.status_code == 200, registered.text

        token = registered.json()["access_token"]
        body = client.get(
            "/api/stats/overview", headers={"Authorization": f"Bearer {token}"}
        ).json()

        # 合并后只剩 3 天前那一天：连续天数为 1，且今天并未打卡
        assert body["consecutive_days"] == 1
        assert body["checked_in_today"] is False

    def test_merged_sessions_appear_in_overview(self, client: TestClient, db: Session,
                                                book: WordBook):
        guest = client.post("/api/auth/guest").json()
        guest_id = int(guest["user"]["id"])
        db.add(
            PracticeSessionRecord(
                user_id=guest_id,
                wordbook_id=book.id,
                mode="review",
                total=5,
                correct_count=4,
                wrong_count=1,
                duration_ms=2000,
                practiced_on=stats_service.today_utc(),
            )
        )
        db.commit()

        registered = client.post(
            "/api/auth/register",
            json={"username": f"merge_user_{guest_id}", "password": "secret123"},
            headers={"X-Guest-Id": str(guest_id)},
        )
        assert registered.status_code == 200, registered.text

        token = registered.json()["access_token"]
        body = client.get(
            "/api/stats/overview", headers={"Authorization": f"Bearer {token}"}
        ).json()

        assert body["recent"], "游客会话应随账号迁移保留"
        assert body["recent"][0]["mode"] == "review"
        assert body["recent"][0]["total"] == 5
        assert body["today"]["words"] == 5
