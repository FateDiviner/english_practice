from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserWordbook(Base):
    """用户与词书的学习关系。"""

    __tablename__ = "user_wordbooks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "wordbook_id",
            name="uq_user_wordbooks_user_id_wordbook_id",
        ),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_user_wordbooks_user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    wordbook_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wordbooks.id", name="fk_user_wordbooks_wordbook_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("learning", "completed", name="user_wordbook_status"),
        nullable=False,
        server_default="learning",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
