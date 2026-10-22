from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PracticeSession(Base):
    """一次默写练习会话。"""

    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_started_at", "started_at"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_practice_sessions_user_id", ondelete="CASCADE"),
        nullable=False,
    )
    wordbook_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "wordbooks.id",
            name="fk_practice_sessions_wordbook_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    mode: Mapped[str] = mapped_column(
        Enum("normal", "wrong_only", name="practice_session_mode"),
        nullable=False,
        server_default="normal",
    )
    strict_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        Enum("ongoing", "finished", name="practice_session_status"),
        nullable=False,
        server_default="ongoing",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
