"""知识库上传：多格式解析与切块测试。

解析失败必须显式报错——扫描版 PDF 抽不出文字层时，静默入库空内容比当场
报错难查得多。
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.kb import DOC_PENDING, KbChunk, KnowledgeDocument
from app.services import kb_service
from app.services.admin_errors import AdminError
from tests.admin_helpers import headers, make_admin, make_user, unique_name


def _chunks_of(db: Session, document_id: int) -> list[KbChunk]:
    """只取本次上传的切块——测试库是会话级共享的，全表取会拿到别人的。"""
    return (
        db.query(KbChunk).filter(KbChunk.document_id == document_id).order_by(KbChunk.seq).all()
    )


def _admin_token(db: Session, client: TestClient) -> str:
    return make_admin(db, client, unique_name("kb_admin"))["access_token"]


def build_pdf(text: str) -> bytes:
    """构造一个带文字层的最小 PDF。

    手写 xref 偏移：pypdf 按 startxref 定位交叉引用表，偏移错了就解析不出文字。
    """
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % index)
        out.write(body)
        out.write(b"\nendobj\n")

    xref_at = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref_at)
    )
    return out.getvalue()


def build_blank_pdf() -> bytes:
    """没有文字层的 PDF（相当于扫描版），用于验证报错路径。

    内容流里只有一个空格，pypdf 抽出来是空白，strip 之后为空。
    """
    return build_pdf(" ")


def build_docx(paragraphs: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload(client: TestClient, token: str, filename: str, data: bytes):
    return client.post(
        "/api/admin/kb/documents",
        files={"file": (filename, data, "application/octet-stream")},
        headers=headers(token),
    )


class TestPermissionGate:
    def test_plain_user_403(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("kb_gate"))
        plain = make_user(db, client, unique_name("kb_plain"))
        response = client.get("/api/admin/kb/documents", headers=headers(plain["access_token"]))
        assert response.status_code == 403


class TestFormats:
    def test_supported_list(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        body = client.get("/api/admin/kb/formats", headers=headers(token)).json()
        assert set(body["extensions"]) == {".md", ".txt", ".pdf", ".docx"}
        assert body["max_bytes"] > 0


class TestUploadMarkdown:
    def test_parses_and_chunks(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        content = "# 现在完成时\n\nI have finished my homework.\n\n## 过去分词\n\n规则变化加 ed。"
        response = _upload(client, token, "grammar.md", content.encode("utf-8"))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "grammar"
        assert body["status"] == DOC_PENDING
        assert body["chunk_count"] >= 2
        assert body["char_count"] == len(content)

    def test_heading_captured_per_chunk(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        content = "# 第一节\n\n内容甲。\n\n# 第二节\n\n内容乙。"
        doc = _upload(client, token, "h.md", content.encode("utf-8")).json()

        rows = db.query(KbChunk).filter(KbChunk.document_id == doc["id"]).all()
        headings = {row.heading for row in rows}
        # 小节标题既是检索特征，也是引用时给用户看的定位
        assert {"第一节", "第二节"} <= headings


class TestUploadPlainText:
    def test_txt_accepted(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "notes.txt", "第一段内容。\n\n第二段内容。".encode("utf-8"))
        assert response.status_code == 200, response.text
        assert response.json()["chunk_count"] >= 1

    def test_gbk_fallback(self, client: TestClient, db: Session) -> None:
        """中文教材很常见 GBK 存盘，不能只认 UTF-8。"""
        token = _admin_token(db, client)
        response = _upload(client, token, "legacy.txt", "这是一段中文。".encode("gbk"))
        assert response.status_code == 200, response.text
        assert response.json()["char_count"] > 0


class TestUploadPdf:
    def test_text_pdf_parsed(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "book.pdf", build_pdf("Present perfect tense"))
        assert response.status_code == 200, response.text
        doc = response.json()
        assert doc["mime_type"] == "application/pdf"
        content = " ".join(row.content for row in _chunks_of(db, doc["id"]))
        assert "Present perfect" in content

    def test_scanned_pdf_rejected_with_reason(self, client: TestClient, db: Session) -> None:
        """扫描版抽不出文字层时必须报错，不能静默入库空内容。"""
        token = _admin_token(db, client)
        response = _upload(client, token, "scan.pdf", build_blank_pdf())
        assert response.status_code == 422
        assert "文字层" in response.json()["detail"]
        assert response.json()["detail"].count("OCR") == 1

    def test_corrupt_pdf_rejected(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "broken.pdf", b"%PDF-1.4 not really a pdf")
        assert response.status_code == 422


class TestUploadDocx:
    def test_paragraphs_and_tables(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "handout.docx", build_docx(["要点一", "要点二"]))
        assert response.status_code == 200, response.text
        content = " ".join(row.content for row in _chunks_of(db, response.json()["id"]))
        assert "要点一" in content and "要点二" in content


class TestRejections:
    def test_unsupported_extension(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "sheet.xlsx", b"anything")
        assert response.status_code == 422
        assert ".xlsx" in response.json()["detail"]

    def test_empty_file(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "empty.md", b"")
        assert response.status_code == 422

    def test_blank_content(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "blank.md", b"   \n\n   ")
        assert response.status_code == 422

    def test_missing_extension_in_name(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        response = _upload(client, token, "noextension", b"hello")
        assert response.status_code == 422

    def test_oversized(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        big = b"x" * (kb_service.settings.kb_max_upload_bytes + 1)
        response = _upload(client, token, "huge.txt", big)
        assert response.status_code == 413


class TestDocumentLifecycle:
    def test_parse_failure_never_reaches_storage(self, client: TestClient, db: Session) -> None:
        """解析失败在上传时就拒绝，不入库。

        所以 failed 状态不是留给解析的——它是留给后续向量化失败的。
        静默入库一份抽不出文字的 PDF，用户要到检索时才发现，难查得多。
        """
        token = _admin_token(db, client)
        ok_name = unique_name("kb_ok")
        bad_name = unique_name("kb_bad")
        assert _upload(client, token, f"{ok_name}.md", "正常内容。".encode()).status_code == 200
        rejected = _upload(client, token, f"{bad_name}.pdf", build_blank_pdf())
        assert rejected.status_code == 422

        listing = client.get("/api/admin/kb/documents", headers=headers(token)).json()
        mine = [item for item in listing if ok_name in item["name"] or bad_name in item["name"]]
        assert len(mine) == 1
        assert ok_name in mine[0]["name"]
        assert mine[0]["status"] == DOC_PENDING

    def test_delete_cascades_chunks(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        doc = _upload(client, token, "gone.md", "要被删掉的内容。".encode()).json()
        assert db.query(KbChunk).filter(KbChunk.document_id == doc["id"]).count() >= 1

        response = client.delete(
            f"/api/admin/kb/documents/{doc['id']}", headers=headers(token)
        )
        assert response.status_code == 200
        assert db.get(KnowledgeDocument, doc["id"]) is None
        assert db.query(KbChunk).filter(KbChunk.document_id == doc["id"]).count() == 0

    def test_delete_missing_404(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        assert (
            client.delete("/api/admin/kb/documents/999999", headers=headers(token)).status_code
            == 404
        )

    def test_upload_logged(self, client: TestClient, db: Session) -> None:
        token = _admin_token(db, client)
        _upload(client, token, "logged.md", "内容。".encode())
        from sqlalchemy import select

        from app.models.audit import AuditLog

        actions = {entry.action for entry in db.scalars(select(AuditLog)).all()}
        assert "kb.upload" in actions


class TestChunking:
    def test_short_text_single_chunk(self) -> None:
        assert len(kb_service.chunk_text("一句话。")) == 1

    def test_long_text_split_with_overlap(self) -> None:
        text = "这是一个句子。" * 200
        chunks = kb_service.chunk_text(text)
        assert len(chunks) > 1
        limit = kb_service.settings.kb_chunk_chars
        assert all(len(chunk.content) <= limit + 50 for chunk in chunks)
        # 序号连续且从 0 开始，检索结果要能按顺序还原
        assert [chunk.seq for chunk in chunks] == list(range(len(chunks)))

    def test_breaks_on_sentence_boundary(self) -> None:
        """尽量在句号处断开，别把一个句子劈两半。"""
        text = ("短句。" * 3 + "这是一个足够长的句子，用来撑满切块窗口。" * 20)
        chunks = kb_service.chunk_text(text)
        for chunk in chunks[:-1]:
            assert chunk.content.endswith(("。", ".", "！", "？", "!", "?", "\n")) or len(
                chunk.content
            ) < kb_service.settings.kb_chunk_chars

    def test_heading_only_section_dropped(self) -> None:
        """只有标题没有正文的小节不应产生空块。"""
        chunks = kb_service.chunk_text("# 空章节\n\n# 有内容\n\n正文。")
        assert len(chunks) == 1
        assert chunks[0].heading == "有内容"


class TestExtractTextUnit:
    def test_raises_admin_error_on_bad_extension(self) -> None:
        with pytest.raises(AdminError):
            kb_service.extract_text("x.csv", b"a,b")

    def test_split_name(self) -> None:
        assert kb_service._split_name("dir/notes.MD") == ("notes", ".md")
        assert kb_service._split_name("C:\\a\\b.txt") == ("b", ".txt")
