import pytest
from app.services.grading import (
    CONSECUTIVE_CORRECT_TO_MASTER,
    is_correct_answer,
    normalize_input,
)
from app.services.spelling_variants import SPELLING_VARIANT_GROUPS

VARIANT_PAIRS = [tuple(group) for group in SPELLING_VARIANT_GROUPS if len(group) == 2]


def test_normalize_input_trims_and_lowercases() -> None:
    assert normalize_input("  HeLLo  ") == "hello"


def test_case_and_outer_whitespace_are_ignored() -> None:
    assert is_correct_answer("  HeLLo  ", "hello")
    assert is_correct_answer("HELLO", "hello")


def test_american_and_british_spellings_work_both_ways() -> None:
    assert is_correct_answer("color", "colour")
    assert is_correct_answer("colour", "color")


def test_strict_mode_rejects_hyphen_and_space_differences() -> None:
    assert not is_correct_answer("icecream", "ice cream", strict_mode=True)
    assert not is_correct_answer("ice-cream", "ice cream", strict_mode=True)


@pytest.mark.parametrize("answer", ["ice cream", "icecream", "ice-cream"])
def test_loose_mode_allows_hyphen_and_space_differences(answer: str) -> None:
    assert is_correct_answer(answer, "ice cream", strict_mode=False)


@pytest.mark.parametrize("answer", ["", "   "])
def test_empty_answers_are_incorrect(answer: str) -> None:
    assert not is_correct_answer(answer, "hello")


def test_incorrect_and_prefix_answers_are_rejected() -> None:
    assert not is_correct_answer("helo", "hello")
    assert not is_correct_answer("hel", "hello")


def test_chinese_input_is_incorrect() -> None:
    assert not is_correct_answer("你好", "hello")


def test_mapping_table_has_at_least_twenty_groups() -> None:
    assert len(SPELLING_VARIANT_GROUPS) >= 20


@pytest.mark.parametrize(("left", "right"), VARIANT_PAIRS)
def test_mapping_groups_work_in_both_directions(left: str, right: str) -> None:
    assert is_correct_answer(left, right)
    assert is_correct_answer(right, left)


def test_mastery_threshold_constant() -> None:
    assert CONSECUTIVE_CORRECT_TO_MASTER == 2
