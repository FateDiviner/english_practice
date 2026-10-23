from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SessionQuestion(Base):
    """一次练习会话中实际生成的题目集合与顺序。"""

    __tablename__ = "session_questions"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "word_id",
            name="uq_session_questions_session_id_word_id",
        ),
        Index("idx_session_questions_session_sort", "session_id", "sort_order"),
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
            name="fk_session_questions_session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("words.id", name="fk_session_questions_word_id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
