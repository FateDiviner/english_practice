"""全项目无 Emoji 红线自检（AGENTS.md 第 2 节交付前清单）。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

# 覆盖 Emoji、组合变体选择符、零宽连接符与常见符号区
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # Emoji 主区块
    "\U00002600-\U000027BF"  # 杂项符号与装饰符号
    "\U0001F1E6-\U0001F1FF"  # 区域指示符（旗帜）
    "\U0000FE00-\U0000FE0F"  # 变体选择符
    "\U0000200D"  # 零宽连接符
    "\U00002B00-\U00002BFF"  # 杂项符号与箭头
    "\U0001F300-\U0001F5FF"  # 符号与象形文字
    "]+"
)

SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "coverage",
    "build",
}
SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".scss",
    ".html",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".txt",
    ".example",
}


def iter_source_files() -> list[Path]:
    """收集需要扫描的源码与文档文件。"""
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES and path.name not in {".env.example"}:
            continue
        files.append(path)
    return files


FILES = iter_source_files()


def _line_of(content: str, index: int) -> int:
    return content.count("\n", 0, index) + 1


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_file_contains_no_emoji(path: Path) -> None:
    content = path.read_text(encoding="utf-8", errors="replace")
    match = EMOJI_PATTERN.search(content)
    assert match is None, (
        f"{path.relative_to(ROOT)} 第 {_line_of(content, match.start())} 行含 Emoji: "
        f"{match.group(0)!r}"
    )


def test_scanner_actually_found_files() -> None:
    """防止扫描范围因路径变化而静默失效。"""
    assert len(FILES) > 30, f"仅扫描到 {len(FILES)} 个文件，扫描范围可能失效"
    assert any(p.suffix == ".tsx" for p in FILES)
    assert any(p.suffix == ".py" for p in FILES)


def test_emoji_detector_detects_known_emoji() -> None:
    """自检：确保本测试的正则确实能识别 Emoji。"""
    # 同样用 chr() 构造样本，避免本自检文件自身含字面 Emoji 而被判违规
    samples = (
        chr(0x1F389),  # 礼花
        chr(0x1F4A1),  # 灯泡
        chr(0x1F600),  # 笑脸
        chr(0x1F680),  # 火箭
        chr(0x1F1E8) + chr(0x1F1F3),  # 旗帜
        chr(0x2764) + chr(0xFE0F),  # 爱心（带变体选择符）
    )
    for sample in samples:
        assert EMOJI_PATTERN.search(sample), f"正则未能识别 {sample!r}"
    assert not EMOJI_PATTERN.search("[正确] [拼写错误] plain text 123")
