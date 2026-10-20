"""Agent 白名单工具：知识库检索与单词精确查询。"""

from __future__ import annotations

from app.config import get_settings
from app.constants import STATUS_ACTIVE
from app.db import SessionLocal
from app.models.word import Word
from app.rag import pipeline as rag_pipeline
from app.rag.types import RagResult
from sqlalchemy import func, select

MAX_QUERY_CHARS = 500
MAX_WORD_CHARS = 128


def tool_specs(include_rag: bool = True) -> list[dict]:
    """返回 LangChain bind_tools 可识别的 JSON Schema 工具列表。"""

    lookup = {
        "type": "function",
        "function": {
            "name": "lookup_word",
            "description": (
                "Look up one exact English word in the active word bank. "
                "Returns phonetics, meaning and example sentences."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "A single English word, without punctuation.",
                        "maxLength": MAX_WORD_CHARS,
                    }
                },
                "required": ["word"],
                "additionalProperties": False,
            },
        },
    }
    if not include_rag:
        return [lookup]

    knowledge = {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Retrieve grounded passages from the learner's knowledge base "
                "and word bank for the current question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A concise, self-contained retrieval query.",
                        "maxLength": MAX_QUERY_CHARS,
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
    return [knowledge, lookup]


def run_knowledge_search(query: str, history: list[dict[str, str]]) -> RagResult:
    """在独立数据库会话中执行现有 RAG 管线。"""

    normalized = query.strip()[:MAX_QUERY_CHARS]
    if not normalized:
        return RagResult(skipped="检索词为空")
    with SessionLocal() as db:
        return rag_pipeline.run(normalized, db, history=history)


def run_lookup_word(word: str) -> list[dict[str, str]]:
    """大小写不敏感地查询有效词条，最多返回 3 个同形条目。"""

    normalized = word.strip()[:MAX_WORD_CHARS].strip(".,;:!?\"'()[]{}")
    if not normalized:
        return []
    with SessionLocal() as db:
        rows = db.scalars(
            select(Word)
            .where(
                Word.status == STATUS_ACTIVE,
                func.lower(Word.word) == normalized.lower(),
            )
            .order_by(Word.wordbook_id, Word.sequence, Word.id)
            .limit(3)
        ).all()
    return [
        {
            "id": str(row.id),
            "word": row.word,
            "phonetic": row.phonetic,
            "translation": row.translation,
            "example_en": row.example_en,
            "example_cn": row.example_cn,
        }
        for row in rows
    ]


def format_word_results(results: list[dict[str, str]]) -> str:
    """把单词查询结果压成规划节点可读的短文本。"""

    if not results:
        return "No exact word entry was found."
    blocks = []
    for item in results:
        parts = [f"{item['word']} {item['phonetic']}".strip(), item["translation"]]
        if item["example_en"]:
            parts.append(f"Example: {item['example_en']}")
        if item["example_cn"]:
            parts.append(f"Example translation: {item['example_cn']}")
        blocks.append("\n".join(part for part in parts if part))
    return "\n\n".join(blocks)
