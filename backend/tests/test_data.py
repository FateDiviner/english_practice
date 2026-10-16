"""内置词书数据质量红线测试。

AGENTS.md 第 1 条：单词与音标数据准确性第一。

规则本身在 app/services/word_validator.py，测试与管理端在线录入共用同一份，
避免「测试过了但页面能存进脏数据」。这里按规则名分组断言，保持逐条可读。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.word_validator import (
    REQUIRED_KEYS,
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


def issues_of(item: dict, rule: str) -> list[str]:
    """取出命中某条规则的问题文案。"""
    return [issue.message for issue in validate_word(item).issues if issue.rule == rule]


WORDS = list(all_words())
WORD_IDS = [f"{code}/{item.get('word')}" for code, item in WORDS]


class TestBookStructure:
    @pytest.mark.parametrize("book", BOOKS, ids=lambda b: b["code"])
    def test_book_is_structurally_valid(self, book: dict):
        result = validate_book(book)
        assert result.ok, f"{book.get('code')} 结构问题: {[i.message for i in result.issues]}"

    def test_no_duplicate_codes_across_books(self):
        codes = [book["code"] for book in BOOKS]
        assert len(codes) == len(set(codes)), f"词书 code 重复: {codes}"

    def test_required_keys_documented(self):
        """字段契约变更时必须同步更新校验器，这里做一次显式对齐。"""
        assert set(REQUIRED_KEYS) == {
            "word", "phonetic", "translation", "example_en", "example_cn",
        }


class TestWordFields:
    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_all_fields_present_and_non_empty(self, code: str, item: dict):
        missing = set(REQUIRED_KEYS) - set(item)
        assert not missing, f"{code} / {item.get('word')} 缺少字段 {missing}"
        for key in REQUIRED_KEYS:
            assert str(item[key]).strip(), f"{code} / {item['word']} 字段 {key} 为空"

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_word_is_plain_ascii(self, code: str, item: dict):
        assert not issues_of(item, "word_ascii"), f"{code} / {item['word']} 非纯 ASCII"
        assert not issues_of(item, "word_trimmed"), f"{code} / {item['word']} 首尾含空格"

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_word_is_lowercase_head(self, code: str, item: dict):
        assert not issues_of(item, "word_lowercase_head")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_phonetic_is_bracketed_and_valid(self, code: str, item: dict):
        assert not issues_of(item, "phonetic_brackets")
        assert not issues_of(item, "phonetic_length")
        assert not issues_of(item, "phonetic_charset")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_translation_starts_with_pos(self, code: str, item: dict):
        assert not issues_of(item, "translation_pos_prefix")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_translation_contains_chinese(self, code: str, item: dict):
        assert not issues_of(item, "translation_has_chinese")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_chinese_example_has_no_english(self, code: str, item: dict):
        assert not issues_of(item, "example_cn_no_english")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_examples_are_terminal_punctuated(self, code: str, item: dict):
        assert not issues_of(item, "example_en_terminal")
        assert not issues_of(item, "example_cn_terminal")

    @pytest.mark.parametrize(("code", "item"), WORDS, ids=WORD_IDS)
    def test_example_shows_the_target_word(self, code: str, item: dict):
        assert not issues_of(item, "example_contains_word")


class TestValidatorSelfCheck:
    """校验器本身必须真的能拦住脏数据，否则上面全绿只是摆设。"""

    def _good(self) -> dict:
        return {
            "word": "abandon",
            "phonetic": "/əˈbændən/",
            "translation": "v. 放弃，遗弃",
            "example_en": "He abandoned his car in the snow.",
            "example_cn": "他把车丢弃在雪地里。",
        }

    def test_accepts_a_clean_word(self):
        assert validate_word(self._good()).ok

    @pytest.mark.parametrize(
        ("mutate", "rule"),
        [
            (lambda item: item.pop("phonetic"), "missing_field"),
            (lambda item: item.update(phonetic=""), "missing_field"),
            (lambda item: item.update(phonetic="abandon"), "phonetic_brackets"),
            (lambda item: item.update(phonetic="//"), "phonetic_length"),
            (lambda item: item.update(translation="放弃"), "translation_pos_prefix"),
            (lambda item: item.update(translation="v. abandon"), "translation_has_chinese"),
            (lambda item: item.update(example_cn="他 abandon 了车。"), "example_cn_no_english"),
            (lambda item: item.update(example_en="He abandoned his car"), "example_en_terminal"),
            (lambda item: item.update(example_cn="他把车丢弃了"), "example_cn_terminal"),
            (lambda item: item.update(example_en="He left the car."), "example_contains_word"),
            (lambda item: item.update(word="Abandon"), "word_lowercase_head"),
            (lambda item: item.update(word=" 放弃 "), "word_ascii"),
        ],
    )
    def test_rejects_known_bad_input(self, mutate, rule: str):
        item = self._good()
        mutate(item)

        assert rule in validate_word(item).rules()

    def test_collects_every_issue_instead_of_stopping_at_first(self):
        item = self._good()
        item["translation"] = "v. abandon"
        item["example_en"] = "He left the car"

        rules = validate_word(item).rules()

        assert {"translation_has_chinese", "example_contains_word"} <= rules

    def test_book_with_duplicate_words_rejected(self):
        payload = {"code": "x", "title": "t", "words": [self._good(), self._good()]}

        assert "book_duplicate_word" in validate_book(payload).rules()

    def test_empty_book_rejected(self):
        assert "book_empty" in validate_book({"code": "x", "title": "t", "words": []}).rules()


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
