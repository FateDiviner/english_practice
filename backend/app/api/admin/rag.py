"""管理端 RAG 调试路由。

调阈值、加减阶段全靠这几条接口——没有 trace 就只能盲调。
不落库：trace 是一次性的观测数据，存表只会越积越多且没有回看价值，
需要留存时由调用方自己复制走。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import get_settings
from app.db import get_db
from app.models.user import User
from app.rag import embeddings, store
from app.rag.pipeline import run
from app.rag.registry import available_stages, available_strategies
from app.rag.types import RagResult
from app.rag.types import Hit as RagHit
from app.schemas.admin import RagHitOut, RagPreviewOut

settings = get_settings()

router = APIRouter(prefix="/api/admin/rag", tags=["admin-rag"])


def _to_hit_out(rank: int, hit: RagHit) -> RagHitOut:
    return RagHitOut(
        rank=rank,
        score=round(hit.score, 6),
        source=hit.source,
        kind=hit.kind,
        content=hit.content[:500],
        heading=hit.heading,
        metadata=hit.metadata,
    )


@router.get("/config")
def config(_admin: User = Depends(require_admin)) -> dict:
    """当前生效的 RAG 配置与可选阶段，调试页据此渲染。"""
    return {
        "enabled": settings.rag_enabled,
        "strategy": settings.rag_strategy,
        "llm_rerank": settings.rag_llm_rerank,
        "top_k": settings.rag_top_k,
        "score_threshold": settings.rag_score_threshold,
        "max_context_chars": settings.rag_max_context_chars,
        "embedding_model": settings.embedding_model,
        "stages": {
            "pre": settings.rag_stages_pre,
            "retrieve": settings.rag_stages_retrieve,
            "fuse": settings.rag_stages_fuse,
            "rerank": settings.rag_stages_rerank,
            "post": settings.rag_stages_post,
        },
        "available_stages": available_stages(),
        "available_strategies": available_strategies(),
        "vector_counts": {
            "kb_chunks": store.get_store().count(store.COLLECTION_KB),
            "word_chunks": store.get_store().count(store.COLLECTION_WORD),
        },
    }


@router.get("/health")
def health(_admin: User = Depends(require_admin)) -> dict:
    """embedding 与向量库是否可用。失败只返回 False，不抛。"""
    return {
        "embedding": embeddings.ping(),
        "kb_chunks": store.get_store().count(store.COLLECTION_KB),
        "word_chunks": store.get_store().count(store.COLLECTION_WORD),
    }


@router.post("/preview", response_model=RagPreviewOut)
def preview(
    payload: dict,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RagPreviewOut:
    """试跑一次检索，返回完整 trace 与全部候选。

    与对话里的检索走同一条管线，所以调试页看到的排序就是线上会用的排序。
    """
    query = str(payload.get("query") or "").strip()
    if not query:
        return RagPreviewOut(query="", lang="en", skipped="问题不能为空", strategy="")

    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []

    result: RagResult = run(query, db, history=history)
    return RagPreviewOut(
        query=query,
        lang=result.lang,
        skipped=result.skipped,
        strategy=settings.rag_strategy,
        hits=[_to_hit_out(index, hit) for index, hit in enumerate(result.hits, start=1)],
        context=result.context,
        trace=[
            {
                "stage": trace.stage,
                "kind": trace.kind,
                "duration_ms": trace.duration_ms,
                "input_count": trace.input_count,
                "output_count": trace.output_count,
                "note": trace.note,
            }
            for trace in result.trace
        ],
    )
