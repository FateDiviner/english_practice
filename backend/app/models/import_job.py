from sqlalchemy import JSON, BigInteger, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImportJob(Base):
    """一次单词文件导入任务。"""

    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("idx_import_jobs_wordbook", "wordbook_id"),
        Index("idx_import_jobs_status", "status"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wordbook_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wordbooks.id", name="fk_import_jobs_wordbook_id", ondelete="RESTRICT"),
        nullable=False,
    )
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_import_jobs_admin_id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "done", "failed", name="import_job_status"),
        nullable=False,
        server_default="pending",
    )
    error_detail: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
