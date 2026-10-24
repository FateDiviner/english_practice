from enum import StrEnum


class Intent(StrEnum):
    """主 Router 识别出的用户意图枚举。"""

    EXPLAIN_WORD = "EXPLAIN_WORD"
    GRAMMAR = "GRAMMAR"
    ORAL_PRACTICE = "ORAL_PRACTICE"
    TRANSLATION = "TRANSLATION"
    GENERAL = "GENERAL"
