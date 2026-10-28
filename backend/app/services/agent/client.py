"""大模型客户端封装。

- LLMClient：统一协议，所有调用方只依赖 stream() 流式输出
- MockLLMClient：本地假数据客户端，无外部依赖，用于跑通 Router + Skill 链路
- OpenAICompatibleClient：OpenAI 兼容协议客户端（DeepSeek / Ollama / vLLM 均可接入）

切换方式：.env 中配置 AI_PROVIDER（任意非 mock 值，如 openai / mimo）、
AI_PROVIDER_URL、AI_PROVIDER_KEY、AI_MODEL，缺任一项时自动回退到 Mock 客户端。
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx
from langsmith import traceable

from app.core.config import get_settings
from app.core.tracing import annotate_trace
from app.services.agent.heuristics import find_english_word, keyword_classify
from app.services.agent.intent import Intent
from app.services.agent.prompts import ROUTER_SCORE_PROMPT_TAG

logger = logging.getLogger(__name__)

MOCK_CHUNK_DELAY_SECONDS = 0.01
REQUEST_TIMEOUT_SECONDS = 60


@dataclass
class ChatMessage:
    role: str
    content: str


class LLMClient(Protocol):
    """大模型客户端协议：输入对话消息，按增量片段异步吐出回复文本。"""

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]: ...


_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9'-]+|\s+|.", re.DOTALL)


def _split_stream_chunks(text: str) -> list[str]:
    """把整段文本切成英文按词、其他按字的片段，模拟打字机效果。"""
    return _CHUNK_PATTERN.findall(text)


class MockLLMClient:
    """本地假数据客户端：识别 Prompt 标签并返回对应的模板化假回复。"""

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        reply = self._reply(messages)
        for chunk in _split_stream_chunks(reply):
            yield chunk
            await asyncio.sleep(MOCK_CHUNK_DELAY_SECONDS)

    def _reply(self, messages: list[ChatMessage]) -> str:
        user_text = messages[-1].content
        system_text = messages[0].content if messages else ""
        if system_text.startswith(ROUTER_SCORE_PROMPT_TAG) or user_text.startswith(
            ROUTER_SCORE_PROMPT_TAG
        ):
            message = user_text.rsplit("用户问题：", 1)[-1].strip()
            selected = keyword_classify(message)
            scores = {intent.value: 5 for intent in Intent}
            scores[selected.value] = 95
            return json.dumps(
                {"scores": scores, "reason": "Mock 关键词路由"},
                ensure_ascii=False,
            )
        return _mock_skill_reply(system_text, user_text)


def _mock_skill_reply(system_text: str, user_text: str) -> str:
    if "[SKILL:EXPLAIN_WORD]" in system_text:
        return _explain_word_reply(user_text)
    if "[SKILL:ORAL_PRACTICE]" in system_text:
        return _oral_practice_reply()
    if "[SKILL:GRAMMAR]" in system_text:
        return _grammar_reply()
    if "[SKILL:TRANSLATION]" in system_text:
        return (
            "（Mock 翻译）译文：这是一条用于跑通翻译技能链路的模拟结果。\n"
            "用词说明：真实模型接入后将按原文语气给出准确译文。"
        )
    if "[SKILL:GENERAL]" in system_text:
        return "（Mock 通用助手）已收到你的问题，我可以继续提供英语学习建议。"
    return "（Mock 回复）我是智能伴学助手，已收到你的消息。"


def _explain_word_reply(user_text: str) -> str:
    word = find_english_word(user_text) or "example"
    return (
        f"{word} 解析（Mock 数据）：\n"
        f"1. 词性释义：{word} 的核心含义与常见词性。\n"
        f"2. 词根词缀：拆解 {word} 的构词逻辑。\n"
        f"3. 例句：This is a sentence with {word}. 这是一个包含 {word} 的例句。\n"
        f"4. 记忆法：联想 {word} 的发音谐音与画面感，加深印象。"
    )


def _oral_practice_reply() -> str:
    return (
        "(Mock 对话) Hi there! Welcome to our restaurant. "
        "Would you like to start with something to drink? "
        "（点评：表达自然，注意 would like 后接动词不定式。）"
    )


def _grammar_reply() -> str:
    return (
        "（Mock 数据）结论：该语法点遵循主谓一致的基本原则。"
        "要点：先确定主语人称与单复数，再选择对应的谓语形式。"
        "正例：She goes to school every day. 她每天去上学。"
        "反例：She go to school every day.（谓语未用第三人称单数）"
    )


def _llm_trace_inputs(inputs: dict) -> dict:
    """把内部消息对象转成可读的 trace 输入。"""
    return {
        "messages": [
            {"role": item.role, "content": item.content}
            for item in inputs.get("messages", [])
        ]
    }


def _join_chunks(chunks: list[str]) -> str:
    return "".join(chunks)


class OpenAICompatibleClient:
    """OpenAI 兼容 /chat/completions 客户端，SSE 流式解析增量文本。"""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model

    @traceable(
        run_type="llm",
        name="llm.chat_completion",
        process_inputs=_llm_trace_inputs,
        reduce_fn=_join_chunks,
    )
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        annotate_trace(model=self._model)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "stream": True,
        }
        timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=REQUEST_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as http:
            async with http.stream("POST", self._url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")[:300]
                    raise RuntimeError(f"模型服务返回 HTTP {response.status_code}：{body}")
                async for line in response.aiter_lines():
                    chunk = _parse_sse_data_line(line)
                    if chunk:
                        yield chunk


def _parse_sse_data_line(line: str) -> str | None:
    """解析 OpenAI 兼容流的一行 SSE 数据，提取 delta 文本。"""
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return None
    data = stripped.removeprefix("data:").strip()
    if data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
        return payload["choices"][0]["delta"].get("content")
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def is_mock_provider() -> bool:
    """是否应使用 Mock 客户端：显式 mock，或真实服务配置不完整。"""
    settings = get_settings()
    provider = (settings.AI_PROVIDER or "").strip().lower()
    return provider in ("", "mock") or not (settings.AI_PROVIDER_URL and settings.AI_PROVIDER_KEY)


@lru_cache
def get_llm_client() -> LLMClient:
    """按配置选择真实客户端或 Mock 客户端，进程内单例。"""
    if is_mock_provider():
        settings = get_settings()
        if (settings.AI_PROVIDER or "").strip().lower() not in ("", "mock"):
            logger.warning(
                "AI_PROVIDER=%s 但 AI_PROVIDER_URL 或 AI_PROVIDER_KEY 未配置，已回退到 Mock 客户端",
                settings.AI_PROVIDER,
            )
        return MockLLMClient()
    settings = get_settings()
    return OpenAICompatibleClient(
        settings.AI_PROVIDER_URL, settings.AI_PROVIDER_KEY, settings.AI_MODEL
    )
