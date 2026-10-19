"""默写核心工具函数测试：输入规整、词性抽取、例句挖空、逐字符比对。"""

from __future__ import annotations

import pytest

from app.services import practice_service as ps


class TestNormalizeAnswer:
    def test_strips_and_lowercases(self):
        assert ps.normalize_answer("  Abandon ") == "abandon"

    def test_collapses_internal_whitespace(self):
        assert ps.normalize_answer("in  credible") == "in credible"

    def test_empty_stays_empty(self):
        assert ps.normalize_answer("   ") == ""


class TestExtractPos:
    @pytest.mark.parametrize(
        ("translation", "expected"),
        [
            ("v. 放弃，遗弃", "v."),
            ("n. 能力，才能", "n."),
            ("adj. 反常的，异常的", "adj."),
            ("adv. 快速地", "adv."),
            ("n./v. 呼吁；上诉", "n./v."),
            ("prep. 在…之间", "prep."),
        ],
    )
    def test_extracts_leading_pos(self, translation: str, expected: str):
        assert ps.extract_pos(translation) == expected

    def test_returns_empty_when_no_pos(self):
        assert ps.extract_pos("无词性前缀的释义") == ""

    def test_handles_empty(self):
        assert ps.extract_pos("") == ""


class TestMaskExample:
    def test_blanks_target_word(self):
        masked = ps.mask_example("They abandoned the plan.", "abandon")
        assert "abandon" not in masked.lower()
        assert masked.startswith("They ")

    def test_blanks_inflected_form(self):
        """屈折形式必须一并挖空，否则能直接反查出拼写。"""
        masked = ps.mask_example("The team completed the project.", "complete")
        assert "complet" not in masked.lower()
        assert masked.startswith("The team ")

    def test_case_insensitive(self):
        masked = ps.mask_example("She Abandoned everything.", "abandon")
        assert "Abandoned" not in masked
        assert "_" * len("Abandoned") in masked

    def test_does_not_match_mid_word(self):
        """词中片段无边界，不应误伤无关单词。"""
        masked = ps.mask_example("Information flows freely.", "form")
        assert masked == "Information flows freely."

    def test_preserves_other_words(self):
        masked = ps.mask_example("He can not swim at all.", "swim")
        assert masked == "He can not ____ at all."

    def test_empty_inputs_safe(self):
        assert ps.mask_example("", "word") == ""
        assert ps.mask_example("text", "") == "text"

    def test_masked_example_never_leaks_spelling(self):
        example = "The team completed the project on time."
        masked = ps.mask_example(example, "complete")
        assert "complete" not in masked.lower()


class TestBuildDiff:
    def test_identical_produces_all_same(self):
        cells = ps.build_diff("cat", "cat")
        assert [cell.status for cell in cells] == ["same", "same", "same"]

    def test_marks_missing_letters(self):
        cells = ps.build_diff("abandn", "abandon")
        statuses = [cell.status for cell in cells]
        assert "missing" in statuses
        assert "".join(cell.char for cell in cells if cell.status == "missing") == "o"

    def test_marks_extra_letters(self):
        cells = ps.build_diff("abandonx", "abandon")
        statuses = [cell.status for cell in cells]
        assert "extra" in statuses
        assert "".join(cell.char for cell in cells if cell.status == "extra") == "x"

    def test_marks_substituted_letters(self):
        cells = ps.build_diff("bandon", "abandon")
        assert any(cell.status == "missing" for cell in cells)

    def test_empty_submission_yields_full_missing(self):
        cells = ps.build_diff("", "cat")
        assert all(cell.status == "missing" for cell in cells)
        assert "".join(cell.char for cell in cells) == "cat"

    def test_total_len_covers_both_strings(self):
        submitted, answer = "abcde", "axc"
        cells = ps.build_diff(submitted, answer)
        kept = "".join(c.char for c in cells if c.status != "missing")
        assert kept == submitted or set(kept) <= set(submitted)
