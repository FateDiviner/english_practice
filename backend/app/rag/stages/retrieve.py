"""检索阶段：BM25、向量、词汇图谱三路召回。

三路各有各的强项——BM25 抓精确词形，向量抓语义改写，图谱抓关系邻居。
任何一路单用都有明显盲区，靠后面的 RRF 融合取长补短。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select

from app.config import get_settings
from app.constants import STATUS_ACTIVE
from app.models.kb import DOC_READY, KbChunk, KnowledgeDocument
from app.models.relation import RELATION_LABELS, RELATION_SYNONYM, WordRelation
from app.models.word import Word
from app.rag import corpus, embeddings, store
from app.rag.registry import register_stage
from app.rag.store import COLLECTION_KB, COLLECTION_WORD
from app.rag.types import Hit, RagContext, StageKind

_TOKEN = re.compile(r"[A-Za-z]+|[㐀-鿿]")

# BM25 参数。k1=1.5 / b=0.75 是检索领域的常用起点，语料量级差异下足够稳
_BM25_K1 = 1.5
_BM25_B = 0.75

settings = get_settings()

# 进程内缓存：语料没变时不该每次检索都重读全表
_CACHE: "Bm25Index | None" = None
_CACHE_SIGNATURE: tuple | None = None


def _tokenize(text: str) -> list[str]:
    """英文按词、中文按单字。

    中文用单字而不是 2-gram：BM25 的 IDF 对单字更稳，
    而 2-gram 会让长查询的分词组合爆炸。
    """
    return [token.lower() for token in _TOKEN.findall(text)]


@dataclass
class Bm25Index:
    """一个语料的 BM25 索引。"""

    doc_ids: list[int] = field(default_factory=list)
    # 与 doc_ids 一一对应的原文，命中后直接当候选内容
    texts: list[str] = field(default_factory=list)
    # kind: chunk / word
    kinds: list[str] = field(default_factory=list)
    metadatas: list[dict] = field(default_factory=list)
    _term_freqs: list[Counter] = field(default_factory=list)
    _doc_len: list[int] = field(default_factory=list)
    _df: Counter = field(default_factory=Counter)
    _avg_len: float = 0.0

    def build(self, doc_ids, texts, kinds, metadatas) -> None:
        self.doc_ids = list(doc_ids)
        self.texts = list(texts)
        self.kinds = list(kinds)
        self.metadatas = list(metadatas)
        self._term_freqs = [Counter(_tokenize(text)) for text in self.texts]
        self._doc_len = [sum(freq.values()) for freq in self._term_freqs]
        self._df = Counter()
        for freq in self._term_freqs:
            for term in freq:
                self._df[term] += 1
        total = sum(self._doc_len)
        self._avg_len = (total / len(self._doc_len)) if self._doc_len else 0.0

    def __len__(self) -> int:
        return len(self.doc_ids)

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        if not self._term_freqs:
            return []
        terms = _tokenize(query)
        if not terms:
            return []

        total_docs = len(self._term_freqs)
        scores: list[float] = [0.0] * total_docs
        for term in set(terms):
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            for index, freq in enumerate(self._term_freqs):
                hits = freq.get(term, 0)
                if not hits:
                    continue
                length_norm = 1 - _BM25_B + _BM25_B * (
                    self._doc_len[index] / (self._avg_len or 1.0)
                )
                scores[index] += idf * (
                    hits * (_BM25_K1 + 1)
                    / (hits + _BM25_K1 * length_norm)
                )

        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        return [(index, score) for index, score in ranked[:top_k] if score > 0]


def _signature(db: Session) -> tuple:
    """语料版本号：文档数、切块数、词数任一变化都要重建索引。

    必须用 count 而不是 scalar(select(id))——后者取的是最小主键，
    新增文档不会改变它，缓存会一直不失效。
    """
    from sqlalchemy import func

    def _count(model, *where) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return (
        _count(KnowledgeDocument, KnowledgeDocument.status == DOC_READY),
        _count(KbChunk),
        _count(Word, Word.status == STATUS_ACTIVE),
    )


def get_index(db: Session) -> Bm25Index:
    """取 BM25 索引，语料没变就复用缓存。"""
    global _CACHE, _CACHE_SIGNATURE
    signature = _signature(db)
    if _CACHE is not None and _CACHE_SIGNATURE == signature:
        return _CACHE

    index = Bm25Index()
    doc_ids: list[int] = []
    texts: list[str] = []
    kinds: list[str] = []
    metadatas: list[dict] = []

    documents = {
        document.id: document
        for document in db.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.status == DOC_READY)
        ).all()
    }
    for chunk in db.scalars(select(KbChunk).order_by(KbChunk.id)).all():
        document = documents.get(chunk.document_id)
        if document is None:
            continue
        doc_ids.append(chunk.id)
        texts.append(corpus.chunk_document(chunk, document))
        kinds.append("chunk")
        metadatas.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "name": document.name,
                "heading": chunk.heading,
            }
        )

    for word in db.scalars(
        select(Word).where(Word.status == STATUS_ACTIVE).order_by(Word.id)
    ).all():
        doc_ids.append(word.id)
        texts.append(corpus.word_document(word))
        kinds.append("word")
        metadatas.append(
            {"word_id": word.id, "word": word.word, "translation": word.translation}
        )

    index.build(doc_ids, texts, kinds, metadatas)
    _CACHE = index
    _CACHE_SIGNATURE = signature
    return index


def invalidate_index() -> None:
    """文档或词库变更后调用，让下一次检索重建索引。"""
    global _CACHE, _CACHE_SIGNATURE
    _CACHE = None
    _CACHE_SIGNATURE = None


@register_stage(StageKind.RETRIEVE, "bm25")
def bm25(ctx: RagContext) -> None:
    """词法召回。抓精确词形，是中文提问里英文原词的唯一可靠来源。"""
    db = ctx.db
    if db is None:
        return
    index = get_index(db)
    query = ctx.retrieval_query or ctx.normalized or ctx.query
    for position, (doc_index, score) in enumerate(
        index.search(query, top_k=settings.rag_top_k * 3), start=1
    ):
        ctx.candidates.append(
            Hit(
                kind=index.kinds[doc_index],
                source="bm25",
                content=index.texts[doc_index],
                score=score,
                rank=position,
                metadata=dict(index.metadatas[doc_index]),
            )
        )


@register_stage(StageKind.RETRIEVE, "vector")
def vector(ctx: RagContext) -> None:
    """语义召回。抓改写与同义，是中文提问命中英文原文的主要通道。

    embedding 失败时静默跳过：检索拿不到向量不该阻断对话。
    """
    db = ctx.db
    if db is None:
        return
    # 两条懒加载入口都在这里触发：没有后台进程，靠第一次检索把索引建起来
    corpus.ensure_kb_index(db)
    corpus.ensure_word_index(db)

    query = ctx.retrieval_query or ctx.normalized or ctx.query
    try:
        query_vector = embeddings.embed_query(query)
    except embeddings.EmbeddingError:
        ctx.notes.append("embedding 不可用，向量路跳过")
        return
    ctx.embedding_calls += 1

    vector_store = store.get_store()
    for collection, kind in ((COLLECTION_KB, "chunk"), (COLLECTION_WORD, "word")):
        for position, row in enumerate(
            vector_store.query(collection, query_vector, top_k=settings.rag_top_k * 2), start=1
        ):
            ctx.candidates.append(
                Hit(
                    kind=kind,
                    source="vector",
                    content=row["document"],
                    score=row["score"],
                    rank=position,
                    heading=row["metadata"].get("heading", ""),
                    metadata=dict(row["metadata"]),
                )
            )


@register_stage(StageKind.RETRIEVE, "graph")
def graph(ctx: RagContext) -> None:
    """词汇图谱召回：命中词的关系邻居一并作为候选。

    这一路专治纯向量答不好的问题——「abandon 的派生词」「和 give up 有什么
    区别」「常见搭配是什么」。零 LLM 成本，只查一张表。
    """
    db = ctx.db
    if db is None or not ctx.keywords:
        return

    matched = _match_words(db, ctx.keywords[:8])
    if not matched:
        return

    for position, word in enumerate(matched, start=1):
        relations = db.scalars(
            select(WordRelation).where(WordRelation.head_word_id == word.id)
        ).all()
        if not relations:
            continue
        # 近义词排在最前：「和 X 有什么区别」是最高频的提问形态
        ordered = sorted(
            relations, key=lambda item: 0 if item.relation == RELATION_SYNONYM else 1
        )
        parts = [f"{word.word} {word.translation}"]
        for relation in ordered:
            label = RELATION_LABELS.get(relation.relation, relation.relation)
            note = f"：{relation.note}" if relation.note else ""
            parts.append(f"{label} {relation.tail_word}{note}")
        ctx.candidates.append(
            Hit(
                kind="relation",
                source="graph",
                content="\n".join(parts),
                # 关系边是人工维护的，置信度高于向量的模糊命中
                score=1.0,
                rank=position,
                heading=f"{word.word} 的词汇关系",
                metadata={
                    "word_id": word.id,
                    "word": word.word,
                    "relations": [relation.tail_word for relation in ordered],
                },
            )
        )


def _match_words(db: Session, keywords: list[str]) -> list[Word]:
    """按关键词找出词库里的对应词条，去重且保序。"""
    wanted = [keyword.lower() for keyword in keywords if keyword.isascii()]
    if not wanted:
        return []
    rows = db.scalars(
        select(Word)
        .where(Word.status == STATUS_ACTIVE, Word.word.in_(wanted))
        .order_by(Word.id)
    ).all()
    return list(rows)
