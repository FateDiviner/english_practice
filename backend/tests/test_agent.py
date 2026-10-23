"""智能伴学 Agent 单元测试：Mock 客户端 + Router + Skill + SSE 事件流。"""

import json

from app.services.agent.client import ChatMessage, MockLLMClient
from app.services.agent.intent import Intent
from app.services.agent.router import IntentRouter, parse_intent
from app.services.agent.service import AgentService
from app.services.agent.skills import build_default_registry


async def _collect(
    service: AgentService, message: str, scene: str | None = None
) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    async for raw in service.stream_chat(message, scene=scene):
        for block in raw.strip().split("\n\n"):
            lines = block.splitlines()
            event = lines[0].removeprefix("event: ")
            payload = json.loads(lines[1].removeprefix("data: "))
            events.append((event, payload))
    return events


async def test_mock_client_streams_full_text() -> None:
    client = MockLLMClient()
    messages = [
        ChatMessage(role="system", content="[SKILL:EXPLAIN_WORD] 你是单词老师"),
        ChatMessage(role="user", content="abandon 是什么意思"),
    ]
    chunks = [chunk async for chunk in client.stream(messages)]
    assert len(chunks) > 1
    assert "abandon" in "".join(chunks)


async def test_parse_intent_accepts_enum_text() -> None:
    assert parse_intent("EXPLAIN_WORD") == Intent.EXPLAIN_WORD
    assert parse_intent(" grammar ") == Intent.GRAMMAR
    assert parse_intent("随便聊聊") is None
    assert parse_intent("oral_practice") == Intent.ORAL_PRACTICE


async def test_router_classify_word_question() -> None:
    router = IntentRouter(MockLLMClient())
    assert await router.classify("abandon 是什么意思") == Intent.EXPLAIN_WORD
    assert await router.classify("meticulous") == Intent.EXPLAIN_WORD


async def test_router_classify_grammar_and_oral() -> None:
    router = IntentRouter(MockLLMClient())
    assert await router.classify("过去完成时怎么用") == Intent.GRAMMAR
    assert await router.classify("我想练口语，来个面试对话") == Intent.ORAL_PRACTICE


async def test_service_stream_chat_emits_meta_delta_done() -> None:
    llm = MockLLMClient()
    service = AgentService(router=IntentRouter(llm), skills=build_default_registry(), llm=llm)
    events = await _collect(service, "abandon 是什么意思")
    names = [event for event, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert set(names) == {"meta", "delta", "done"}
    assert events[0][1]["intent"] == Intent.EXPLAIN_WORD.value
    assert events[0][1]["skill"] == "explain_word"
    content = "".join(payload["content"] for event, payload in events if event == "delta")
    assert "abandon" in content


async def test_service_stream_chat_oral_practice_scene() -> None:
    llm = MockLLMClient()
    service = AgentService(router=IntentRouter(llm), skills=build_default_registry(), llm=llm)
    events = await _collect(service, "帮我练点餐口语", scene="restaurant")
    assert events[0][1]["intent"] == Intent.ORAL_PRACTICE
    assert events[0][1]["scene"] == "restaurant"


async def test_agent_chat_requires_login(client) -> None:
    response = await client.post("/api/v1/agent/chat", json={"message": "hello"})
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_agent_chat_streams_sse(client) -> None:
    from tests.practice_answer_helpers import create_user

    headers, _ = await create_user(client, "agent_chat")
    response = await client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "abandon 是什么意思", "scene": None, "history": []},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: done" in body
    meta_line = next(line for line in body.splitlines() if line.startswith("data: {"))
    assert json.loads(meta_line.removeprefix("data: "))["intent"] == Intent.EXPLAIN_WORD.value
