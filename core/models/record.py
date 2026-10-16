"""练习记录与错题表 user_word_records。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class UserWordRecord(Base):
    """用户与单词的练习状态，驱动遗忘曲线调度。"""

    __tablename__ = "user_word_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # learning: 学习中 / mastered: 已掌握 / wrong: 错题（生词）
    status: Mapped[str] = mapped_column(String(16), default="learning", nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    right_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 记忆强度 0~5，对应遗忘曲线复习间隔档位
    ease_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="records")
    word = relationship("Word", lazy="selectin")

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
