"""意图关键词兜底规则。

Router 解析大模型输出失败时，用本模块的规则做本地兜底，
Mock 客户端也复用同一套规则，保证无 API Key 时逻辑可跑通。
"""

import re

from app.services.agent.intent import Intent

_ORAL_KEYWORDS = ("口语", "对练", "陪练", "对话练习", "练口语", "说英语", "点餐", "面试")

_TRANSLATION_KEYWORDS = (
    "翻译",
    "translate",
    "英译汉",
    "汉译英",
    "中译英",
    "英译中",
)

_GRAMMAR_KEYWORDS = (
    "语法",
    "时态",
    "语态",
    "从句",
    "纠错",
    "批改",
    "病句",
    "主谓一致",
    "过去完成时",
    "grammar",
)

_WORD_KEYWORDS = ("什么意思", "单词", "词根", "词缀", "记忆", "用法", "搭配", "meaning of")

_WORD_MEANING_PATTERN = re.compile(
    r"\b(?:meaning|define|definition|explain\s+(?:the\s+)?word)\b"
    r"|\bwhat\s+(?:does|do|is)\b[^.?!]{0,40}\bmean\b",
    re.IGNORECASE,
)

_SINGLE_WORD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z'-]{0,30}$")

_ENGLISH_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]{1,30}")


def find_english_word(message: str) -> str | None:
    """从用户输入中提取第一个英文单词，提取不到返回 None。"""
    match = _ENGLISH_TOKEN_PATTERN.search(message)
    return match.group(0) if match else None


def keyword_classify(message: str) -> Intent:
    """基于关键词的本地意图分类，作为模型输出解析失败的兜底。"""
    text = message.strip().lower()
    if any(keyword in text for keyword in _TRANSLATION_KEYWORDS):
        return Intent.TRANSLATION
    if any(keyword in text for keyword in _ORAL_KEYWORDS):
        return Intent.ORAL_PRACTICE
    if any(keyword in text for keyword in _GRAMMAR_KEYWORDS):
        return Intent.GRAMMAR
    if any(keyword in text for keyword in _WORD_KEYWORDS) and find_english_word(message):
        return Intent.EXPLAIN_WORD
    if _WORD_MEANING_PATTERN.search(message) and find_english_word(message):
        return Intent.EXPLAIN_WORD
    if _SINGLE_WORD_PATTERN.match(text):
        return Intent.EXPLAIN_WORD
    return Intent.GENERAL
