from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class McpChangeRequest(Base):
    """MCP 提交的写操作申请，等待管理员在后台审批后执行。"""

    __tablename__ = "mcp_change_requests"
    __table_args__ = (
        Index("idx_mcp_change_requests_status", "status", "created_at"),
        Index("idx_mcp_change_requests_requested_by", "requested_by"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "approved",
            "rejected",
            "executed",
            "failed",
            "expired",
            "cancelled",
            name="mcp_change_status",
        ),
        nullable=False,
        server_default="pending",
    )
    requested_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_mcp_change_requests_requested_by", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_mcp_change_requests_approved_by", ondelete="RESTRICT"),
        nullable=True,
    )
    client_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class McpAuditLog(Base):
    """MCP 工具调用与审批动作的审计记录，敏感参数在写入前脱敏。"""

    __tablename__ = "mcp_audit_logs"
    __table_args__ = (
        Index("idx_mcp_audit_logs_admin_created", "admin_id", "created_at"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_mcp_audit_logs_admin_id", ondelete="RESTRICT"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    params_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class McpImportUpload(Base):
    """MCP 导入文件暂存，审批通过并创建导入任务后标记为已消费。"""

    __tablename__ = "mcp_import_uploads"
    __table_args__ = (
        Index("idx_mcp_import_uploads_uploaded_by", "uploaded_by"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary(length=16 * 1024 * 1024), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_mcp_import_uploads_uploaded_by", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
