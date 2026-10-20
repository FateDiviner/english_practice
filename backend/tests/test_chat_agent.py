"""LangGraph Agent 图、工具调用、SSE 与持久化测试。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.ai.agent import AgentToolUnsupported
from app.ai.agent.graph import stream_agent
from app.ai.agent.tools import tool_specs
from app.api import chat as chat_api
from app.config import get_settings
from app.rag.types import Hit, RagResult
from app.schemas.chat import AgentMetadata

settings = get_settings()


class FakeToolModel(FakeMessagesListChatModel):
    """可返回工具调用或普通回答的确定性测试模型。"""

    def bind_tools(self, tools, **kwargs):
        return self


def parse_sse(text: str) -> list[dict]:
    frames: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    frames.append(json.loads(payload))
    return frames


async def _drain(events: AsyncIterator[dict]) -> list[dict]:
    return [event async for event in events]


def collect_agent(model: FakeToolModel, **kwargs) -> list[dict]:
    async def run() -> AsyncIterator[dict]:
        async for event in stream_agent(model=model, **kwargs):
            yield event

    return asyncio.run(_drain(run()))


def _tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


class TestAgentGraph:
    def test_direct_preset_skips_planning_and_streams_answer(self) -> None:
        model = FakeToolModel(responses=[AIMessage(content="Direct answer.")])
        events = collect_agent(
            model,
            history=[],
            user_input="hello",
            preset="free_chat",
            context=None,
        )
        assert [event["type"] for event in events] == ["agent", "delta", "result"]
        assert events[0]["phase"] == "responding"
        assert events[-1]["content"] == "Direct answer."
        assert events[-1]["metadata"]["mode"] == "agent"
        assert events[-1]["metadata"]["rounds"] == 0

    def test_knowledge_search_runs_rag_and_returns_sources(self, monkeypatch) -> None:
        rag_result = RagResult(
            context="[1] Study notes\nThe present perfect links past and present.",
            hits=[
                Hit(
                    kind="chunk",
                    source="test",
                    content="The present perfect links past and present.",
                    score=0.05,
                    metadata={"chunk_id": 1, "name": "Grammar notes"},
                )
            ],
        )
        monkeypatch.setattr(
            "app.ai.agent.graph.run_knowledge_search",
            lambda query, history: rag_result,
        )
        model = FakeToolModel(
            responses=[
                _tool_call("knowledge_search", {"query": "present perfect"}, "call_1"),
                AIMessage(content="Planning complete"),
                AIMessage(content="According to [1], the tense links both times."),
            ]
        )
        events = collect_agent(
            model,
            history=[],
            user_input="现在完成时怎么构成",
            preset=None,
            context=None,
        )
        types = [event["type"] for event in events]
        assert "tool_call" in types
        assert "status" in types
        assert "tool_result" in types
        result = next(event for event in events if event["type"] == "result")
        assert result["metadata"]["tools"] == ["knowledge_search"]
        assert result["metadata"]["rounds"] == 1
        assert result["metadata"]["sources"][0]["kind"] == "chunk"
        assert result["metadata"]["sources"][0]["index"] == 1

    def test_lookup_word_adds_wordbank_source(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.ai.agent.graph.run_lookup_word",
            lambda word: [
                {
                    "id": "42",
                    "word": "abandon",
                    "phonetic": "/əˈbændən/",
                    "translation": "v. 放弃",
                    "example_en": "They had to abandon the plan.",
                    "example_cn": "他们不得不放弃这个计划。",
                }
            ],
        )
        model = FakeToolModel(
            responses=[
                _tool_call("lookup_word", {"word": "abandon"}, "call_word"),
                AIMessage(content="Planning complete"),
                AIMessage(content="The verb means to give up completely."),
            ]
        )
        events = collect_agent(
            model,
            history=[],
            user_input="explain abandon",
            preset=None,
            context=None,
        )
        result = next(event for event in events if event["type"] == "result")
        assert result["metadata"]["tools"] == ["lookup_word"]
        assert result["metadata"]["sources"][0]["kind"] == "word"
        assert result["metadata"]["sources"][0]["label"] == "abandon"

    def test_tool_round_limit_forces_final_answer(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "agent_max_tool_rounds", 1)
        monkeypatch.setattr("app.ai.agent.graph.run_lookup_word", lambda word: [])
        model = FakeToolModel(
            responses=[
                _tool_call("lookup_word", {"word": "alpha"}, "call_1"),
                _tool_call("lookup_word", {"word": "beta"}, "call_2"),
                AIMessage(content="Final answer after the tool budget."),
            ]
        )
        events = collect_agent(
            model,
            history=[],
            user_input="compare alpha and beta",
            preset=None,
            context=None,
        )
        tool_results = [
            event for event in events if event.get("type") == "tool_result"
        ]
        assert len(tool_results) == 1
        result = next(event for event in events if event["type"] == "result")
        assert result["metadata"]["rounds"] == 1
        assert result["content"].startswith("Final answer")

    def test_rag_disabled_removes_knowledge_tool(self) -> None:
        names = [item["function"]["name"] for item in tool_specs(include_rag=False)]
        assert names == ["lookup_word"]


class TestAgentChatApi:
    def test_agent_events_done_and_history_metadata(
        self, auth_client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "agent_enabled", True)
        monkeypatch.setattr(settings, "ai_base_url", "http://model.test")
        monkeypatch.setattr(settings, "ai_api_key", "test-key")
        monkeypatch.setattr(settings, "ai_model", "test-model")

        async def fake_stream_agent(**kwargs) -> AsyncIterator[dict]:
            yield {"type": "agent", "phase": "planning", "round": 1}
            yield {"type": "tool_call", "tool": "knowledge_search", "round": 1}
            yield {"type": "status", "phase": "retrieving"}
            yield {"type": "status", "phase": "retrieved", "hits": 2, "sources": []}
            yield {"type": "delta", "delta": "Grounded answer."}
            yield {
                "type": "result",
                "content": "Grounded answer.",
                "metadata": {
                    "mode": "agent",
                    "rounds": 1,
                    "tools": ["knowledge_search"],
                    "sources": [
                        {
                            "index": 1,
                            "kind": "chunk",
                            "label": "Notes",
                            "source": "test",
                        }
                    ],
                    "fallback": None,
                    "elapsed_ms": 0,
                },
            }

        monkeypatch.setattr(chat_api, "stream_agent", fake_stream_agent)
        response = auth_client.post("/api/chat/send", json={"content": "Explain this"})
        assert response.status_code == 200
        frames = parse_sse(response.text)
        types = [frame["type"] for frame in frames]
        assert types[0] == "start"
        assert "agent" in types
        assert "tool_call" in types
        assert "delta" in types
        assert types[-1] == "done"

        done = frames[-1]
        assert done["metadata"]["mode"] == "agent"
        assert done["metadata"]["tools"] == ["knowledge_search"]
        assert done["sources"][0]["index"] == 1
        assert done["metadata"]["elapsed_ms"] >= 0

        history = auth_client.get("/api/chat/messages").json()
        assistant = next(item for item in reversed(history) if item["role"] == "assistant")
        assert assistant["metadata"]["mode"] == "agent"
        assert assistant["metadata"]["sources"][0]["label"] == "Notes"

    def test_tool_unsupported_falls_back_once(
        self, auth_client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "agent_enabled", True)
        monkeypatch.setattr(settings, "ai_base_url", "http://model.test")
        monkeypatch.setattr(settings, "ai_api_key", "test-key")
        monkeypatch.setattr(settings, "ai_model", "test-model")
        monkeypatch.setattr(settings, "rag_enabled", False)

        async def unsupported(**kwargs) -> AsyncIterator[dict]:
            raise AgentToolUnsupported("当前模型不支持 Agent 工具调用")
            yield  # pragma: no cover - 仅为生成器协议

        async def fake_legacy_stream(*args, **kwargs) -> AsyncIterator[str]:
            yield "Fallback answer."

        monkeypatch.setattr(chat_api, "stream_agent", unsupported)
        monkeypatch.setattr(chat_api, "stream_chat", fake_legacy_stream)

        response = auth_client.post("/api/chat/send", json={"content": "hello"})
        frames = parse_sse(response.text)
        fallback = next(
            frame
            for frame in frames
            if frame["type"] == "agent" and frame["phase"] == "fallback"
        )
        assert "不支持" in fallback["reason"]
        done = next(frame for frame in frames if frame["type"] == "done")
        assert done["metadata"]["mode"] == "chat"
        assert done["metadata"]["fallback"] == "当前模型不支持 Agent 工具调用"
        assert done["content"] == "Fallback answer."

    def test_invalid_historical_metadata_is_ignored(
        self, auth_client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "agent_enabled", False)
        monkeypatch.setattr(settings, "rag_enabled", False)

        async def fake_legacy_stream(*args, **kwargs) -> AsyncIterator[str]:
            yield "Stored."

        monkeypatch.setattr(chat_api, "stream_chat", fake_legacy_stream)
        auth_client.post("/api/chat/send", json={"content": "hello"})

        from app.db import SessionLocal
        from app.models.chat import ChatMessage

        with SessionLocal() as db:
            row = db.query(ChatMessage).order_by(ChatMessage.id.desc()).first()
            assert row is not None
            row.agent_metadata = "{broken json"
            db.commit()
            row_id = row.id

        history = auth_client.get("/api/chat/messages").json()
        message = next(item for item in history if item["id"] == row_id)
        assert message["metadata"] is None

    def test_metadata_schema_rejects_negative_values(self) -> None:
        try:
            AgentMetadata.model_validate(
                {"mode": "agent", "rounds": -1, "elapsed_ms": -2}
            )
        except Exception:
            pass
        else:
            raise AssertionError("negative agent metadata should be rejected")
