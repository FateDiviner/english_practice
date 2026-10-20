"""LangGraph 编排：规划、白名单工具、上下文合并与最终流式回答。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    ToolMessage,
    convert_to_messages,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime

from app.ai.agent.context import compile_references
from app.ai.agent.model import (
    AgentToolUnsupported,
    as_ai_error,
    classify_planner_error,
    create_chat_model,
)
from app.ai.agent.tools import (
    format_word_results,
    run_knowledge_search,
    run_lookup_word,
    tool_specs,
)
from app.ai.client import AIError
from app.ai.prompts import build_agent_plan_messages, build_messages
from app.config import get_settings
from app.rag.types import RagResult

logger = logging.getLogger(__name__)

MAX_TOOLS_PER_ROUND = 2
DIRECT_PRESETS = {"grammar_check", "free_chat"}


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    history: list[dict[str, str]]
    user_input: str
    preset: str | None
    context: str | None
    route_mode: Literal["direct", "agent"]
    tool_round: int
    max_tool_rounds: int
    rag_enabled: bool
    retrievals: list[RagResult]
    word_results: list[dict[str, str]]
    tools_used: list[str]
    compiled_context: str
    sources: list[dict]
    final_text: str


def _append_unique(items: list[str], values: list[str]) -> list[str]:
    merged = list(items)
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def _route_node(state: AgentState) -> dict:
    preset = state.get("preset")
    mode: Literal["direct", "agent"] = "direct" if preset in DIRECT_PRESETS else "agent"
    return {"route_mode": mode}


def _route_next(state: AgentState) -> str:
    return "direct" if state.get("route_mode") == "direct" else "agent"


def _plan_next(state: AgentState) -> str:
    messages = state.get("messages") or []
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        if state.get("tool_round", 0) < state.get("max_tool_rounds", 2):
            return "tools"
    return "compile"


def _tool_error(call_id: str, name: str, message: str) -> ToolMessage:
    return ToolMessage(
        content=f"Tool {name} failed: {message}",
        tool_call_id=call_id,
        name=name,
        status="error",
    )


async def _tools_node(state: AgentState, runtime: Runtime) -> dict:
    messages = state.get("messages") or []
    calls = (
        list(messages[-1].tool_calls or [])
        if messages and isinstance(messages[-1], AIMessage)
        else []
    )
    round_number = state.get("tool_round", 0) + 1
    tool_messages: list[ToolMessage] = []
    new_retrievals: list[RagResult] = []
    new_words: list[dict[str, str]] = []
    used: list[str] = []

    for position, call in enumerate(calls):
        name = str(call.get("name") or "")
        call_id = str(call.get("id") or f"agent_call_{round_number}_{position}")
        args = call.get("args") or {}
        used.append(name)

        if position >= MAX_TOOLS_PER_ROUND:
            runtime.stream_writer(
                {
                    "type": "tool_result",
                    "tool": name,
                    "round": round_number,
                    "success": False,
                    "reason": "tool_budget",
                }
            )
            tool_messages.append(
                _tool_error(call_id, name, "Only two tool calls are allowed in one round.")
            )
            continue

        if name == "knowledge_search":
            if not state.get("rag_enabled"):
                tool_messages.append(_tool_error(call_id, name, "Knowledge search is disabled."))
                continue
            query = args.get("query")
            if not isinstance(query, str) or not query.strip():
                tool_messages.append(
                    _tool_error(call_id, name, "query must be a non-empty string.")
                )
                continue

            runtime.stream_writer(
                {
                    "type": "tool_call",
                    "tool": name,
                    "round": round_number,
                    "query": query[:120],
                }
            )
            runtime.stream_writer({"type": "status", "phase": "retrieving"})
            try:
                result = await asyncio.to_thread(
                    run_knowledge_search, query, state.get("history") or []
                )
            except Exception:  # noqa: BLE001 - 工具失败不阻断对话
                logger.exception("Agent knowledge_search failed")
                runtime.stream_writer(
                    {"type": "status", "phase": "skipped", "reason": "检索异常"}
                )
                runtime.stream_writer(
                    {
                        "type": "tool_result",
                        "tool": name,
                        "round": round_number,
                        "success": False,
                        "reason": "retrieval_error",
                    }
                )
                tool_messages.append(_tool_error(call_id, name, "retrieval failed"))
                continue

            if result.hits:
                new_retrievals.append(result)
                runtime.stream_writer(
                    {
                        "type": "status",
                        "phase": "retrieved",
                        "hits": len(result.hits),
                        "sources": result.sources,
                    }
                )
                tool_content = (
                    f"Retrieved {len(result.hits)} grounded passages:\n\n{result.context}"
                )
                success = True
                reason = None
            else:
                reason = result.skipped or "no relevant material"
                runtime.stream_writer(
                    {"type": "status", "phase": "skipped", "reason": reason}
                )
                tool_content = f"No relevant material was found: {reason}"
                success = True

            runtime.stream_writer(
                {
                    "type": "tool_result",
                    "tool": name,
                    "round": round_number,
                    "success": success,
                    "hits": len(result.hits),
                    "reason": reason,
                }
            )
            tool_messages.append(
                ToolMessage(
                    content=tool_content,
                    tool_call_id=call_id,
                    name=name,
                    status="success",
                )
            )
            continue

        if name == "lookup_word":
            word = args.get("word")
            if not isinstance(word, str) or not word.strip():
                tool_messages.append(
                    _tool_error(call_id, name, "word must be a non-empty string.")
                )
                continue

            runtime.stream_writer(
                {
                    "type": "tool_call",
                    "tool": name,
                    "round": round_number,
                    "query": word[:120],
                }
            )
            try:
                results = await asyncio.to_thread(run_lookup_word, word)
            except Exception:  # noqa: BLE001 - 工具失败不阻断对话
                logger.exception("Agent lookup_word failed")
                runtime.stream_writer(
                    {
                        "type": "tool_result",
                        "tool": name,
                        "round": round_number,
                        "success": False,
                        "reason": "lookup_error",
                    }
                )
                tool_messages.append(_tool_error(call_id, name, "word lookup failed"))
                continue

            if results:
                new_words.extend(results)
            runtime.stream_writer(
                {
                    "type": "tool_result",
                    "tool": name,
                    "round": round_number,
                    "success": True,
                    "hits": len(results),
                }
            )
            tool_messages.append(
                ToolMessage(
                    content=format_word_results(results),
                    tool_call_id=call_id,
                    name=name,
                    status="success",
                )
            )
            continue

        runtime.stream_writer(
            {
                "type": "tool_result",
                "tool": name or "unknown",
                "round": round_number,
                "success": False,
                "reason": "unknown_tool",
            }
        )
        tool_messages.append(_tool_error(call_id, name or "unknown", "unknown tool"))

    return {
        "messages": tool_messages,
        "tool_round": round_number,
        "retrievals": state.get("retrievals", []) + new_retrievals,
        "word_results": state.get("word_results", []) + new_words,
        "tools_used": _append_unique(state.get("tools_used", []), used),
    }


def _compile_node(state: AgentState) -> dict:
    context, sources = compile_references(
        state.get("retrievals", []),
        state.get("word_results", []),
    )
    return {
        "compiled_context": context,
        "sources": [source.model_dump() for source in sources],
    }


async def _respond_node(state: AgentState, runtime: Runtime, model: BaseChatModel) -> dict:
    runtime.stream_writer({"type": "agent", "phase": "responding"})
    messages = build_messages(
        history=state.get("history") or [],
        user_input=state.get("user_input", ""),
        preset=state.get("preset"),
        context=state.get("context"),
        rag_context=state.get("compiled_context") or None,
    )
    chunks: list[str] = []
    try:
        async for chunk in model.astream(convert_to_messages(messages)):
            text = chunk.text
            if not text:
                continue
            chunks.append(text)
            runtime.stream_writer({"type": "delta", "delta": text})
    except Exception as exc:  # noqa: BLE001 - 统一转成聊天层错误
        raise as_ai_error(exc) from exc

    content = "".join(chunks).strip()
    if not content:
        raise AIError("模型未返回内容，请稍后重试", status_code=502, retryable=True)

    runtime.stream_writer(
        {
            "type": "result",
            "content": content,
            "metadata": {
                "mode": "agent",
                "rounds": state.get("tool_round", 0),
                "tools": state.get("tools_used", []),
                "sources": state.get("sources", []),
                "fallback": None,
                "elapsed_ms": 0,
            },
        }
    )
    return {"final_text": content}


def _plan_node_factory(planner):
    async def plan(state: AgentState, runtime: Runtime) -> dict:
        round_number = state.get("tool_round", 0) + 1
        runtime.stream_writer(
            {"type": "agent", "phase": "planning", "round": round_number}
        )
        try:
            response = await planner.ainvoke(
                convert_to_messages(state.get("messages") or [])
            )
        except Exception as exc:  # noqa: BLE001 - 在节点边界分类异常
            raise classify_planner_error(exc) from exc
        return {"messages": [response]}

    return plan


def build_graph(model: BaseChatModel, planner) -> StateGraph:
    """构造请求级 StateGraph；不使用跨请求 checkpointer。"""

    graph = StateGraph(AgentState)
    graph.add_node("route", _route_node)
    graph.add_node("plan", _plan_node_factory(planner))
    graph.add_node("tools", _tools_node)
    graph.add_node("compile", _compile_node)

    async def respond(state: AgentState, runtime: Runtime) -> dict:
        return await _respond_node(state, runtime, model)

    graph.add_node("respond", respond)
    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        _route_next,
        {"direct": "compile", "agent": "plan"},
    )
    graph.add_conditional_edges(
        "plan",
        _plan_next,
        {"tools": "tools", "compile": "compile"},
    )
    graph.add_edge("tools", "plan")
    graph.add_edge("compile", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


async def stream_agent(
    *,
    history: list[dict[str, str]],
    user_input: str,
    preset: str | None,
    context: str | None,
    model: BaseChatModel | None = None,
) -> AsyncIterator[dict]:
    """运行一次 LangGraph Agent，并逐个产出 SSE 所需事件。"""

    settings = get_settings()
    chat_model = model or create_chat_model()
    specs = tool_specs(include_rag=settings.rag_enabled)
    try:
        planner = chat_model.bind_tools(specs) if specs else chat_model
    except NotImplementedError as exc:
        raise AgentToolUnsupported("当前模型不支持 Agent 工具调用") from exc

    graph = build_graph(chat_model, planner)
    initial: AgentState = {
        "messages": build_agent_plan_messages(
            history=history,
            user_input=user_input,
            preset=preset,
            context=context,
        ),
        "history": history,
        "user_input": user_input,
        "preset": preset,
        "context": context,
        "route_mode": "agent",
        "tool_round": 0,
        "max_tool_rounds": max(settings.agent_max_tool_rounds, 0),
        "rag_enabled": settings.rag_enabled,
        "retrievals": [],
        "word_results": [],
        "tools_used": [],
        "compiled_context": "",
        "sources": [],
    }
    saw_result = False
    try:
        async for event in graph.astream(
            initial,
            config={"recursion_limit": max(settings.agent_recursion_limit, 4)},
            stream_mode="custom",
        ):
            if isinstance(event, dict) and event.get("type") == "result":
                saw_result = True
            yield event
    except (AIError, AgentToolUnsupported):
        raise
    except Exception as exc:  # noqa: BLE001 - 图级异常统一归一化
        raise as_ai_error(exc) from exc

    if not saw_result:
        raise AIError("Agent 未生成最终回答，请稍后重试", status_code=502, retryable=True)
