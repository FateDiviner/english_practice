"""语料装载：知识库切块 + 词库词条（懒加载）。

词库向量刻意不在启动时构建——313 个词条就是 313 次 embedding 调用，
放在启动路径上会让后端冷启动从几百毫秒变成十几秒。首次检索时才建，
之后只补新增的词。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STATUS_ACTIVE
from app.models.kb import DOC_READY, KbChunk, KnowledgeDocument
from app.models.relation import RELATION_LABELS, RELATION_SYNONYM, WordRelation
from app.models.word import Word
from app.rag import embeddings, store
from app.rag.store import COLLECTION_KB, COLLECTION_WORD

FAILED_STATUS = "failed"
READY_STATUS = "ready"


@dataclass
class IndexStats:
    """一次索引的结果，管理端展示用。"""

    indexed: int = 0
    failed: int = 0


def word_document(word: Word) -> str:
    """词条拼成一段可检索文本，中英都在里面。

    中英混排是刻意的：中文提问要能命中英文词条，反过来也一样。
    """
    return (
        f"{word.word} {word.phonetic}\n"
        f"{word.translation}\n"
        f"{word.example_en}\n"
        f"{word.example_cn}"
    ).strip()


def chunk_document(chunk: KbChunk, document: KnowledgeDocument) -> str:
    heading = f"## {chunk.heading}\n" if chunk.heading else ""
    return f"{heading}{chunk.content}".strip()


def _chunk_rows(db: Session) -> list[tuple[KbChunk, KnowledgeDocument]]:
    """全部 ready 文档的切块，按文档与序号排列。"""
    documents = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.status == DOC_READY)
        .order_by(KnowledgeDocument.id)
    ).all()
    pairs: list[tuple[KbChunk, KnowledgeDocument]] = []
    for document in documents:
        chunks = db.scalars(
            select(KbChunk)
            .where(KbChunk.document_id == document.id)
            .order_by(KbChunk.seq)
        ).all()
        pairs.extend((chunk, document) for chunk in chunks)
    return pairs


def index_kb(db: Session) -> IndexStats:
    """把全部 ready 文档的切块一次性向量化。

    整表重建而不是增量：文档重新上传时旧切块必须消失，否则同一篇资料会
    留下重复块，检索结果里出现两段一模一样的内容。
    """
    stats = IndexStats()
    pairs = _chunk_rows(db)
    vector_store = store.get_store()
    vector_store.replace_collection(COLLECTION_KB)
    if not pairs:
        return stats

    documents_text = [chunk_document(chunk, document) for chunk, document in pairs]
    try:
        vectors = embeddings.embed(documents_text)
    except embeddings.EmbeddingError:
        stats.failed = len(pairs)
        _mark_all_failed(db)
        return stats

    vector_store.upsert(
        COLLECTION_KB,
        ids=[chunk.id for chunk, _ in pairs],
        embeddings=vectors,
        documents=documents_text,
        metadatas=[
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "name": document.name,
                "heading": chunk.heading,
                "seq": chunk.seq,
            }
            for chunk, document in pairs
        ],
    )
    stats.indexed = len(pairs)
    return stats


def index_document(db: Session, document_id: int) -> bool:
    """索引单份文档，成功后把它标记为 ready。

    仍走 index_kb 的整表重建路径：向量库里只有一份 KB 集合，单独写一份
    文档会与「其余文档已在库里」的前提冲突。
    """
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        return False
    if document.status == DOC_READY:
        stats = index_kb(db)
        return stats.failed == 0

    document.status = DOC_READY
    db.commit()
    stats = index_kb(db)
    return stats.failed == 0


def _mark_all_failed(db: Session) -> None:
    """embedding 整体不可用时，把受影响文档全部标成失败并写明原因。

    只标一份会让其余文档永远停在 ready 却查不到，排查时很难联想到是同一次
    embedding 失败。
    """
    documents = db.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.status == DOC_READY)
    ).all()
    for document in documents:
        document.status = FAILED_STATUS
        document.error = "向量化失败，请检查 embedding 配置后重新索引"
    db.commit()


def ensure_word_index(db: Session) -> int:
    """词库向量懒加载：首次检索时构建，之后只补新增的词。

    返回本次新写入的词条数。embedding 不可用时静默返回 0，
    检索会退化到 BM25 与图谱两路。
    """
    words = db.scalars(
        select(Word).where(Word.status == STATUS_ACTIVE).order_by(Word.id)
    ).all()
    if not words:
        return 0

    vector_store = store.get_store()
    indexed = vector_store.ids(COLLECTION_WORD)
    pending = [word for word in words if word.id not in indexed]
    if not pending:
        return 0

    try:
        vectors = embeddings.embed([word_document(word) for word in pending])
    except embeddings.EmbeddingError:
        return 0

    vector_store.upsert(
        COLLECTION_WORD,
        ids=[word.id for word in pending],
        embeddings=vectors,
        documents=[word_document(word) for word in pending],
        metadatas=[
            {
                "word_id": word.id,
                "word": word.word,
                "translation": word.translation,
                "phonetic": word.phonetic,
            }
            for word in pending
        ],
    )
    return len(pending)


def graph_document(db: Session, word: Word) -> str:
    """把词条的关系邻居拼成一段文本，供 graph 检索路产生候选。

    近义词排在最前：「和 give up 有什么区别」是最高频的提问形态。
    """
    relations = db.scalars(
        select(WordRelation).where(WordRelation.head_word_id == word.id)
    ).all()
    if not relations:
        return ""

    parts = [f"{word.word} {word.translation}"]
    ordered = sorted(
        relations, key=lambda item: 0 if item.relation == RELATION_SYNONYM else 1
    )
    for relation in ordered:
        label = RELATION_LABELS.get(relation.relation, relation.relation)
        note = f"：{relation.note}" if relation.note else ""
        parts.append(f"{label} {relation.tail_word}{note}")
    return "\n".join(parts)


def remove_document_vectors(document_id: int, chunk_ids: list[int]) -> int:
    """删文档时把它的切块向量一并摘掉，返回摘掉的条数。"""
    if not chunk_ids:
        return 0
    return store.get_store().delete(COLLECTION_KB, chunk_ids)


def remove_word_vectors(word_ids: list[int]) -> int:
    """删词或下架词时摘掉它的向量，避免检索命中已不可用的词。"""
    if not word_ids:
        return 0
    return store.get_store().delete(COLLECTION_WORD, word_ids)
