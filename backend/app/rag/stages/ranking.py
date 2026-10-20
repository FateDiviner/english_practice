"""融合与重排阶段。"""

from __future__ import annotations

from app.config import get_settings
from app.rag.registry import register_stage
from app.rag.types import Hit, RagContext, StageKind

# RRF 的平滑常数。60 是检索领域的常用取值，能压掉排名靠前的偶然优势，
# 让多路融合更看重「稳定出现在前列」而不是「某一路分数特别高」
_RRF_K = 60

settings = get_settings()


@register_stage(StageKind.FUSE, "rrf")
def rrf(ctx: RagContext) -> None:
    """倒数排名融合：score = Σ 1/(k + rank_i)。

    免调参是它最大的价值——BM25 的分数量纲与余弦相似度完全不同，
    直接加权求和需要反复调权重，而 RRF 只看排名，天然免疫量纲问题。

    标度要记住：单路第一名的分是 1/61 ≈ 0.0164，三路同时第一也不过 0.049。
    rag_score_threshold 必须落在这个量级上，否则 BM25 与向量的命中会被
    阈值全部挡掉，RAG 等于白接。
    """
    if not ctx.candidates:
        return

    # 同一块内容可能被多路各召回一次，融合前先按去重键合并，取最好的排名
    best: dict[str, Hit] = {}
    for hit in ctx.candidates:
        key = f"{hit.kind}:{hit.dedup_key[:120]}"
        existing = best.get(key)
        if existing is None or hit.rank < existing.rank:
            best[key] = hit

    fused: list[Hit] = []
    for hit in best.values():
        # graph 路给的是人工维护的关系，直接给满分不参与排名融合，
        # 否则它在三路里会被 BM25 与向量的名次稀释掉
        score = 1.0 if hit.source == "graph" else 1.0 / (_RRF_K + hit.rank)
        fused.append(
            Hit(
                kind=hit.kind,
                source=hit.source,
                content=hit.content,
                score=score,
                rank=0,
                heading=hit.heading,
                metadata=dict(hit.metadata),
            )
        )

    fused.sort(key=lambda item: item.score, reverse=True)
    for index, hit in enumerate(fused, start=1):
        hit.rank = index
    ctx.candidates = fused[: settings.rag_top_k * 3]


@register_stage(StageKind.RERANK, "lexical")
def lexical(ctx: RagContext) -> None:
    """精确命中加分：查询里的词在候选里出现，说明这条更贴题。

    这一步补的是 RRF 的盲区——RRF 只看排名，会把「恰好精确命中查询词」
    和「语义相近但没提这个词」排成一样。
    """
    keywords = [keyword for keyword in ctx.keywords if len(keyword) >= 3]
    if not keywords or not ctx.candidates:
        return

    for hit in ctx.candidates:
        lowered = hit.content.lower()
        hits = sum(1 for keyword in keywords if keyword in lowered)
        # 每命中一个词加固定权重；上限压在 0.5，避免词法命中完全盖过语义
        hit.score += min(hits * 0.05, 0.5)

    ctx.candidates.sort(key=lambda item: item.score, reverse=True)
    for index, hit in enumerate(ctx.candidates, start=1):
        hit.rank = index
    ctx.candidates = ctx.candidates[: settings.rag_top_k]


@register_stage(StageKind.RERANK, "llm")
def llm(ctx: RagContext) -> None:
    """用模型重排候选。默认关闭——每次多一轮调用会吃掉首字延迟预算。

    失败时静默保留原排序：重排是锦上添花，不该因为它挂掉而丢掉已经
    召回的内容。
    """
    if not settings.rag_llm_rerank or len(ctx.candidates) < 2:
        return
    try:
        scores = _score_with_model(ctx)
    except Exception:  # noqa: BLE001 - 重排失败必须回落，不能阻断对话
        ctx.notes.append("模型重排失败，保留原排序")
        return
    if not scores or len(scores) != len(ctx.candidates):
        return

    for hit, score in zip(ctx.candidates, scores):
        hit.score += score * 0.3
    ctx.candidates.sort(key=lambda item: item.score, reverse=True)
    for index, hit in enumerate(ctx.candidates, start=1):
        hit.rank = index


def _score_with_model(ctx: RagContext) -> list[float] | None:
    """让模型给每条候选打 0~1 的相关度分。"""
    import json
    import urllib.request

    if not (settings.ai_base_url and settings.ai_api_key):
        return None

    listing = "\n".join(
        f"{index}. {hit.content[:300]}" for index, hit in enumerate(ctx.candidates, 1)
    )
    prompt = (
        "你是英语学习资料检索的评分员。给下面每条资料打 0 到 1 的相关度分，"
        "1 表示直接回答了问题，0 表示完全无关。只输出一个 JSON 数组，不要解释。\n\n"
        f"问题：{ctx.retrieval_query or ctx.query}\n\n资料：\n{listing}"
    )
    body = json.dumps(
        {
            "model": settings.ai_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        settings.ai_base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    text = payload["choices"][0]["message"]["content"].strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        return None
    return [float(item) for item in json.loads(text[start : end + 1])]
