"""后处理阶段：阈值门控、去重、上下文压缩、引用标注。"""

from __future__ import annotations

import re

from app.config import get_settings
from app.rag.registry import register_stage
from app.rag.types import RagContext, StageKind

settings = get_settings()

_SENTENCE = re.compile(r"[^。.!?！？\n]+[。.!?！？]?")


@register_stage(StageKind.POST, "threshold")
def threshold(ctx: RagContext) -> None:
    """最高分低于阈值则放弃全部上下文。

    学习场景里，自信地答错比「知识库里没有相关信息」危害大得多。
    注入一段不相关的内容，模型会顺着它编；什么都不注入，模型至少知道自己
    没有依据。
    """
    if not ctx.candidates:
        ctx.skipped = ctx.skipped or "没有召回任何内容"
        ctx.final = []
        return

    best = max(hit.score for hit in ctx.candidates)
    if best < settings.rag_score_threshold:
        ctx.skipped = f"最高相关度 {best:.3f} 低于阈值 {settings.rag_score_threshold}"
        ctx.final = []
        ctx.candidates = []
        return

    ctx.final = list(ctx.candidates)


@register_stage(StageKind.POST, "dedup")
def dedup(ctx: RagContext) -> None:
    """去掉几乎相同的段落。

    BM25 与向量两路会把同一段各召回一次；不合并的话上下文里会出现两遍
    一模一样的内容，白白吃掉字符预算。
    """
    kept = []
    seen_keys: list[str] = []
    for hit in ctx.final:
        key = hit.dedup_key[:160]
        if any(_similar(key, other) for other in seen_keys):
            continue
        seen_keys.append(key)
        kept.append(hit)
    ctx.final = kept


def _similar(left: str, right: str) -> bool:
    """token 集合 Jaccard 超过 0.8 视为重复。"""
    if left == right:
        return True
    if not left or not right:
        return False
    a, b = set(left), set(right)
    union = len(a | b)
    return bool(union) and len(a & b) / union > 0.8


@register_stage(StageKind.POST, "compress")
def compress(ctx: RagContext) -> None:
    """把候选压进字符预算。

    预算紧张时优先保留排名靠前的，并对每块取与查询最相关的句子为中心开窗，
    而不是机械地截断——截断经常把关键句切掉一半。
    """
    budget = settings.rag_max_context_chars
    if budget <= 0:
        ctx.final = []
        return

    kept = []
    used = 0
    for hit in ctx.final:
        snippet = _best_window(hit.content, ctx.keywords or [ctx.retrieval_query or ctx.query])
        remaining = budget - used
        if remaining <= 0:
            break
        if len(snippet) > remaining:
            snippet = snippet[:remaining].rstrip()
            if len(snippet) < 20:
                break
        kept.append((hit, snippet))
        used += len(snippet)

    ctx.final = [hit for hit, _ in kept]
    ctx.compressed = {id(hit): snippet for hit, snippet in kept}


def _best_window(text: str, keywords: list[str]) -> str:
    """取包含关键词最多的句子附近的一段。"""
    limit = min(600, settings.rag_max_context_chars)
    if len(text) <= limit:
        return text

    sentences = [match.group(0).strip() for match in _SENTENCE.finditer(text)]
    sentences = [sentence for sentence in sentences if sentence]
    if not sentences:
        return text[:limit]

    lowered = [keyword.lower() for keyword in keywords if keyword]
    best_index, best_hits = 0, -1
    for index, sentence in enumerate(sentences):
        hits = sum(1 for keyword in lowered if keyword in sentence.lower())
        if hits > best_hits:
            best_index, best_hits = index, hits

    start = max(0, best_index - 1)
    window: list[str] = []
    used = 0
    for sentence in sentences[start:]:
        if used + len(sentence) > limit:
            break
        window.append(sentence)
        used += len(sentence)
    return "\n".join(window) if window else text[:limit]


@register_stage(StageKind.POST, "cite")
def cite(ctx: RagContext) -> None:
    """给每块加上引用编号与来源，拼成最终注入 prompt 的上下文。

    编号要与给模型的指令对齐，否则模型引用的 [1] 指不到任何东西——
    用户核对时会发现张冠李戴，比不引用更糟。
    """
    if not ctx.final:
        ctx.context = ""
        return

    blocks: list[str] = []
    snippets = getattr(ctx, "compressed", {})
    for index, hit in enumerate(ctx.final, start=1):
        snippet = snippets.get(id(hit)) or hit.content
        label = _source_label(hit)
        prefix = f"[{index}] {label}\n" if label else f"[{index}]\n"
        blocks.append(prefix + snippet)
    ctx.context = "\n\n".join(blocks)


def _source_label(hit) -> str:
    """来源标签：文档名#小节 / 词条 / 词汇关系。"""
    if hit.kind == "chunk":
        name = hit.metadata.get("name", "知识库")
        heading = hit.heading or hit.metadata.get("heading", "")
        return f"来源: {name}" + (f" #{heading}" if heading else "")
    if hit.kind == "word":
        word = hit.metadata.get("word", "")
        return f"词库词条: {word}" if word else "词库词条"
    if hit.kind == "relation":
        word = hit.metadata.get("word", "")
        return f"词汇关系: {word}" if word else "词汇关系"
    return hit.source
