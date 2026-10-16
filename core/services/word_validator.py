"""词条与词书的数据质量校验器。

规则与 AGENTS.md 第 1 条「单词与音标数据准确性第一」一致，原本只存在于
tests/test_data.py 的断言里。抽成共享校验器后，测试与管理端在线录入、
批量导入用的是同一份规则，不会出现「测试过了但页面能存进脏数据」。

返回结构化错误而不是抛断言：管理端需要逐条错误报告，测试需要按规则名分组。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# IPA 中允许出现的字符（含音标专用符号与连接符）
PHONETIC_ALLOWED = re.compile(r"^[ˈˌː.\/əæɔʊɪiɜʌɑa-zæɔʃθðʒŋ()\-ˈˌː\.]+$")
POS_PREFIX = re.compile(r"^(?:conj|prep|pron|adj|adv|num|art|aux|intj|int|vt|vi|n|v)\b")
CHINESE = re.compile(r"[一-鿿]")
ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")

REQUIRED_KEYS = ("word", "phonetic", "translation", "example_en", "example_cn")
BOOK_REQUIRED_KEYS = ("code", "title", "words")


@dataclass
class ValidationIssue:
    """一条校验问题。rule 供测试与前端分组，message 给人看。"""

    rule: str
    field: str
    message: str


@dataclass
class ValidationResult:
    """校验结论。"""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def rules(self) -> set[str]:
        return {issue.rule for issue in self.issues}

    def add(self, rule: str, field_name: str, message: str) -> None:
        self.issues.append(ValidationIssue(rule=rule, field=field_name, message=message))


def validate_word(item: dict) -> ValidationResult:
    """校验单个词条，返回全部问题而非短路。"""
    result = ValidationResult()

    for key in REQUIRED_KEYS:
        if key not in item:
            result.add("missing_field", key, f"缺少字段 {key}")
        elif not str(item[key] or "").strip():
            result.add("missing_field", key, f"字段 {key} 为空")

    # 缺字段时后续规则无从判断
    if not result.ok:
        return result

    word = str(item["word"])
    if not word.isascii():
        result.add("word_ascii", "word", f"{word} 含非 ASCII 字符")
    if word != word.strip():
        result.add("word_trimmed", "word", f"{word} 首尾含空格")
    if word[:1].isupper():
        result.add(
            "word_lowercase_head",
            "word",
            f"{word} 应为小写词头（专有名词除外，需人工确认）",
        )

    phonetic = str(item["phonetic"])
    if not (phonetic.startswith("/") and phonetic.endswith("/") and len(phonetic) >= 2):
        result.add("phonetic_brackets", "phonetic", f"音标未用 / / 包裹: {phonetic}")
    elif len(phonetic) <= 3:
        result.add("phonetic_length", "phonetic", f"音标过短: {phonetic}")
    else:
        inner = phonetic[1:-1]
        if not (PHONETIC_ALLOWED.match(inner) or re.match(r"^[\wˈˌː./\-()]+$", inner)):
            result.add("phonetic_charset", "phonetic", f"音标含异常字符: {phonetic}")

    translation = str(item["translation"])
    if not POS_PREFIX.match(translation):
        result.add(
            "translation_pos_prefix",
            "translation",
            f"释义缺少词性前缀: {translation}",
        )
    if not CHINESE.search(translation):
        result.add("translation_has_chinese", "translation", "释义缺少中文")

    example_cn = str(item["example_cn"])
    offenders = ENGLISH_WORD.findall(example_cn)
    if offenders:
        result.add(
            "example_cn_no_english",
            "example_cn",
            f"中文例句夹杂英文 {offenders}",
        )

    if not example_cn.rstrip().endswith(("。", "！", "？", '"')):
        result.add("example_cn_terminal", "example_cn", "中文例句缺少句末标点")
    if not str(item["example_en"]).rstrip().endswith((".", "!", "?", '"')):
        result.add("example_en_terminal", "example_en", "英文例句缺少句末标点")

    stem = word[: max(4, len(word) - 2)]
    if stem not in str(item["example_en"]).lower():
        result.add(
            "example_contains_word",
            "example_en",
            f"例句未体现目标词: {item['example_en']}",
        )

    return result


def validate_book(payload: dict) -> ValidationResult:
    """校验一本词书的结构与内部唯一性。"""
    result = ValidationResult()

    for key in BOOK_REQUIRED_KEYS:
        if not payload.get(key):
            result.add("book_missing_field", key, f"词书缺少 {key}")

    words = payload.get("words") or []
    if not words:
        result.add("book_empty", "words", "词书没有任何单词")
        return result

    seen: set[str] = set()
    for item in words:
        word = str(item.get("word", "")).strip().lower()
        if not word:
            continue
        if word in seen:
            result.add("book_duplicate_word", "word", f"存在重复词: {word}")
        seen.add(word)

    return result


def validate_book_deep(payload: dict) -> ValidationResult:
    """结构校验 + 逐词条校验，供批量导入产出可定位的错误报告。

    issue.field 形如 words[3].phonetic，message 前缀形如 [abandon]，
    让使用者一眼知道是哪本书的第几条、哪个词、违反了哪条红线。
    """
    result = validate_book(payload)
    if not payload.get("words"):
        return result

    for index, item in enumerate(payload["words"]):
        if not isinstance(item, dict):
            result.add(
                "missing_field",
                f"words[{index}]",
                f"第 {index + 1} 条不是对象",
            )
            continue
        label = str(item.get("word") or f"#{index + 1}")
        for issue in validate_word(item).issues:
            result.issues.append(
                ValidationIssue(
                    rule=issue.rule,
                    field=f"words[{index}].{issue.field}",
                    message=f"[{label}] {issue.message}",
                )
            )
    return result


def validate_batch(books: list[dict]) -> ValidationResult:
    """校验一批词书，附带跨词书的 code 唯一性。"""
    result = ValidationResult()
    codes: set[str] = set()
    for payload in books:
        merged = validate_book_deep(payload)
        result.issues.extend(merged.issues)
        for item in merged.issues:
            item.message = f"[{payload.get('code', '?')}] {item.message}"

        code = str(payload.get("code", "")).strip()
        if code:
            if code in codes:
                result.add(
                    "book_duplicate_code",
                    "code",
                    f"词书 code 重复: {code}",
                )
            codes.add(code)

    return result
