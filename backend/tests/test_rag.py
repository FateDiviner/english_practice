"""RAG 管线测试。

embedding 一律 mock，不打真实接口；向量库指向临时目录。
重点验证三件事：门控真的会跳过、阈值真的会拒答、任何失败都不阻断对话。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.kb import DOC_READY, KbChunk, KnowledgeDocument
from app.models.relation import WordRelation
from app.rag import corpus, embeddings, pipeline, store
from app.rag.registry import (
    RagConfigError,
    available_stages,
    available_strategies,
    get_strategy,
    register_stage,
    resolve_stages,
)
from app.rag.store import FaissVectorStore, NullVectorStore
from app.rag.stages import post, pre, ranking, retrieve
from app.rag.types import Hit, RagContext, StageKind
from app.db import SessionLocal
from app.services.auth_service import create_user
from tests.admin_helpers import unique_name

settings = get_settings()
DIM = settings.embedding_dimension


def _fake_embed(texts: list[str], use_cache: bool = True) -> list[list[float]]:
    """确定性假向量：同一 token 始终落到同一维，保证同文本同向量。

    哈希向量抓不住语义相似度，所以本文件的断言只依赖 BM25 与图谱两路；
    向量路只验证「被调用、失败时降级」，不验证排序质量。
    """
    out: list[list[float]] = []
    for text in texts:
        vector = np.zeros(DIM, dtype="float32")
        for token in text.lower().split():
            vector[int(hashlib.md5(token.encode()).hexdigest()[:6], 16) % DIM] += 1.0
        norm = float(np.linalg.norm(vector)) or 1.0
        out.append((vector / norm).tolist())
    return out


@pytest.fixture
def rag_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """把 embedding 与向量库都换成可控实现。"""
    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: _fake_embed([text])[0])
    monkeypatch.setattr(store, "_STORE", None)
    store.set_store(FaissVectorStore(tmp_path / "index"))
    retrieve.invalidate_index()
    try:
        yield
    finally:
        store.set_store(None)
        retrieve.invalidate_index()


@pytest.fixture
def seeded(db: Session, rag_env: None) -> Session:
    """词库懒加载 + 一份两块的知识库文档。

    必须依赖 rag_env：embedding 是在这里被换成假实现的，
    否则 corpus.index_kb 会去打真实接口。
    """
    corpus.ensure_word_index(db)
    admin = create_user(db, unique_name("rag_seed"), "secret123")
    db.commit()
    document = KnowledgeDocument(
        name="grammar",
        source_filename="grammar.md",
        mime_type="text/markdown",
        size_bytes=120,
        char_count=120,
        chunk_count=2,
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
            content="现在完成时由 have 或 has 加过去分词构成，强调对现在的影响。",
        )
    )
    db.add(
        KbChunk(
            document_id=document.id,
            seq=1,
            heading="被动语态",
            content="被动语态由 be 加过去分词构成，强调动作的承受者。",
        )
    )
    db.commit()
    assert corpus.index_kb(db).failed == 0
    return db


class TestRegistry:
    def test_all_stages_registered(self) -> None:
        stages = available_stages()
        assert set(stages["pre"]) == {
            "normalize", "lang_detect", "intent_gate", "keywords", "rewrite",
        }
        assert set(stages["retrieve"]) == {"bm25", "vector", "graph"}
        assert stages["fuse"] == ["rrf"]
        assert set(stages["post"]) == {"cite", "compress", "dedup", "threshold"}

    def test_strategies_registered(self) -> None:
        assert set(available_strategies()) == {"naive", "corrective", "self_rag"}

    def test_unknown_stage_raises(self) -> None:
        with pytest.raises(RagConfigError) as excinfo:
            resolve_stages(StageKind.PRE, "normalize,不存在的阶段")
        assert "不存在的阶段" in str(excinfo.value)

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(RagConfigError):
            get_strategy("nope")

    def test_self_rag_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            get_strategy("self_rag")(RagContext(query="x"))

    def test_configured_list_is_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "rag_stages_pre", "normalize,lang_detect")
        ctx = RagContext(query="abandon 怎么用")
        pipeline.strategies.run_stages(ctx, StageKind.PRE, settings.rag_stages_pre)
        # 只配了两个阶段，就只该跑两个，不该把 intent_gate 也跑掉
        assert [trace.stage for trace in ctx.trace] == ["normalize", "lang_detect"]


class TestPreStages:
    def test_normalize_fullwidth(self) -> None:
        ctx = RagContext(query="  ＡＢＡＮＤＯＮ　 ")
        pre.normalize(ctx)
        assert ctx.normalized == "ABANDON"

    def test_lang_detect(self) -> None:
        for query, expected in (
            ("现在完成时怎么构成", "zh"),
            ("present perfect tense", "en"),
            ("abandon 怎么用", "mixed"),
        ):
            ctx = RagContext(query=query)
            pre.normalize(ctx)
            pre.lang_detect(ctx)
            assert ctx.lang == expected, query

    @pytest.mark.parametrize(
        ("query", "reason"),
        [
            ("hi", "输入过短"),
            ("thanks", "寒暄"),
            ("帮我纠正这句话的语法", "纠错类请求"),
            ("please check my grammar", "纠错类请求"),
        ],
    )
    def test_intent_gate_skips(self, query: str, reason: str) -> None:
        ctx = RagContext(query=query)
        pre.normalize(ctx)
        pre.intent_gate(ctx)
        assert ctx.skipped is not None and reason in ctx.skipped

    def test_real_question_not_gated(self) -> None:
        ctx = RagContext(query="现在完成时怎么构成")
        pre.normalize(ctx)
        pre.intent_gate(ctx)
        assert ctx.skipped is None

    def test_keywords_prefer_quoted(self) -> None:
        ctx = RagContext(query='帮我讲讲 "abandon" 这个词')
        pre.normalize(ctx)
        pre.keywords(ctx)
        assert ctx.keywords[0] == "abandon"

    def test_rewrite_resolves_pronoun(self) -> None:
        ctx = RagContext(
            query="这个词怎么用",
            history=[{"role": "user", "content": '我说的是 "abandon"'}],
        )
        pre.normalize(ctx)
        pre.rewrite(ctx)
        assert "abandon" in ctx.retrieval_query


class TestBm25:
    def test_indexes_seeded_corpus(self, seeded: Session) -> None:
        index = retrieve.get_index(seeded)
        assert len(index) >= 313 + 2

    def test_finds_exact_word(self, seeded: Session) -> None:
        ctx = RagContext(query="abandon", db=seeded)
        pre.normalize(ctx)
        retrieve.bm25(ctx)
        assert ctx.candidates
        assert ctx.candidates[0].kind == "word"
        assert "abandon" in ctx.candidates[0].content.lower()

    def test_finds_chinese_chunk(self, seeded: Session) -> None:
        ctx = RagContext(query="现在完成时", db=seeded)
        pre.normalize(ctx)
        retrieve.bm25(ctx)
        assert any("现在完成时" in hit.content for hit in ctx.candidates)

    def test_cache_invalidated_on_change(self, seeded: Session) -> None:
        first = retrieve.get_index(seeded)
        assert retrieve.get_index(seeded) is first
        retrieve.invalidate_index()
        assert retrieve.get_index(seeded) is not first


class TestVectorStage:
    def test_degrades_when_embedding_fails(
        self, seeded: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(text=""):
            raise embeddings.EmbeddingError("挂了")

        # vector 阶段走的是 embed_query，不是 embed
        monkeypatch.setattr(embeddings, "embed_query", boom)
        ctx = RagContext(query="abandon 怎么用", db=seeded)
        pre.normalize(ctx)
        retrieve.vector(ctx)
        assert ctx.candidates == []
        assert any("embedding 不可用" in note for note in ctx.notes)

    def test_word_vectors_lazy_loaded(self, seeded: Session) -> None:
        assert store.get_store().count(store.COLLECTION_WORD) >= 313


class TestGraphStage:
    def test_neighbors_retrieved(self, seeded: Session) -> None:
        from sqlalchemy import select

        from app.models.word import Word

        word = seeded.scalar(select(Word).where(Word.word == "abandon"))
        seeded.add(
            WordRelation(
                head_word_id=word.id, tail_word="give up", relation="synonym", note="近义"
            )
        )
        seeded.commit()

        ctx = RagContext(query="abandon 的近义词", db=seeded)
        pre.normalize(ctx)
        pre.keywords(ctx)
        retrieve.graph(ctx)

        assert any(hit.source == "graph" for hit in ctx.candidates)
        graph_hit = next(hit for hit in ctx.candidates if hit.source == "graph")
        assert "give up" in graph_hit.content
        assert graph_hit.score == 1.0

    def test_no_relations_no_candidates(self, seeded: Session) -> None:
        ctx = RagContext(query="ephemeral 的近义词", db=seeded)
        pre.normalize(ctx)
        pre.keywords(ctx)
        retrieve.graph(ctx)
        assert all(hit.source != "graph" for hit in ctx.candidates)


class TestFusionAndRerank:
    def test_rrf_merges_duplicate_content(self) -> None:
        ctx = RagContext(query="q")
        for source, rank in (("bm25", 1), ("vector", 2)):
            ctx.candidates.append(
                Hit(kind="word", source=source, content="同一段内容", rank=rank)
            )
        ranking.rrf(ctx)
        # 同一内容两路各召回一次，融合后应当只剩一条
        assert len(ctx.candidates) == 1

    def test_rrf_score_scale(self) -> None:
        """RRF 分数量级必须与阈值匹配，否则检索结果会被全部挡掉。"""
        ctx = RagContext(query="q")
        ctx.candidates.append(Hit(kind="word", source="bm25", content="x", rank=1))
        ranking.rrf(ctx)
        assert 0.01 < ctx.candidates[0].score < 0.02
        assert ctx.candidates[0].score >= settings.rag_score_threshold

    def test_graph_hit_keeps_full_score(self) -> None:
        ctx = RagContext(query="q")
        ctx.candidates.append(Hit(kind="relation", source="graph", content="g", rank=3))
        ranking.rrf(ctx)
        assert ctx.candidates[0].score == 1.0

    def test_lexical_boost_prefers_exact_match(self) -> None:
        ctx = RagContext(query="abandon")
        ctx.keywords = ["abandon"]
        ctx.candidates = [
            Hit(kind="word", source="bm25", content="无关内容", score=0.016, rank=1),
            Hit(kind="word", source="bm25", content="abandon 的释义", score=0.016, rank=2),
        ]
        ranking.lexical(ctx)
        assert "abandon" in ctx.candidates[0].content

    def test_llm_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert settings.rag_llm_rerank is False
        ctx = RagContext(query="q")
        ctx.candidates = [Hit(kind="word", source="bm25", content="a", score=1.0, rank=1),
                          Hit(kind="word", source="bm25", content="b", score=0.9, rank=2)]
        ranking.llm(ctx)
        # 开关关闭时不该有任何调用，分数原样保留
        assert ctx.candidates[0].score == 1.0


class TestPostStages:
    def test_threshold_rejects_low_scores(self) -> None:
        ctx = RagContext(query="q")
        ctx.candidates = [Hit(kind="word", source="bm25", content="x", score=0.001, rank=1)]
        post.threshold(ctx)
        assert ctx.final == []
        assert "低于阈值" in (ctx.skipped or "")

    def test_threshold_accepts_graph_hits(self) -> None:
        ctx = RagContext(query="q")
        ctx.candidates = [Hit(kind="relation", source="graph", content="g", score=1.0, rank=1)]
        post.threshold(ctx)
        assert len(ctx.final) == 1

    def test_dedup_removes_similar(self) -> None:
        ctx = RagContext(query="q")
        ctx.final = [
            Hit(kind="chunk", source="bm25", content="这是一段完全相同的文字内容", rank=1),
            Hit(kind="chunk", source="vector", content="这是一段完全相同的文字内容", rank=2),
            Hit(kind="chunk", source="bm25", content="另一段毫不相干的资料", rank=3),
        ]
        post.dedup(ctx)
        assert len(ctx.final) == 2

    def test_compress_respects_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "rag_max_context_chars", 100)
        ctx = RagContext(query="q")
        ctx.final = [Hit(kind="chunk", source="bm25", content="短句。" * 200, rank=1)]
        post.compress(ctx)
        assert sum(len(snippet) for snippet in ctx.compressed.values()) <= 100

    def test_cite_numbers_and_labels(self) -> None:
        ctx = RagContext(query="q")
        ctx.final = [
            Hit(kind="chunk", source="bm25", content="内容甲", rank=1,
                heading="小节", metadata={"name": "grammar"}),
            Hit(kind="word", source="bm25", content="内容乙", rank=2,
                metadata={"word": "abandon"}),
        ]
        post.cite(ctx)
        assert "[1] 来源: grammar #小节" in ctx.context
        assert "[2] 词库词条: abandon" in ctx.context


class TestPipeline:
    def test_real_question_returns_context(
        self, seeded: Session, rag_env: None
    ) -> None:
        result = pipeline.run("现在完成时怎么构成", seeded)
        assert result.skipped is None
        assert result.hits
        assert result.context
        assert result.sources

    def test_smalltalk_is_gated(self, seeded: Session, rag_env: None) -> None:
        result = pipeline.run("hi", seeded)
        assert result.skipped == "输入过短"
        assert result.embedding_calls == 0

    def test_disabled_rag_short_circuits(self, seeded: Session, monkeypatch) -> None:
        monkeypatch.setattr(settings, "rag_enabled", False)
        result = pipeline.run("现在完成时怎么构成", seeded)
        assert "未启用" in (result.skipped or "")

    def test_empty_query_short_circuits(self, seeded: Session, rag_env: None) -> None:
        result = pipeline.run("   ", seeded)
        assert result.skipped is not None

    def test_embedding_failure_never_raises(
        self, seeded: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """embedding 全挂也不能阻断对话——这是 RAG 的底线。

        而且不该退化成「什么都不给」：BM25 与图谱两路不依赖向量，
        仍然能召回内容。降级要降到还剩什么用什么，不是直接归零。
        """
        def boom(texts, use_cache=True):
            raise embeddings.EmbeddingError("挂了")

        monkeypatch.setattr(embeddings, "embed", boom)
        monkeypatch.setattr(embeddings, "embed_query", lambda text: boom([text]))
        result = pipeline.run("现在完成时怎么构成", seeded)

        assert result.embedding_calls == 0
        assert result.hits, "BM25 与图谱两路不依赖向量，仍应有召回"
        assert any(hit.source in ("bm25", "graph") for hit in result.hits)
        assert result.context

    def test_unknown_strategy_never_raises(
        self, seeded: Session, rag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """配错策略名不能让对话挂掉，管线要兜住并降级。"""
        monkeypatch.setattr(settings, "rag_strategy", "不存在的策略")
        result = pipeline.run("现在完成时怎么构成", seeded)
        assert result.skipped is not None

    def test_self_rag_degrades_to_naive(
        self, seeded: Session, rag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rag_strategy", "self_rag")
        result = pipeline.run("现在完成时怎么构成", seeded)
        # 未实现的策略不该让对话挂掉，而是回落到 naive
        assert result.skipped is None
        assert result.hits

    def test_trace_records_every_stage(self, seeded: Session, rag_env: None) -> None:
        result = pipeline.run("现在完成时怎么构成", seeded)
        stages = [trace.stage for trace in result.trace]
        assert "normalize" in stages
        assert "intent_gate" in stages
        assert "rrf" in stages
        assert all(trace.duration_ms >= 0 for trace in result.trace)

    def test_default_path_makes_no_llm_call(
        self, seeded: Session, rag_env: None
    ) -> None:
        """2 秒首字延迟预算的前提：默认路径零额外 LLM 调用。"""
        assert settings.rag_llm_rerank is False
        result = pipeline.run("现在完成时怎么构成", seeded)
        assert result.embedding_calls <= 1


class TestIndexingLazyLoad:
    """索引触发点：没有后台进程，靠启动预热 + 检索兜底。

    这两个缺口都曾让 RAG 只剩 BM25 一路在工作，而症状只是「向量路没召回」，
    极难从现象反查，所以各留一条回归。
    """

    def test_kb_pending_indexed_on_retrieval(
        self, seeded: Session, rag_env: None, db: Session
    ) -> None:
        from sqlalchemy import select

        from app.models.kb import DOC_PENDING, KnowledgeDocument
        from app.rag.store import COLLECTION_KB

        # 把文档退回待索引，模拟「上传后还没检索过」
        for document in db.scalars(select(KnowledgeDocument)).all():
            document.status = DOC_PENDING
        db.commit()
        store.get_store().replace_collection(COLLECTION_KB)
        assert store.get_store().count(COLLECTION_KB) == 0

        ctx = RagContext(query="现在完成时", db=db)
        pre.normalize(ctx)
        retrieve.vector(ctx)

        assert store.get_store().count(COLLECTION_KB) > 0
        assert any(hit.kind == "chunk" for hit in ctx.candidates)

    def test_ensure_word_index_is_idempotent(self, seeded: Session, db: Session) -> None:
        from app.rag.store import COLLECTION_WORD

        # seeded 夹具已经建过索引，先清空才能验证「建一次、之后不再重复建」
        store.get_store().replace_collection(COLLECTION_WORD)
        assert store.get_store().count(COLLECTION_WORD) == 0

        first = corpus.ensure_word_index(db)
        assert first > 0
        assert corpus.ensure_word_index(db) == 0
        assert store.get_store().count(COLLECTION_WORD) == first

    def test_batch_size_respects_provider_limit(self) -> None:
        """当前供应商硬上限 10 条，超了直接 400。

        失败是静默降级的，症状只会表现为「向量路没召回」，所以钉在这里。
        """
        assert settings.embedding_batch_size <= 10

    def test_warm_up_is_non_blocking(self, seeded: Session) -> None:
        """预热必须在后台线程里跑，不能阻塞启动路径。"""
        import threading

        before = threading.active_count()
        corpus.warm_up(db_factory=SessionLocal)
        assert threading.active_count() > before


class TestVectorStoreContract:
    def test_null_store_is_silent(self) -> None:
        null = NullVectorStore()
        assert null.query("c", [0.0] * DIM) == []
        assert null.count("c") == 0
        assert null.delete("c", [1]) == 0

    def test_dimension_mismatch_is_explained(self, tmp_path) -> None:
        vector_store = FaissVectorStore(tmp_path / "dim")
        with pytest.raises(ValueError, match="embedding_dimension"):
            vector_store.upsert("c", [1], [[0.0, 1.0]], ["x"])
