"""连续打卡的推导：日历口径与反推计算。

这两个函数只依赖 practice_sessions 一张表，却被 core 的账号迁移逻辑用到，
因此必须放在 core——放在 backend 会让 core 反向依赖 backend。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.session import PracticeSessionRecord


def today_utc() -> date:
    """全项目统一的日历口径：UTC。"""
    return datetime.now(timezone.utc).date()


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
