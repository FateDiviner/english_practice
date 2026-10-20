"""审计日志表 audit_logs。

只增不改不删：应用层不提供任何修改或删除审计的接口，这是「审计只增」落到
代码上唯一可执行的形式。业务写操作与审计必须同事务提交，否则会出现
「操作成功但审计丢失」或「审计写了但操作回滚」。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditLog(Base):
    """一次管理端操作的留痕。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 用户被删除后审计仍需可读，因此外键置空而非级联删除
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # 冗余保存操作人姓名快照：用户名被改后日志仍能认出是谁
    actor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # user.create / user.ban / wordbook.archive / word.purge ...
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # JSON 变更摘要，严禁包含密码、哈希、令牌与对话正文
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=False
    )

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
