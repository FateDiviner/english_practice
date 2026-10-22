from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class WrongWord(Base):
    """用户错词本记录。"""

    __tablename__ = "wrong_words"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_wrong_words_user_id_word_id"),
        Index("idx_wrong_words_user_resolved", "user_id", "resolved"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_wrong_words_user_id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("words.id", name="fk_wrong_words_word_id", ondelete="RESTRICT"),
        nullable=False,
    )
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_wrong_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
