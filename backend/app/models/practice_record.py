from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PracticeRecord(Base):
    """练习会话中的单题作答记录。"""

    __tablename__ = "practice_records"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "word_id",
            name="uq_practice_records_session_id_word_id",
        ),
        Index("idx_records_session", "session_id"),
        Index("idx_records_word", "word_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "practice_sessions.id",
            name="fk_practice_records_session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("words.id", name="fk_practice_records_word_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_input: Mapped[str] = mapped_column(String(100), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    used_hint: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    answered_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
