"""智能伴学 Agent 单元测试：Mock 客户端 + Router + Skill + SSE 事件流。"""

import json

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.ai_conversation import AiConversation
from app.models.ai_message import AiMessage
from app.models.user import User
from app.services.agent.client import (
    ChatMessage,
    MockLLMClient,
    OpenAICompatibleClient,
    get_llm_client,
    is_mock_provider,
)
from app.services.agent.intent import Intent
from app.services.agent.router import IntentRouter, parse_intent
from app.services.agent.service import AgentService
from app.services.agent.skills import SkillRegistry, build_default_registry
from sqlalchemy import delete, select


def _build_router(llm) -> tuple[IntentRouter, SkillRegistry]:
    skills = build_default_registry()
    return IntentRouter(llm, skills), skills


def _build_service(llm) -> AgentService:
    router, skills = _build_router(llm)
    return AgentService(router=router, skills=skills, llm=llm)


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


def test_get_llm_client_accepts_any_non_mock_provider(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "AI_PROVIDER", "Mimo")
    monkeypatch.setattr(settings, "AI_PROVIDER_URL", "https://example.com/v1")
    monkeypatch.setattr(settings, "AI_PROVIDER_KEY", "sk-test")
    get_llm_client.cache_clear()

    assert not is_mock_provider()
    assert isinstance(get_llm_client(), OpenAICompatibleClient)


def test_get_llm_client_falls_back_to_mock_without_key(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "AI_PROVIDER", "Mimo")
    monkeypatch.setattr(settings, "AI_PROVIDER_KEY", "")
    get_llm_client.cache_clear()

    assert is_mock_provider()
    assert isinstance(get_llm_client(), MockLLMClient)


async def test_parse_intent_accepts_enum_text() -> None:
    assert parse_intent("EXPLAIN_WORD") == Intent.EXPLAIN_WORD
    assert parse_intent(" grammar ") == Intent.GRAMMAR
    assert parse_intent("translation") == Intent.TRANSLATION
    assert parse_intent("GENERAL") == Intent.GENERAL
    assert parse_intent("随便聊聊") is None
    assert parse_intent("oral_practice") == Intent.ORAL_PRACTICE


def test_registry_registers_all_skills_and_default() -> None:
    registry = build_default_registry()

    assert [item.value for item in registry.list_intents()] == [
        "EXPLAIN_WORD",
        "GRAMMAR",
        "ORAL_PRACTICE",
        "TRANSLATION",
        "GENERAL",
    ]
    assert registry.default_intent == Intent.GENERAL
    assert registry.get(Intent.GENERAL).name == "general"
    assert registry.get_by_name("translation").intent == Intent.TRANSLATION


async def test_router_classify_word_question() -> None:
    router, _ = _build_router(MockLLMClient())
    assert await router.classify("abandon 是什么意思") == Intent.EXPLAIN_WORD
    assert await router.classify("meticulous") == Intent.EXPLAIN_WORD


async def test_router_classify_grammar_and_oral() -> None:
    router, _ = _build_router(MockLLMClient())
    assert await router.classify("过去完成时怎么用") == Intent.GRAMMAR
    assert await router.classify("我想练口语，来个面试对话") == Intent.ORAL_PRACTICE


async def test_router_classify_translation_and_general() -> None:
    router, _ = _build_router(MockLLMClient())
    assert await router.classify("把这句话翻译成英文：今天天气很好") == Intent.TRANSLATION
    assert await router.classify("今天午饭吃什么比较好") == Intent.GENERAL


async def test_router_classify_english_word_questions() -> None:
    router, _ = _build_router(MockLLMClient())
    assert await router.classify("What does the word abandon mean?") == Intent.EXPLAIN_WORD
    assert await router.classify("Explain the word resilient in one line.") == Intent.EXPLAIN_WORD


async def test_router_skips_llm_for_keyword_hits() -> None:
    class ExplodingLLM:
        async def stream(self, _messages):
            raise AssertionError("关键词命中时不应调用模型路由")
            yield  # pragma: no cover

    router, _ = _build_router(ExplodingLLM())
    decision = await router.decide("把这句话翻译成英文：今天天气很好")

    assert decision.intent == Intent.TRANSLATION
    assert decision.fallback_used is False
    assert "跳过模型路由" in (decision.reason or "")


async def test_router_returns_confidence_and_ranked_candidates() -> None:
    router, _ = _build_router(MockLLMClient())
    decision = await router.decide("把这句话翻译成英文：今天天气很好")

    assert decision.intent == Intent.TRANSLATION
    assert decision.skill == "translation"
    assert decision.confidence == 90
    assert decision.fallback_used is False
    assert len(decision.candidates) == 5
    assert decision.candidates[0].intent == Intent.TRANSLATION


async def test_router_falls_back_when_llm_json_is_invalid() -> None:
    class InvalidRouterLLM:
        async def stream(self, _messages):
            yield "这不是 JSON"

    router, _ = _build_router(InvalidRouterLLM())
    decision = await router.decide("解方程 x + 1 = 2")

    assert decision.intent == Intent.GENERAL
    assert decision.fallback_used is True
    assert decision.confidence == 90
    assert "本地关键词" in (decision.reason or "")


async def test_service_stream_chat_emits_meta_delta_done() -> None:
    service = _build_service(MockLLMClient())
    events = await _collect(service, "abandon 是什么意思")
    names = [event for event, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert set(names) == {"meta", "delta", "done"}
    meta = events[0][1]
    assert meta["intent"] == Intent.EXPLAIN_WORD.value
    assert meta["skill"] == "explain_word"
    assert meta["confidence"] == 90
    assert meta["fallback_used"] is False
    assert len(meta["candidates"]) == 5
    content = "".join(payload["content"] for event, payload in events if event == "delta")
    assert "abandon" in content


async def test_service_stream_chat_oral_practice_scene() -> None:
    service = _build_service(MockLLMClient())
    events = await _collect(service, "帮我练点餐口语", scene="restaurant")
    meta = events[0][1]
    assert meta["intent"] == Intent.ORAL_PRACTICE
    assert meta["scene"] == "restaurant"
    assert meta["skill"] == "oral_practice"


async def test_agent_chat_requires_login(client) -> None:
    response = await client.post("/api/v1/agent/chat", json={"message": "hello"})
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def _cleanup_user(user_id: int) -> None:
    async with async_session_factory() as session:
        conversation_ids = select(AiConversation.id).where(
            AiConversation.user_id == user_id,
        )
        await session.execute(
            delete(AiMessage).where(AiMessage.conversation_id.in_(conversation_ids)),
        )
        await session.execute(
            delete(AiConversation).where(AiConversation.user_id == user_id),
        )
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_agent_chat_streams_sse(client) -> None:
    from tests.practice_answer_helpers import create_user

    headers, user_id = await create_user(client, "agent_chat")
    try:
        response = await client.post(
            "/api/v1/agent/chat",
            headers=headers,
            json={"message": "把这句话翻译成英文：你好", "scene": None, "history": []},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text
        assert "event: meta" in body
        assert "event: delta" in body
        assert "event: done" in body
        meta_line = next(line for line in body.splitlines() if line.startswith("data: {"))
        meta = json.loads(meta_line.removeprefix("data: "))
        assert meta["intent"] == Intent.TRANSLATION.value
        assert meta["skill"] == "translation"
        assert meta["confidence"] == 90
        assert isinstance(meta["conversation_id"], int)
    finally:
        await _cleanup_user(user_id)
