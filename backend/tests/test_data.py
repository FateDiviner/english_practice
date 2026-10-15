"""内置词书数据质量红线测试。

AGENTS.md 第 1 条：单词与音标数据准确性第一。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

REQUIRED_KEYS = {"word", "phonetic", "translation", "example_en", "example_cn"}
# IPA 中允许出现的字符（含音标专用符号与连接符）
PHONETIC_ALLOWED = re.compile(r"^[ˈˌː.\/əæɔʊɪiɜʌɑa-zæɔʃθðʒŋ()\-ˈˌː\.]+$")
POS_PREFIX = re.compile(
    r"^(?:conj|prep|pron|adj|adv|num|art|aux|intj|int|vt|vi|n|v)\b"
)


def load_books() -> list[dict]:
    files = sorted(DATA_DIR.glob("*.json"))
    assert files, f"在 {DATA_DIR} 未找到任何词书数据"
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


BOOKS = load_books()


def all_words() -> list[tuple[str, dict]]:
    for book in BOOKS:
        for item in book["words"]:
            yield book["code"], item


class TestBookStructure:
    @pytest.mark.parametrize("book", BOOKS, ids=lambda b: b["code"])
    def test_required_top_level_fields(self, book: dict):
        for key in ("code", "title", "description", "difficulty", "words"):
            assert key in book, f"{book.get('code')} 缺少字段 {key}"
        assert book["words"], f"{book['code']} 没有任何单词"

    @pytest.mark.parametrize("book", BOOKS, ids=lambda b: b["code"])
    def test_book_codes_unique(self, book: dict):
        codes = [b["code"] for b in BOOKS]
        assert codes.count(book["code"]) == 1

    @pytest.mark.parametrize("book", BOOKS, ids=lambda b: b["code"])
    def test_no_duplicate_words_within_book(self, book: dict):
        words = [item["word"].lower() for item in book["words"]]
        duplicates = {w for w in words if words.count(w) > 1}
        assert not duplicates, f"{book['code']} 存在重复词: {duplicates}"


class TestWordFields:
    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_all_fields_present_and_non_empty(self, code: str, item: dict):
        missing = REQUIRED_KEYS - set(item)
        assert not missing, f"{code} / {item.get('word')} 缺少字段 {missing}"
        for key in REQUIRED_KEYS:
            assert str(item[key]).strip(), f"{code} / {item['word']} 字段 {key} 为空"

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_word_is_plain_ascii_lowercase(self, code: str, item: dict):
        word = item["word"]
        assert word.isascii(), f"{word} 含非 ASCII 字符"
        assert word == word.strip()
        assert not word[0].isupper(), f"{word} 应为小写词头（专有名词除外，此处需人工确认）"

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_phonetic_is_bracketed_and_valid(self, code: str, item: dict):
        phonetic = item["phonetic"]
        assert phonetic.startswith("/") and phonetic.endswith("/"), f"{item['word']} 音标未用 / / 包裹: {phonetic}"
        assert len(phonetic) > 3, f"{item['word']} 音标过短: {phonetic}"
        inner = phonetic[1:-1]
        assert PHONETIC_ALLOWED.match(inner) or re.match(r"^[\wˈˌː.\/\-()]+$", inner), (
            f"{item['word']} 音标含异常字符: {phonetic}"
        )

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_translation_starts_with_pos(self, code: str, item: dict):
        assert POS_PREFIX.match(item["translation"]), (
            f"{code} / {item['word']} 释义缺少词性前缀: {item['translation']}"
        )

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_chinese_fields_contain_no_english_words(self, code: str, item: dict):
        for key in ("example_cn",):
            offenders = re.findall(r"[A-Za-z]{3,}", item[key])
            assert not offenders, f"{code} / {item['word']} 中文字段夹杂英文 {offenders}"

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_translation_contains_chinese(self, code: str, item: dict):
        assert re.search(r"[一-鿿]", item["translation"]), (
            f"{code} / {item['word']} 释义缺少中文: {item['translation']}"
        )

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_examples_are_terminal_punctuated(self, code: str, item: dict):
        assert item["example_en"].rstrip().endswith((".", "!", "?", '"')), (
            f"{code} / {item['word']} 英文例句缺少句末标点"
        )
        assert item["example_cn"].rstrip().endswith(("。", "！", "？", '"')), (
            f"{code} / {item['word']} 中文例句缺少句末标点"
        )

    @pytest.mark.parametrize(("code", "item"), list(all_words()), ids=lambda v: v if isinstance(v, str) else "")
    def test_example_shows_the_target_word(self, code: str, item: dict):
        stem = item["word"][: max(4, len(item["word"]) - 2)]
        assert stem in item["example_en"].lower(), (
            f"{code} / {item['word']} 例句未体现目标词: {item['example_en']}"
        )


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
