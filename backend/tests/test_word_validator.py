"""数据质量校验器自身的正反例测试。

每条规则至少一个反例，确保规则真的在拦东西——否则 test_data.py 跑绿
也只说明「没人在管」，而不是「数据是对的」。
"""

from __future__ import annotations

import pytest

from app.services.word_validator import (
    ValidationResult,
    validate_batch,
    validate_book,
    validate_book_deep,
    validate_word,
)


def good_word(**overrides) -> dict:
    """一条完全合规的词条，用例只改自己关心的那个字段。"""
    item = {
        "word": "abandon",
        "phonetic": "/əˈbændən/",
        "translation": "v. 放弃，遗弃",
        "example_en": "They had to abandon the plan.",
        "example_cn": "他们不得不放弃这个计划。",
    }
    item.update(overrides)
    return item


def rules_of(result: ValidationResult) -> set[str]:
    return result.rules()


def self_book(words: list) -> dict:
    """一条结构合法的词书骨架，用例只改自己关心的部分。"""
    return {
        "code": "deep-test",
        "title": "测试词书",
        "description": "",
        "difficulty": "",
        "words": words,
    }


class TestValidWordPasses:
    def test_baseline_is_clean(self):
        assert validate_word(good_word()).ok


class TestMissingField:
    @pytest.mark.parametrize("key", ["word", "phonetic", "translation", "example_en", "example_cn"])
    def test_absent_key(self, key: str):
        item = good_word()
        del item[key]
        result = validate_word(item)
        assert not result.ok
        assert "missing_field" in rules_of(result)

    @pytest.mark.parametrize("key", ["word", "phonetic", "translation", "example_en", "example_cn"])
    def test_blank_key(self, key: str):
        result = validate_word(good_word(**{key: "   "}))
        assert "missing_field" in rules_of(result)

    def test_short_circuits_after_missing(self):
        """字段缺失时后续规则无从判断，应当直接返回，不产生噪声问题。"""
        item = good_word()
        del item["phonetic"]
        result = validate_word(item)
        assert rules_of(result) == {"missing_field"}


class TestWordRules:
    def test_non_ascii_rejected(self):
        assert "word_ascii" in rules_of(validate_word(good_word(word="abandoné")))

    def test_surrounding_spaces_rejected(self):
        assert "word_trimmed" in rules_of(validate_word(good_word(word=" abandon ")))

    def test_uppercase_head_rejected(self):
        assert "word_lowercase_head" in rules_of(validate_word(good_word(word="Abandon")))


class TestPhoneticRules:
    def test_unbracketed_rejected(self):
        assert "phonetic_brackets" in rules_of(validate_word(good_word(phonetic="əˈbændən")))

    def test_only_one_bracket_rejected(self):
        assert "phonetic_brackets" in rules_of(validate_word(good_word(phonetic="/əˈbændən")))

    def test_too_short_rejected(self):
        assert "phonetic_length" in rules_of(validate_word(good_word(phonetic="/ə/")))

    def test_abnormal_charset_rejected(self):
        result = validate_word(good_word(phonetic="/!!!###/"))
        assert "phonetic_charset" in rules_of(result)


class TestTranslationRules:
    def test_missing_pos_prefix_rejected(self):
        result = validate_word(good_word(translation="放弃，遗弃"))
        assert "translation_pos_prefix" in rules_of(result)

    def test_missing_chinese_rejected(self):
        result = validate_word(good_word(translation="v. give up"))
        assert "translation_has_chinese" in rules_of(result)

    @pytest.mark.parametrize(
        "pos", ["v.", "n.", "adj.", "adv.", "prep.", "conj.", "pron.", "vt.", "vi.", "num.", "art.", "aux."]
    )
    def test_all_pos_prefixes_accepted(self, pos: str):
        item = good_word(translation=f"{pos} 测试释义")
        assert validate_word(item).ok, f"{pos} 应当被接受"


class TestExampleRules:
    def test_english_inside_chinese_example_rejected(self):
        result = validate_word(good_word(example_cn="他们放弃了 plan。"))
        assert "example_cn_no_english" in rules_of(result)

    def test_chinese_example_without_terminal_punct_rejected(self):
        result = validate_word(good_word(example_cn="他们不得不放弃这个计划"))
        assert "example_cn_terminal" in rules_of(result)

    def test_english_example_without_terminal_punct_rejected(self):
        result = validate_word(good_word(example_en="They had to abandon the plan"))
        assert "example_en_terminal" in rules_of(result)

    def test_example_without_target_word_rejected(self):
        result = validate_word(good_word(example_en="They had to give it up."))
        assert "example_contains_word" in rules_of(result)

    def test_example_with_stem_variant_accepted(self):
        """词干截断：abandon 的变体 abandoning 也应算命中。"""
        item = good_word(example_en="They are abandoning the plan.")
        assert validate_word(item).ok


