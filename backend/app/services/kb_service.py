"""知识库上传：多格式解析与切块。

解析失败必须显式报错，绝不静默入库空内容——扫描版 PDF 抽不出文字层时，
用户以为传上去了，检索时才发现什么都没有，比当场报错难查得多。
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.kb import (
    DOC_FAILED,
    DOC_PENDING,
    KbChunk,
    KnowledgeDocument,
)
from app.models.user import User
from app.schemas.admin import KbDocumentOut
from app.services import audit_service
from app.services.admin_errors import AdminError

settings = get_settings()

# 扩展名 -> (MIME, 解析器名字)
SUPPORTED = {
    ".md": ("text/markdown", "markdown"),
    ".txt": ("text/plain", "text"),
    ".pdf": ("application/pdf", "pdf"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
}


class ParseError(Exception):
    """文档解析失败，携带给使用者看的原因。"""


@dataclass
class Chunk:
    """一个切块，携带所在小节标题。"""

    seq: int
    heading: str
    content: str


def _split_name(filename: str) -> tuple[str, str]:
    """返回 (不含扩展名的名字, 小写扩展名)。"""
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem, dot, ext = name.rpartition(".")
    if not dot:
        raise AdminError("文件名缺少扩展名，无法判断格式", status_code=422)
    return (stem or name).strip(), f".{ext.lower()}"


def _read_text(data: bytes) -> str:
    """UTF-8 优先，失败回退 GBK——中文教材很常见 GBK 存盘。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AdminError("文件编码无法识别，请另存为 UTF-8 后重试", status_code=422)


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf 抛的异常类型不固定
        raise ParseError(f"PDF 文件损坏或格式不受支持：{exc}") from exc

    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(pages).strip()
    if not text:
        raise ParseError(
            "PDF 未包含可提取的文字层（通常是扫描版）。本平台不做 OCR，请改传文字版 PDF 或导出为 .md/.txt"
        )
    return text


def _parse_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - python-docx 抛的异常类型不固定
        raise ParseError(f"DOCX 文件损坏或格式不受支持：{exc}") from exc

    parts: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    # 表格里的内容经常是考点对照，不能漏
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n\n".join(parts).strip()
    if not text:
        raise ParseError("DOCX 未包含任何文字内容")
    return text


def extract_text(filename: str, data: bytes) -> tuple[str, str, str]:
    """解析文档，返回 (标题, MIME, 正文)。"""
    stem, ext = _split_name(filename)
    entry = SUPPORTED.get(ext)
    if entry is None:
        supported = "、".join(sorted(SUPPORTED))
        raise AdminError(f"不支持的文件格式 {ext}，仅支持 {supported}", status_code=422)
    mime, parser = entry

    if parser == "pdf":
        body = _parse_pdf(data)
    elif parser == "docx":
        body = _parse_docx(data)
    else:
        body = _read_text(data).strip()

    if not body:
        raise ParseError("文件内容为空")
    return stem, mime, body


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def chunk_text(text: str) -> list[Chunk]:
    """按小节标题与空行分段，段内再按字符预算滑窗。

    每块记住所在小节：既是额外的检索特征，也是引用时给用户看的定位
    （「来自 xxx.md 的 ## 现在完成时」），比只给文件名有用得多。
    """
    limit = settings.kb_chunk_chars
    overlap = settings.kb_chunk_overlap

    sections: list[tuple[str, list[str]]] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        paragraph = "\n".join(buffer).strip()
        if paragraph:
            sections.append((heading, [paragraph]))
        buffer.clear()

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            heading = match.group(2).strip()
            continue
        if not line.strip():
            flush()
            continue
        buffer.append(line)
    flush()

    # 每个 section 的 body 现在是单段；再按字符预算滑窗切小块
    chunks: list[Chunk] = []
    seq = 0
    for section_heading, paragraphs in sections:
        body = "\n\n".join(paragraphs)
        if len(body) <= limit:
            chunks.append(Chunk(seq=seq, heading=section_heading, content=body))
            seq += 1
            continue
        start = 0
        while start < len(body):
            end = min(start + limit, len(body))
            # 尽量在句号或换行处断开，别把一个句子劈两半
            if end < len(body):
                window = body[start:end]
                cut = max(window.rfind("。"), window.rfind(". "), window.rfind("\n"))
                if cut > limit // 2:
                    end = start + cut + 1
            chunks.append(
                Chunk(seq=seq, heading=section_heading, content=body[start:end].strip())
            )
            seq += 1
            if end >= len(body):
                break
            start = max(end - overlap, start + 1)

    return [chunk for chunk in chunks if chunk.content]


def to_document_out(document: KnowledgeDocument) -> KbDocumentOut:
    """转成管理端视图。"""
    return KbDocumentOut(
        id=document.id,
        name=document.name,
        source_filename=document.source_filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        char_count=document.char_count,
        chunk_count=document.chunk_count,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat() if document.created_at else "",
    )


def create_document(
    db: Session,
    actor: User,
    filename: str,
    data: bytes,
    request: Request | None = None,
) -> KnowledgeDocument:
    """解析并入库一份文档，向量化留到索引阶段异步做。"""
    if not data:
        raise AdminError("上传的文件为空", status_code=422)
    if len(data) > settings.kb_max_upload_bytes:
        limit_mb = settings.kb_max_upload_bytes // (1024 * 1024)
        raise AdminError(f"文件过大，最大 {limit_mb}MB", status_code=413)

    try:
        name, mime, body = extract_text(filename, data)
    except ParseError as exc:
        raise AdminError(str(exc), status_code=422) from exc

    chunks = chunk_text(body)
    if not chunks:
        raise AdminError("文档解析后没有任何可检索的内容", status_code=422)

    document = KnowledgeDocument(
        name=name,
        source_filename=filename,
        mime_type=mime,
        size_bytes=len(data),
        char_count=len(body),
        chunk_count=len(chunks),
        status=DOC_PENDING,
        created_by=actor.id,
    )
    db.add(document)
    db.flush()
    for chunk in chunks:
        db.add(
            KbChunk(
                document_id=document.id,
                seq=chunk.seq,
                heading=chunk.heading,
                content=chunk.content,
            )
        )

    audit_service.record(
        db,
        actor=actor,
        action="kb.upload",
        target_type="knowledge_document",
        target_id=document.id,
        detail={
            "filename": filename,
            "size_bytes": len(data),
            "chunk_count": len(chunks),
        },
        affected_rows=len(chunks),
        request=request,
    )
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session) -> list[KbDocumentOut]:
    """全部文档，含失败的——失败了要让人看得见原因，而不是消失。"""
    rows = db.scalars(
        select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
    ).all()
    return [to_document_out(row) for row in rows]


def delete_document(
    db: Session, actor: User, document_id: int, request: Request | None = None
) -> None:
    """删除文档，切块随级联清除，向量由调用方从 VectorStore 里摘掉。"""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise AdminError("文档不存在", status_code=404)

    audit_service.record(
        db,
        actor=actor,
        action="kb.delete",
        target_type="knowledge_document",
        target_id=document_id,
        detail={"filename": document.source_filename, "chunk_count": document.chunk_count},
        affected_rows=document.chunk_count,
        request=request,
    )
    db.delete(document)
    db.commit()


def chunk_ids_of(db: Session, document_id: int) -> list[int]:
    """取文档下全部切块 id，供删除时同步清掉向量。"""
    return list(
        db.scalars(
            select(KbChunk.id).where(KbChunk.document_id == document_id)
        ).all()
    )
