from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Wordbook(Base):
    """词书表模型，字段定义严格对应 docs/data-dictionary.md。"""

    __tablename__ = "wordbooks"
    __table_args__ = (
        Index("idx_wordbooks_status", "status"),
        Index("idx_wordbooks_created_by", "created_by"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("draft", "published", "archived", name="wordbook_status"),
        nullable=False,
        server_default="draft",
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_wordbooks_created_by", ondelete="RESTRICT"),
        nullable=False,
    )
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
