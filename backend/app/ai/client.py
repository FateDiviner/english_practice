"""大模型对接层：OpenAI 兼容协议 SSE 流式调用 + 未配置时的本地 Mock 降级。

所有 AI 请求统一经由后端代理，API Key 只存在于服务端环境变量，绝不下发前端。
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.prompts import PRESETS
from app.config import get_settings

# Mock 降级时的打字机延迟（毫秒），测试可置 0 以加速
MOCK_DELAY_MS = 12

# 聊天端点相对路径
CHAT_COMPLETIONS_PATH = "/chat/completions"


class AIError(Exception):
    """模型调用失败，由 API 层转换为可重试的 HTTP 响应。"""

    def __init__(self, message: str, status_code: int = 502, retryable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


# 常见中式英语错误 -> 修正规则，仅供 Mock 降级时演示纠错能力
_MOCK_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bI am agree\b", re.IGNORECASE),
        "[语法指正]\n- \"agree\" 是动词，前面不加 be 动词，应说 \"I agree\"。\n\n[地道表达]\n- I agree with you on that point.\n- That makes sense to me.",
    ),
    (
        re.compile(r"\bhe (?:go|come|do|have)\b", re.IGNORECASE),
        "[语法指正]\n- 第三人称单数的一般现在时，动词要加 -s，应说 \"he goes\"。\n\n[地道表达]\n- He goes to the gym every morning.\n- He usually goes by subway.",
    ),
    (
        re.compile(r"\bI didn't went\b", re.IGNORECASE),
        "[语法指正]\n- \"did\" 已经承担过去式，后面的动词要用原形：\"I didn't go\"。\n\n[地道表达]\n- I didn't go to the meeting yesterday.\n- I never went back after that.",
    ),
    (
        re.compile(r"\bmore better\b", re.IGNORECASE),
        "[语法指正]\n- \"better\" 本身已是比较级，不能再用 \"more\" 修饰。\n\n[地道表达]\n- This one works better for me.\n- It would be better to start earlier.",
    ),
]


def _mock_correction(text: str) -> str:
    for pattern, block in _MOCK_RULES:
        if pattern.search(text):
            return block
    return ""


def _mock_reply(user_input: str, preset: str | None) -> str:
    """生成 Mock 流式回复，保证未配置 API Key 时全流程仍可跑通。"""
    text = user_input.strip()
    correction = _mock_correction(text)

    if preset == "explain_word":
        body = (
            "Good question. Give me the exact word you want to break down and I will "
            "cover its part of speech, a core meaning, one collocation and one example."
        )
    elif preset == "grammar_check":
        body = (
            "I have read your sentence carefully. Here is what stands out, "
            "followed by a more natural phrasing."
        )
        if not correction:
            correction = (
                "[语法指正]\n- Your sentence is grammatically sound. "
                "Watch the article usage and you are set.\n\n[地道表达]\n"
                "- That sounds like a solid plan.\n- I think that is the way to go."
            )
    elif preset == "free_chat":
        body = (
            "Nice to practise with you. What has been the best part of your week so far?"
        )
    else:
        body = (
            "Understood. Tell me a bit more and I will help you shape it into natural English."
        )

    return f"{body}\n\n{correction}".strip()


async def _iter_mock(user_input: str, preset: str | None) -> AsyncIterator[str]:
    """Mock 逐字推送，模拟真实打字机效果。"""
    content = _mock_reply(user_input, preset)
    # 按词切分，保留尾随空格，观感接近真实流式
    chunks = re.findall(r"\S+\s*", content)
    delay = MOCK_DELAY_MS / 1000
    for chunk in chunks:
        if delay > 0:
            await asyncio.sleep(delay)
        yield chunk


async def stream_chat(
    messages: list[dict[str, str]],
    user_input: str = "",
    preset: str | None = None,
) -> AsyncIterator[str]:
    """流式获取模型回复，逐块产出文本。

    - 配置齐全：走 OpenAI 兼容 SSE 接口。
    - 未配置：降级为本地 Mock 流，保证全流程可跑通。
    """
    settings = get_settings()
    if not settings.ai_enabled:
        async for chunk in _iter_mock(user_input, preset):
            yield chunk
        return

    url = settings.ai_base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload: dict[str, Any] = {
        "model": settings.ai_model,
        "messages": messages,
        "stream": True,
    }

    timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url, headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", "ignore")[:300]
                    raise AIError(
                        f"模型服务返回 {response.status_code}: {detail}",
                        status_code=502,
                        retryable=response.status_code >= 500,
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
    except httpx.TimeoutException as exc:
        raise AIError("模型响应超时，请稍后重试", status_code=504, retryable=True) from exc
    except httpx.HTTPError as exc:
        raise AIError(
            f"模型服务连接失败：{exc.__class__.__name__}",
            status_code=502,
            retryable=True,
        ) from exc


def preset_text(preset: str | None) -> str:
    """返回快捷指令的说明文案，便于前端回显。"""
    return PRESETS.get(preset or "", "")
