from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Word(Base):
    """单词表模型，字段定义严格对应 docs/data-dictionary.md。"""

    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint(
            "wordbook_id",
            "spelling",
            name="uq_words_wordbook_id_spelling",
        ),
        Index("idx_words_wordbook_id", "wordbook_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wordbook_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wordbooks.id", name="fk_words_wordbook_id", ondelete="RESTRICT"),
        nullable=False,
    )
    spelling: Mapped[str] = mapped_column(String(100), nullable=False)
    phonetic_uk: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phonetic_us: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meaning_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    part_of_speech: Mapped[str | None] = mapped_column(String(20), nullable=True)
    example_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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
