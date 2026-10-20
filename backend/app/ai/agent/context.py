"""Agent 工具结果的合并、去重、引用重编号与上下文压缩。"""

from __future__ import annotations

import re

from app.config import get_settings
from app.rag.types import Hit, RagResult
from app.schemas.chat import ChatSource

_BLOCK_START = re.compile(r"(?m)^\[\d+\]\s")


def _split_cited_blocks(context: str) -> list[str]:
    """按 RAG cite 阶段生成的 [n] 标记切出正文，不含编号本身。"""

    if not context.strip():
        return []
    matches = list(_BLOCK_START.finditer(context))
    if not matches:
        return [context.strip()]
    blocks: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(context)
        body = context[match.end():end].strip()
        if body:
            blocks.append(body)
    return blocks


def _hit_source(hit: Hit, index: int) -> ChatSource:
    label = hit.heading or hit.metadata.get("word") or hit.metadata.get("name") or ""
    return ChatSource(
        index=index,
        kind=hit.kind,
        label=str(label)[:200],
        source=hit.source,
    )


def _source_key(hit: Hit, body: str) -> str:
    metadata = hit.metadata
    object_id = (
        metadata.get("chunk_id")
        or metadata.get("word_id")
        or metadata.get("document_id")
        or metadata.get("relation")
    )
    if object_id is not None:
        return f"{hit.kind}:{object_id}"
    normalized = "".join(body.lower().split())
    return f"{hit.kind}:{normalized[:160]}"


def _word_source(item: dict[str, str]) -> ChatSource:
    return ChatSource(
        index=1,
        kind="word",
        label=item.get("word", "")[:200],
        source="wordbank",
    )


def compile_references(
    retrievals: list[RagResult],
    word_results: list[dict[str, str]],
) -> tuple[str, list[ChatSource]]:
    """合并多次检索与单词查询，统一生成最终编号和来源列表。"""

    items: list[tuple[str, ChatSource, str]] = []
    seen: set[str] = set()

    for item in word_results:
        key = f"word:{item.get('id') or item.get('word', '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        lines = [
            "Exact word-bank entry",
            f"{item.get('word', '')} {item.get('phonetic', '')}".strip(),
            item.get("translation", ""),
        ]
        if item.get("example_en"):
            lines.append(f"Example: {item['example_en']}")
        if item.get("example_cn"):
            lines.append(f"Example translation: {item['example_cn']}")
        body = "\n".join(line for line in lines if line)
        items.append((body, _word_source(item), key))

    for result in retrievals:
        if not result.hits:
            continue
        bodies = _split_cited_blocks(result.context)
        if len(bodies) != len(result.hits):
            bodies = []
            for hit in result.hits:
                label = hit.heading or hit.metadata.get("word") or hit.metadata.get("name")
                prefix = f"{label}\n" if label else ""
                bodies.append(prefix + hit.content)
        for position, hit in enumerate(result.hits):
            body = bodies[position] if position < len(bodies) else hit.content
            key = _source_key(hit, body)
            if key in seen:
                continue
            seen.add(key)
            items.append((body, _hit_source(hit, 1), key))

    if not items:
        return "", []

    budget = max(get_settings().rag_max_context_chars, 1000)
    blocks: list[str] = []
    sources: list[ChatSource] = []
    used = 0
    for body, source, _key in items:
        remaining = budget - used
        if remaining <= 0:
            break
        if len(body) > remaining:
            body = body[:remaining].rstrip()
            if len(body) < 20:
                break
        index = len(blocks) + 1
        blocks.append(f"[{index}] {body}")
        sources.append(source.model_copy(update={"index": index}))
        used += len(body) + 16

    return "\n\n".join(blocks), sources
