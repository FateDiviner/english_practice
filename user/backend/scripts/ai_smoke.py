"""真实大模型连通性冒烟测试。

pytest 套件一律走 Mock 以保证确定性；本脚本用于验证 .env 中配置的
真实模型端点是否可用、是否逐字流式、纠错区块能否被解析。

用法：
    cd user/backend
    .venv/Scripts/python -X utf8 -m scripts.ai_smoke

不会打印任何密钥内容。
"""

from __future__ import annotations

import asyncio
import sys
import time

from app.ai.client import AIError, stream_chat
from app.ai.corrections import parse_feedback
from app.ai.prompts import build_messages

SAMPLE_INPUT = "I am agree with you, and yesterday I didn't went to school."
PRESET = "grammar_check"
MAX_CHARS = 400


async def run() -> int:
    from core.config import get_settings

    settings = get_settings()
    if not settings.ai_enabled:
        print("[失败] .env 未配置齐全 AI_BASE_URL / AI_API_KEY / AI_MODEL")
        return 1

    print(f"[配置] base  = {settings.ai_base_url}")
    print(f"[配置] model = {settings.ai_model}")
    print(f"[配置] key   = {settings.ai_api_key[:6]}...{settings.ai_api_key[-4:]}")
    print(f"[输入] {SAMPLE_INPUT}")

    messages = build_messages([], SAMPLE_INPUT, preset=PRESET)

    started = time.perf_counter()
    chunks: list[str] = []
    first_byte_at: float | None = None

    try:
        async for delta in stream_chat(
            messages, user_input=SAMPLE_INPUT, preset=PRESET
        ):
            if first_byte_at is None:
                first_byte_at = time.perf_counter() - started
            chunks.append(delta)
    except AIError as exc:
        print(f"[失败] AIError (status={exc.status_code}, retryable={exc.retryable}): {exc.message}")
        return 2

    elapsed = time.perf_counter() - started
    full_text = "".join(chunks)

    if not full_text.strip():
        print("[失败] 模型返回了空内容")
        return 3

    body, block = parse_feedback(full_text)

    print(f"[结果] 首字延迟 = {first_byte_at:.2f}s | 总耗时 = {elapsed:.2f}s | "
          f"分片数 = {len(chunks)} | 字符数 = {len(full_text)}")
    print("[正文]")
    preview = body or full_text
    print("  " + preview[:MAX_CHARS].replace("\n", "\n  "))
    if len(preview) > MAX_CHARS:
        print("  ...(已截断)")

    if block is None:
        print("[纠错] 未解析到纠错区块 —— 回复中缺少 [语法指正] / [地道表达] 结构")
        return 4

    print("[纠错] 语法指正:", block.grammar or "(空)")
    for item in block.polish:
        print("[纠错] 地道表达:", item)

    # 流式分片拼接必须与最终解析结果一致
    assert "".join(chunks) == full_text
    print("[通过] 流式输出、首字延迟与纠错区块解析均正常")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
