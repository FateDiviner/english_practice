"""AI 伴学接入 RAG 的测试，以及管理端检索调试接口。

核心契约：SSE 帧结构在原有的 start/delta/error/done 之上新增 status，
且 RAG 关闭或失败时行为与接入前完全一致。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.kb import DOC_READY, KbChunk, KnowledgeDocument
from app.rag import corpus, embeddings, store
from app.rag.stages import retrieve
from app.rag.store import FaissVectorStore
from app.services.auth_service import create_user
from tests.admin_helpers import headers, make_admin, make_user, unique_name

settings = get_settings()


def parse_sse(text: str) -> list[dict]:
    frames = []
    for block in text.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    frames.append(json.loads(payload))
    return frames


@pytest.fixture
def rag_ready(
    tmp_path, monkeypatch: pytest.MonkeyPatch, db: Session
) -> Iterator[None]:
    """把 embedding 换成确定性假实现，向量库指向临时目录，并喂一份文档。"""
    import hashlib

    import numpy as np

    dim = settings.embedding_dimension

    def fake(texts, use_cache=True):
        out = []
        for text in texts:
            vector = np.zeros(dim, dtype="float32")
            for token in text.lower().split():
                vector[int(hashlib.md5(token.encode()).hexdigest()[:6], 16) % dim] += 1.0
            norm = float(np.linalg.norm(vector)) or 1.0
            out.append((vector / norm).tolist())
        return out

    monkeypatch.setattr(embeddings, "embed", fake)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: fake([text])[0])
    monkeypatch.setattr(store, "_STORE", None)
    store.set_store(FaissVectorStore(tmp_path / "index"))
    retrieve.invalidate_index()

    corpus.ensure_word_index(db)
    admin = create_user(db, unique_name("chat_rag"), "secret123")
    db.commit()
    document = KnowledgeDocument(
        name="grammar",
        source_filename="grammar.md",
        mime_type="text/markdown",
        size_bytes=80,
        char_count=80,
        chunk_count=1,
        status=DOC_READY,
        created_by=admin.id,
    )
    db.add(document)
    db.flush()
    db.add(
        KbChunk(
            document_id=document.id,
            seq=0,
            heading="现在完成时",
            content="现在完成时由 have 或 has 加过去分词构成。",
        )
    )
    db.commit()
    assert corpus.index_kb(db).failed == 0
    try:
        yield
    finally:
        store.set_store(None)
        retrieve.invalidate_index()


class TestChatEmitsStatusFrames:
    def test_status_frame_when_retrieved(
        self, auth_client: TestClient, rag_ready: None
    ) -> None:
        response = auth_client.post(
            "/api/chat/send", json={"content": "现在完成时怎么构成"}
        )
        frames = parse_sse(response.text)
        types = [frame["type"] for frame in frames]

        assert "status" in types
        statuses = [frame for frame in frames if frame["type"] == "status"]
        phases = [frame["phase"] for frame in statuses]
        assert "retrieved" in phases
        retrieved = next(frame for frame in statuses if frame["phase"] == "retrieved")
        assert retrieved["hits"] >= 1
        assert retrieved["sources"]

    def test_status_frame_when_skipped(
        self, auth_client: TestClient, rag_ready: None
    ) -> None:
        """门控跳过时也要给前端一个明确的 reason，否则它不知道该不该显示检索态。"""
        response = auth_client.post("/api/chat/send", json={"content": "hi"})
        frames = parse_sse(response.text)
        statuses = [frame for frame in frames if frame["type"] == "status"]
        assert statuses
        assert statuses[0]["phase"] == "skipped"
        assert statuses[0]["reason"]

    def test_done_frame_carries_sources(
        self, auth_client: TestClient, rag_ready: None
    ) -> None:
        response = auth_client.post(
            "/api/chat/send", json={"content": "现在完成时怎么构成"}
        )
        done = next(frame for frame in parse_sse(response.text) if frame["type"] == "done")
        assert "sources" in done
        assert done["sources"]
        assert {"index", "kind", "label", "source"} <= set(done["sources"][0])

    def test_stream_still_works(self, auth_client: TestClient, rag_ready: None) -> None:
        """接了 RAG 之后逐字输出与纠错区块不能坏。"""
        response = auth_client.post(
            "/api/chat/send", json={"content": "I am agree with you"}
        )
        frames = parse_sse(response.text)
        types = [frame["type"] for frame in frames]
        assert "start" in types
        assert "delta" in types
        assert "done" in types
        assert "error" not in types


class TestRagDisabled:
    def test_no_status_frames_when_disabled(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAG 关掉后行为必须与接入前完全一致，不能留下多余帧。"""
        monkeypatch.setattr(settings, "rag_enabled", False)
        response = auth_client.post(
            "/api/chat/send", json={"content": "现在完成时怎么构成"}
        )
        frames = parse_sse(response.text)
        assert all(frame["type"] != "status" for frame in frames)
        done = next(frame for frame in frames if frame["type"] == "done")
        assert done["sources"] == []

    def test_disabled_result_skips(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.db import SessionLocal
        from app.rag.pipeline import run

        monkeypatch.setattr(settings, "rag_enabled", False)
        with SessionLocal() as db:
            result = run("现在完成时怎么构成", db)
        assert "未启用" in (result.skipped or "")


class TestRagFailureDegrades:
    def test_embedding_failure_does_not_break_chat(
        self, auth_client: TestClient, rag_ready: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(texts, use_cache=True):
            raise embeddings.EmbeddingError("挂了")

        monkeypatch.setattr(embeddings, "embed", boom)
        monkeypatch.setattr(embeddings, "embed_query", lambda text: boom([text]))

        response = auth_client.post(
            "/api/chat/send", json={"content": "现在完成时怎么构成"}
        )
        frames = parse_sse(response.text)
        assert any(frame["type"] == "delta" for frame in frames)
        assert any(frame["type"] == "done" for frame in frames)
        assert not any(frame["type"] == "error" for frame in frames)


class TestRagAdminApi:
    def test_config_lists_available_stages(self, client: TestClient, db: Session) -> None:
        token = make_admin(db, client, unique_name("rag_cfg"))["access_token"]
        body = client.get("/api/admin/rag/config", headers=headers(token)).json()
        assert body["strategy"] == "naive"
        assert body["llm_rerank"] is False
        assert set(body["available_stages"]["retrieve"]) == {"bm25", "vector", "graph"}
        assert "naive" in body["available_strategies"]
        assert {"kb_chunks", "word_chunks"} <= set(body["vector_counts"])

    def test_config_requires_admin(self, client: TestClient, db: Session) -> None:
        make_admin(db, client, unique_name("rag_gate"))
        plain = make_user(db, client, unique_name("rag_plain"))
        assert (
            client.get("/api/admin/rag/config", headers=headers(plain["access_token"])).status_code
            == 403
        )

    def test_preview_returns_trace(
        self, client: TestClient, db: Session, rag_ready: None
    ) -> None:
        token = make_admin(db, client, unique_name("rag_prev"))["access_token"]
        response = client.post(
            "/api/admin/rag/preview",
            json={"query": "现在完成时怎么构成"},
            headers=headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["lang"] == "zh"
        assert body["trace"]
        stages = [trace["stage"] for trace in body["trace"]]
        assert "normalize" in stages and "rrf" in stages
        # 调阈值全靠这条：候选与分数要一起给出来
        for hit in body["hits"]:
            assert {"rank", "score", "source", "kind", "content"} <= set(hit)

    def test_preview_empty_query(self, client: TestClient, db: Session) -> None:
        token = make_admin(db, client, unique_name("rag_empty"))["access_token"]
        body = client.post(
            "/api/admin/rag/preview", json={"query": ""}, headers=headers(token)
        ).json()
        assert body["skipped"]

    def test_health_reports_embedding(
        self, client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        token = make_admin(db, client, unique_name("rag_h"))["access_token"]
        monkeypatch.setattr(
            embeddings, "ping", lambda: False
        )
        body = client.get("/api/admin/rag/health", headers=headers(token)).json()
        assert body["embedding"] is False
