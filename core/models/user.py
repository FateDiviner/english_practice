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
    # active: 正常 / banned: 封禁（登录与已有令牌一律拒绝）
    status: Mapped[str] = mapped_column(String(16), default="active", index=True, nullable=False)
    active_wordbook_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    consecutive_days: Mapped[int] = mapped_column(default=0, nullable=False)
    last_checkin_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # cascade="all, delete-orphan"：删除用户时由 ORM 连带删除子对象。
    # 必须显式声明——否则 ORM 把被删除用户的子对象当孤儿，转而把它们的
    # 外键 UPDATE 成 NULL；而 user_id 是 NOT NULL，直接 IntegrityError。
    # （注意 passive_deletes=True 不管用：records/messages 是 lazy="selectin"，
    #   子对象在查到用户时就已进 session，passive_deletes 只影响“是否去库里加载”。）
    # 数据库侧外键仍是 ON DELETE CASCADE，作为 ORM 之外路径的兜底。
    records = relationship(
        "UserWordRecord",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    # 练习会话只在看板与打卡重算时按需查询，不做预加载
    sessions = relationship(
        "PracticeSessionRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "ChatMessage",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
