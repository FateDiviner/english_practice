"""实时纠错区块的结构化解析。

模型输出中约定携带：
[语法指正]
- 原因说明

[地道表达]
- 更地道的表达 1
- 更地道的表达 2

此处将其拆分为前端可直接渲染的 FeedbackBlock。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.schemas.chat import FeedbackBlock

_GRAMMAR_HEADING = re.compile(r"\[?\s*语法指正\s*\]?[:：]?", re.IGNORECASE)
_POLISH_HEADING = re.compile(r"\[?\s*地道表达\s*\]?[:：]?", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*(.+)$")

# 兜底：英文提示词，兼容模型未严格使用中文小标题的情况
_EN_GRAMMAR = re.compile(r"\[?\s*grammar(?:\s*(?:note|correction|fix))?\s*\]?[:：]?", re.I)
_EN_POLISH = re.compile(r"\[?\s*(?:better|polished)\s*expression\s*\]?[:：]?", re.I)


def _split_sections(text: str) -> tuple[str, str, str]:
    """把回复切成 (正文, 语法段, 地道表达段)。"""
    grammar_match = _GRAMMAR_HEADING.search(text) or _EN_GRAMMAR.search(text)
    polish_match = _POLISH_HEADING.search(text) or _EN_POLISH.search(text)

    anchors = sorted(
        [m for m in (grammar_match, polish_match) if m], key=lambda m: m.start()
    )
    if not anchors:
        return text.strip(), "", ""

    first = anchors[0]
    preamble = text[: first.start()].strip()

    sections: dict[str, str] = {"grammar": "", "polish": ""}
    order = []
    if grammar_match and grammar_match in anchors:
        order.append(("grammar", grammar_match))
    if polish_match and polish_match in anchors:
        order.append(("polish", polish_match))

    for index, (key, match) in enumerate(order):
        end = order[index + 1][1].start() if index + 1 < len(order) else len(text)
        body = text[match.end():end].strip()
        sections[key] = body

    return preamble, sections["grammar"], sections["polish"]


def _collect_items(body: str) -> list[str]:
    """从区块正文里收集条目；无列表符号时按非空行拆分。"""
    if not body:
        return []
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        list_match = _LIST_ITEM.match(stripped)
        items.append(list_match.group(1).strip() if list_match else stripped)
    return [item for item in items if item]


def parse_feedback(text: str) -> tuple[str, FeedbackBlock | None]:
    """解析模型回复，返回 (净化正文, 纠错区块或 None)。

    无纠错区块时返回 None，前端据此隐藏纠错卡片。
    """
    if not text:
        return "", None

    preamble, grammar_body, polish_body = _split_sections(text)
    grammar_items = _collect_items(grammar_body)
    polish_items = _collect_items(polish_body)

    if not grammar_items and not polish_items:
        return text.strip(), None

    block = FeedbackBlock(
        grammar=" ".join(grammar_items) if grammar_items else "",
        polish=polish_items,
    )
    return preamble, block


def feedback_to_json(block: FeedbackBlock | None) -> str | None:
    """将纠错区块序列化为可入库的 JSON 字符串。"""
    if block is None:
        return None
    return json.dumps(
        {"grammar": block.grammar, "polish": block.polish},
        ensure_ascii=False,
    )


def feedback_from_json(raw: str | None) -> FeedbackBlock | None:
    """从数据库 JSON 字段还原纠错区块。"""
    if not raw:
        return None
    try:
        data: Any = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    grammar = data.get("grammar") or ""
    polish = data.get("polish") or []
    if not isinstance(polish, list):
        polish = [str(polish)]
    if not grammar and not polish:
        return None
    return FeedbackBlock(grammar=str(grammar), polish=[str(item) for item in polish])
