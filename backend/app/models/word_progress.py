from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WordProgress(Base):
    """用户对单个单词的掌握进度。"""

    __tablename__ = "word_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_word_progress_user_id_word_id"),
        Index("idx_word_progress_user", "user_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_word_progress_user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("words.id", name="fk_word_progress_word_id", ondelete="RESTRICT"),
        nullable=False,
    )
    mastery_level: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    consecutive_correct: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    last_result: Mapped[str | None] = mapped_column(
        Enum("correct", "wrong", name="word_progress_last_result"),
        nullable=True,
    )
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
