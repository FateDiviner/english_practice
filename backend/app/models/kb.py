"""知识库表：文档与切块。

向量不在这里——它们住在 VectorStore（faiss 索引文件）里，按 chunk.id 关联。
MySQL 只管结构化元数据与正文，向量检索与业务数据分开，两边各管各的备份。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# 文档状态
DOC_PENDING = "pending"  # 已入库，尚未开始向量化
DOC_INDEXING = "indexing"  # 向量化进行中
DOC_READY = "ready"  # 可检索
DOC_FAILED = "failed"  # 向量化失败，error 字段记录原因

DOCUMENT_STATUSES = (DOC_PENDING, DOC_INDEXING, DOC_READY, DOC_FAILED)

DOCUMENT_STATUS_LABELS = {
    DOC_PENDING: "[待索引]",
    DOC_INDEXING: "[索引中]",
    DOC_READY: "[可用]",
    DOC_FAILED: "[失败]",
}


class KnowledgeDocument(Base):
    """一份上传的教学资料。"""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # md / txt / pdf / docx
    mime_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=DOC_PENDING, index=True, nullable=False
    )
    # 失败原因，例如「PDF 未包含可提取的文字层」
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 上传人被删除后文档仍要可用，因此外键置空而非级联删除
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=False
    )

    chunks = relationship(
        "KbChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)


class KbChunk(Base):
    """文档切块，是检索的最小单位，也是引用来源的落点。"""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 所在小节标题，既是额外的检索特征，也是引用时给用户看的定位
    heading: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
