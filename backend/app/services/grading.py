from app.services.spelling_variants import get_variant_group

CONSECUTIVE_CORRECT_TO_MASTER = 2


def normalize_input(text: str) -> str:
    """去除首尾空白并转换为小写。"""
    return text.strip().lower()


def _is_known_variant_pair(left: str, right: str) -> bool:
    """判断两个已 normalise 的单词是否属于同一个英美变体组。"""
    left_group = get_variant_group(left)
    return left_group is not None and left_group == get_variant_group(right)


def _remove_hyphens_and_spaces(text: str) -> str:
    """宽松模式下忽略连字符和普通空格差异。"""
    return text.replace("-", "").replace(" ", "")


def is_correct_answer(
    user_input: str,
    correct_spelling: str,
    strict_mode: bool = True,
) -> bool:
    """判断用户默写答案是否正确；不做前缀或模糊匹配。"""
    if not isinstance(user_input, str) or not isinstance(correct_spelling, str):
        return False

    normalized_input = normalize_input(user_input)
    normalized_correct = normalize_input(correct_spelling)
    if not normalized_input or not normalized_correct:
        return False

    if normalized_input == normalized_correct or _is_known_variant_pair(
        normalized_input,
        normalized_correct,
    ):
        return True

    if strict_mode:
        return False

    return _remove_hyphens_and_spaces(normalized_input) == _remove_hyphens_and_spaces(
        normalized_correct,
    )