class TestCollectsAllIssues:
    def test_does_not_short_circuit_on_field_errors(self):
        """一条词条可以同时违反多条规则，报告要一次给全，别让人改一次跑一次。"""
        result = validate_word(
            good_word(
                word="Abandon",
                phonetic="bad",
                translation="give up",
                example_en="They gave it up",
                example_cn="他们放弃了",
            )
        )
        assert {
            "word_lowercase_head",
            "phonetic_brackets",
            "translation_pos_prefix",
            "translation_has_chinese",
            "example_en_terminal",
            "example_cn_terminal",
            "example_contains_word",
        } <= rules_of(result)


class TestBookRules:
    def _book(self, **overrides) -> dict:
        payload = {
            "code": "unit-test",
            "title": "测试词书",
            "description": "仅用于测试",
            "difficulty": "easy",
            "words": [good_word()],
        }
        payload.update(overrides)
        return payload

    def test_valid_book_passes(self):
        assert validate_book(self._book()).ok

    @pytest.mark.parametrize("key", ["code", "title", "words"])
    def test_missing_required_key(self, key: str):
        payload = self._book()
        payload[key] = [] if key == "words" else ""
        assert "book_missing_field" in rules_of(validate_book(payload))

    def test_non_dict_payload_reported_not_crashed(self):
        """导入文件是外部输入，payload 本身可能就不是对象。

        这里曾直接 .get 抛 AttributeError，让导入接口从 422 变成 500。
        """
        result = validate_book("not-an-object")
        assert "book_not_object" in rules_of(result)

    def test_non_dict_word_entry_does_not_crash(self):
        """words 里混进字符串时，校验器必须给结论而不是抛异常。

        职责分工：validate_book 只管去重，跳过非对象条目；
        validate_book_deep 负责用 words[i] 把它定位出来。
        """
        payload = self._book(words=[good_word(), "oops"])
        assert validate_book(payload).ok
        assert "words[1]" in {i.field for i in validate_book_deep(payload).issues}

    def test_empty_words_rejected(self):
        assert "book_empty" in rules_of(validate_book(self._book(words=[])))

    def test_duplicate_word_rejected(self):
        payload = self._book(words=[good_word(), good_word(word="abandon")])
        assert "book_duplicate_word" in rules_of(validate_book(payload))

    def test_duplicate_word_is_case_insensitive(self):
        payload = self._book(words=[good_word(), good_word(word="ABANDON")])
        assert "book_duplicate_word" in rules_of(validate_book(payload))


class TestValidateBookDeep:
    def test_issue_field_is_locatable(self):
        """field 要形如 words[3].phonetic，让使用者一眼知道错在第几条。"""
        words = [good_word() for _ in range(4)]
        words[3] = good_word(phonetic="nope")
        result = validate_book_deep(self_book(words=words))
        assert result.ok is False
        assert any(issue.field == "words[3].phonetic" for issue in result.issues)

    def test_issue_message_carries_word_label(self):
        words = [good_word(), good_word(word="ephemeral", phonetic="nope")]
        result = validate_book_deep(self_book(words=words))
        assert any("[ephemeral]" in issue.message for issue in result.issues)

    def test_non_object_entry_reported(self):
        words = [good_word(), "not-an-object"]
        result = validate_book_deep(self_book(words=words))
        assert any(issue.field == "words[1]" for issue in result.issues)


class TestValidateBatch:
    def _book(self, code: str) -> dict:
        return {
            "code": code,
            "title": "测试词书",
            "description": "",
            "difficulty": "",
            "words": [good_word()],
        }

    def test_single_book_list_passes(self):
        assert validate_batch([self._book("only-one")]).ok

    def test_duplicate_code_across_books_rejected(self):
        result = validate_batch([self._book("same-code"), self._book("same-code")])
        assert "book_duplicate_code" in rules_of(result)

    def test_issue_message_carries_book_code(self):
        words = [good_word(phonetic="nope")]
        bad = {"code": "broken-book", "title": "t", "description": "", "difficulty": "", "words": words}
        result = validate_batch([bad])
        assert any("[broken-book]" in issue.message for issue in result.issues)
