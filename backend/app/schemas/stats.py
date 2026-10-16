"""学习看板相关模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailyStat(BaseModel):
    """单日练习统计。"""

    date: str
    sessions: int = 0
    words: int = 0
    correct: int = 0
    accuracy: float = 0.0


class RecentSession(BaseModel):
    """最近一次练习记录。"""

    date: str
    wordbook_id: int
    wordbook_title: str = ""
    # normal / wrong_book / review
    mode: str
    total: int
    correct: int
    accuracy: float
    duration_ms: int


class LearningTotals(BaseModel):
    """累计学习状态（跨全部词书）。"""

    mastered: int = 0
    learning: int = 0
    wrong: int = 0
    # 有练习记录的词数，不区分状态
    practiced: int = 0


class StatsOverview(BaseModel):
    """学习看板概览。"""

    consecutive_days: int = 0
    checked_in_today: bool = False
    today: DailyStat
    # 含今天在内、按日升序，未练习的日期补零，前端可直接画柱状图
    daily: list[DailyStat] = Field(default_factory=list)
    recent: list[RecentSession] = Field(default_factory=list)
    totals: LearningTotals
