"""用户表 users。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class User(Base):
    """注册用户，含一键游客账号。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # user: 普通用户 / admin: 管理端管理员。游客永远是 user
    role: Mapped[str] = mapped_column(String(16), default="user", index=True, nullable=False)
    active_wordbook_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    consecutive_days: Mapped[int] = mapped_column(default=0, nullable=False)
    last_checkin_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    records = relationship("UserWordRecord", back_populates="user", lazy="selectin")
    # 练习会话只在看板与打卡重算时按需查询，不做预加载
    sessions = relationship("PracticeSessionRecord", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user", lazy="selectin")
