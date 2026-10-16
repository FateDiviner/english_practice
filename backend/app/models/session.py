"""练习会话表 practice_sessions。

会话本身（切词顺序、耗时基准）仍是进程内缓存，刷新即丢；
但每一次结算都必须落库——看板的今日进度、近 N 天趋势与连续打卡
全部依赖这张表，没有它就只能展示当下这一组的数据。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PracticeSessionRecord(Base):
    """一次已完成的练习结算记录。"""

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    wordbook_id: Mapped[int] = mapped_column(
        ForeignKey("wordbooks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # normal / wrong_book / review
    mode: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 结算归属的自然日（UTC），看板按日聚合与打卡判定都以它为准
    practiced_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="sessions")

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
