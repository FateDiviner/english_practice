"""add mcp tables

Revision ID: c9f3a2b7d1e4
Revises: 03545f06505d
Create Date: 2026-10-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f3a2b7d1e4"
down_revision: str | Sequence[str] | None = "03545f06505d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mcp_change_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "executed",
                "failed",
                "expired",
                "cancelled",
                name="mcp_change_status",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("requested_by", sa.BigInteger(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("client_name", sa.String(length=100), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_mcp_change_requests_requested_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name="fk_mcp_change_requests_approved_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_mcp_change_requests_status",
        "mcp_change_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_mcp_change_requests_requested_by",
        "mcp_change_requests",
        ["requested_by"],
    )

    op.create_table(
        "mcp_audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("params_summary", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("client_name", sa.String(length=100), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["users.id"],
            name="fk_mcp_audit_logs_admin_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_mcp_audit_logs_admin_created",
        "mcp_audit_logs",
        ["admin_id", "created_at"],
    )

    op.create_table(
        "mcp_import_uploads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.LargeBinary(length=16 * 1024 * 1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="fk_mcp_import_uploads_uploaded_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_mcp_import_uploads_uploaded_by",
        "mcp_import_uploads",
        ["uploaded_by"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_mcp_import_uploads_uploaded_by", table_name="mcp_import_uploads")
    op.drop_table("mcp_import_uploads")
    op.drop_index("idx_mcp_audit_logs_admin_created", table_name="mcp_audit_logs")
    op.drop_table("mcp_audit_logs")
    op.drop_index("idx_mcp_change_requests_requested_by", table_name="mcp_change_requests")
    op.drop_index("idx_mcp_change_requests_status", table_name="mcp_change_requests")
    op.drop_table("mcp_change_requests")
