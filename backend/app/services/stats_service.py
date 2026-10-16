"""学习看板统计与连续打卡。

数据来源是落库的练习会话（practice_sessions）。日历口径与 scheduler 保持一致，
统一使用 UTC，避免"今天"在复习队列与打卡之间出现两种边界。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.record import UserWordRecord
from app.models.session import PracticeSessionRecord
from app.models.user import User
from app.models.wordbook import WordBook

# 看板默认展示的天数
DEFAULT_TREND_DAYS = 7


def today_utc() -> date:
    """全项目统一的日历口径：UTC。"""
    return datetime.now(timezone.utc).date()


def mark_checkin(db: Session, user_id: int) -> None:
    """记录一次打卡：同一天幂等，隔天续接，断签归一。

    在每次作答时调用（而非结算时），保证练到一半退出也能算作当天练过。
    """
    today = today_utc()
    stamp = today.isoformat()
    user = db.get(User, user_id)
    if user is None or user.last_checkin_date == stamp:
        return

    yesterday = (today - timedelta(days=1)).isoformat()
    if user.last_checkin_date == yesterday:
        user.consecutive_days = (user.consecutive_days or 0) + 1
    else:
        user.consecutive_days = 1
    user.last_checkin_date = stamp


def record_session(
    db: Session,
    *,
    user_id: int,
    wordbook_id: int,
    mode: str,
    total: int,
    correct_count: int,
    wrong_count: int,
    duration_ms: int,
) -> PracticeSessionRecord:
    """把一次结算写入练习会话表。"""
    record = PracticeSessionRecord(
        user_id=user_id,
        wordbook_id=wordbook_id,
        mode=mode,
        total=total,
        correct_count=correct_count,
        wrong_count=wrong_count,
        duration_ms=duration_ms,
        practiced_on=today_utc(),
    )
    db.add(record)
    return record


def recompute_streak(db: Session, user_id: int) -> tuple[int, date | None]:
    """从练习会话反推连续天数，返回 (天数, 最近练习日)。

    游客转正合并两侧数据后必须重算：直接取两个计数器的较大值会把
    已经过期的连续天数也一起继承下来。
    """
    days = [
        row[0]
        for row in db.execute(
            select(PracticeSessionRecord.practiced_on)
            .where(PracticeSessionRecord.user_id == user_id)
            .distinct()
            .order_by(PracticeSessionRecord.practiced_on.desc())
        ).all()
    ]
    if not days:
        return 0, None

    streak = 1
    for previous, current in zip(days, days[1:]):
        if (previous - current).days != 1:
            break
        streak += 1
    return streak, days[0]


def build_overview(db: Session, user_id: int, days: int = DEFAULT_TREND_DAYS) -> dict:
    """生成学习看板概览：连续打卡、今日进度、近 N 天趋势与累计掌握。"""
    today = today_utc()
    start = today - timedelta(days=days - 1)

    rows = list(
        db.scalars(
            select(PracticeSessionRecord)
            .where(
                PracticeSessionRecord.user_id == user_id,
                PracticeSessionRecord.practiced_on >= start,
            )
            .order_by(PracticeSessionRecord.practiced_on, PracticeSessionRecord.id)
        ).all()
    )
    grouped: dict[date, list[PracticeSessionRecord]] = defaultdict(list)
    for row in rows:
        grouped[row.practiced_on].append(row)

    def _stat(day: date) -> dict:
        items = grouped.get(day, [])
        words = sum(item.total for item in items)
        correct = sum(item.correct_count for item in items)
        return {
            "date": day.isoformat(),
            "sessions": len(items),
            "words": words,
            "correct": correct,
            "accuracy": round(correct / words * 100, 1) if words else 0.0,
        }

    daily = [_stat(start + timedelta(days=offset)) for offset in range(days)]

    recent_rows = list(
        db.scalars(
            select(PracticeSessionRecord)
            .where(PracticeSessionRecord.user_id == user_id)
            .order_by(PracticeSessionRecord.id.desc())
            .limit(10)
        ).all()
    )
    recent = [
        {
            "date": item.practiced_on.isoformat(),
            "wordbook_id": item.wordbook_id,
            "mode": item.mode,
            "total": item.total,
            "correct": item.correct_count,
            "accuracy": (
                round(item.correct_count / item.total * 100, 1) if item.total else 0.0
            ),
            "duration_ms": item.duration_ms,
        }
        for item in recent_rows
    ]

    user = db.get(User, user_id)
    totals_by_status = {
        status: count
        for status, count in db.execute(
            select(UserWordRecord.status, func.count())
            .where(UserWordRecord.user_id == user_id)
            .group_by(UserWordRecord.status)
        ).all()
    }
    titles = {
        book.id: book.title
        for book in db.scalars(select(WordBook)).all()
    }
    for entry in recent:
        entry["wordbook_title"] = titles.get(entry["wordbook_id"], "")

    return {
        "consecutive_days": (user.consecutive_days or 0) if user else 0,
        "checked_in_today": bool(user and user.last_checkin_date == today.isoformat()),
        "today": _stat(today),
        "daily": daily,
        "recent": recent,
        "totals": {
            "mastered": totals_by_status.get("mastered", 0),
            "learning": totals_by_status.get("learning", 0),
            "wrong": totals_by_status.get("wrong", 0),
            "practiced": sum(totals_by_status.values()),
        },
    }
