"""LangGraph Agent 的模型工厂与异常归一化。"""

from __future__ import annotations

import openai
from langchain_openai import ChatOpenAI

from app.ai.client import AIError
from app.config import get_settings


class AgentToolUnsupported(Exception):
    """当前模型或供应商不支持工具调用，应降级到标准聊天路径。"""


def create_chat_model() -> ChatOpenAI:
    """创建 OpenAI 兼容聊天模型；密钥只从后端配置读取。"""

    settings = get_settings()
    base_url = settings.ai_base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    return ChatOpenAI(
        model=settings.ai_model,
        base_url=base_url or None,
        api_key=settings.ai_api_key,
        timeout=settings.ai_timeout_seconds,
        max_retries=0,
        temperature=0,
        use_responses_api=False,
    )


def as_ai_error(exc: Exception) -> AIError:
    """把 LangChain / OpenAI 异常映射为聊天层可重试错误。"""

    if isinstance(exc, AIError):
        return exc

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code in (401, 403):
            return AIError("模型服务认证失败，请检查后端配置", status_code=401, retryable=False)
        if status_code == 429:
            return AIError("模型服务限流，请稍后重试", status_code=429, retryable=True)
        if status_code >= 500:
            return AIError(f"模型服务返回 {status_code}", status_code=502, retryable=True)
        return AIError(f"模型服务返回 {status_code}", status_code=502, retryable=False)

    if isinstance(exc, (openai.APITimeoutError, TimeoutError)):
        return AIError("模型响应超时，请稍后重试", status_code=504, retryable=True)
    if isinstance(exc, (openai.APIConnectionError, ConnectionError)):
        return AIError("模型服务连接失败，请稍后重试", status_code=502, retryable=True)

    return AIError("模型服务暂时不可用，请稍后重试", status_code=502, retryable=True)


def classify_planner_error(exc: Exception) -> Exception:
    """规划节点异常分类：工具不支持走降级，其余映射成 AIError。"""

    if isinstance(exc, (AIError, AgentToolUnsupported)):
        return exc

    message = str(exc).lower()
    unsupported_markers = (
        "tool" in message and (
            "support" in message
            or "unexpected" in message
            or "not allow" in message
            or "invalid" in message
        )
    )
    if isinstance(exc, openai.BadRequestError) or unsupported_markers:
        return AgentToolUnsupported("当前模型不支持 Agent 工具调用")
    return as_ai_error(exc)
