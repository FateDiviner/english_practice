"""对话消息表 chat_messages。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ChatMessage(Base):
    """AI 伴学对话历史。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # user / assistant / system
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 纠错区块 JSON：{"grammar": "...", "polish": ["...", "..."]}
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Agent/RAG 执行摘要 JSON：模式、轮次、工具、来源与耗时
    # ORM 属性不能叫 metadata（SQLAlchemy 保留名），物理列名仍是 metadata。
    # 不建索引：MySQL 不允许给 TEXT 列建整列索引（error 1170），
    # 且该列只随 user_id 顺序读取、从不单独过滤，索引既建不了也没必要。
    agent_metadata: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="messages")