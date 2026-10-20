"""单词表 words。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import STATUS_ACTIVE
from app.db import Base


class Word(Base):
    """单词实体：英文原词 + 音标 + 中文释义 + 例句。"""

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wordbook_id: Mapped[int] = mapped_column(
        ForeignKey("wordbooks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    word: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phonetic: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    translation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    example_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    example_cn: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # active: 可用 / archived: 已下架。物理删除仅在零用户引用时允许
    status: Mapped[str] = mapped_column(
        String(16), default=STATUS_ACTIVE, index=True, nullable=False
    )
    sequence: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    wordbook = relationship("WordBook", back_populates="words")
