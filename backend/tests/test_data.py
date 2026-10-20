"""内置词书数据质量红线测试。

AGENTS.md 第 1 条：单词与音标数据准确性第一。

规则本身住在 app/services/word_validator.py，本文件只负责拿真实数据去喂它。
这样测试与管理端在线录入、批量导入用的是同一份规则，不会出现
「测试过了但页面能存进脏数据」。校验器每条规则自身的正反例见 test_word_validator.py。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.word_validator import (
    validate_batch,
    validate_book,
    validate_word,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_books() -> list[dict]:
    files = sorted(DATA_DIR.glob("*.json"))
    assert files, f"在 {DATA_DIR} 未找到任何词书数据"
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


BOOKS = load_books()


def all_words() -> list[tuple[str, dict]]:
    for book in BOOKS:
        for item in book["words"]:
            yield book["code"], item


WORDS = list(all_words())


def _explain(code: str, issues) -> str:
    """把结构化问题列表拼成人能一眼定位的文案。"""
    joined = "；".join(f"{issue.field}: {issue.message}" for issue in issues)
    return f"{code} 未通过校验 -> {joined}"


class TestBooksPassValidator:
    @pytest.mark.parametrize("book", BOOKS, ids=lambda b: b["code"])
    def test_book_structure(self, book: dict):
        result = validate_book(book)
        assert result.ok, _explain(book["code"], result.issues)

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=[c for c, _ in WORDS])
    def test_word_fields(self, code: str, item: dict):
        result = validate_word(item)
        assert result.ok, _explain(code, result.issues)

    def test_whole_corpus_passes_batch(self):
        """跨词书的 code 唯一性也由校验器把关，这里跑全量。"""
        result = validate_batch(BOOKS)
        assert result.ok, _explain("corpus", result.issues)


class TestBookCodesUnique:
    def test_codes_are_unique(self):
        codes = [book["code"] for book in BOOKS]
        assert len(codes) == len(set(codes)), f"词书 code 重复: {codes}"


class TestCoverage:
    def test_cet4_meets_prd_minimum(self):
        cet4 = next(b for b in BOOKS if b["code"] == "cet4")
        assert 100 <= len(cet4["words"]) <= 300, "PRD 要求 CET-4 词库 100~300 词"

    def test_has_at_least_three_books(self):
        assert len(BOOKS) >= 3, "PRD 要求提供 3~4 本预置词书"

    def test_no_emoji_anywhere(self):
        # 用 chr() 构造字符类：源码里不放任何字面 Emoji 或不可见字符，
        # 否则本文件自身就会被"无 Emoji 自检"判为违规。
        ranges = "".join(
            chr(low) + "-" + chr(high)
            for low, high in (
                (0x1F000, 0x1FAFF),  # Emoji 主区块
                (0x2600, 0x27BF),  # 杂项符号与装饰符号
                (0x1F1E6, 0x1F1FF),  # 区域指示符（旗帜）
            )
        )
        invisible = chr(0x200D) + chr(0xFE0F)  # 零宽连接符 + 变体选择符
        emoji = re.compile("[" + ranges + re.escape(invisible) + "]")
        for path in DATA_DIR.glob("*.json"):
            content = path.read_text(encoding="utf-8")
            assert not emoji.search(content), f"{path.name} 含有 Emoji"
