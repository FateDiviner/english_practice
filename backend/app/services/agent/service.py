"""AgentService：编排 Router -> Skill -> 大模型流式输出，并封装 SSE 事件。"""

import json
from collections.abc import AsyncIterator
from functools import lru_cache

from app.services.agent.client import ChatMessage, get_llm_client
from app.services.agent.router import IntentRouter
from app.services.agent.skills import SkillContext, build_default_registry
from app.services.agent.skills.base import SkillRegistry


def format_sse(event: str, payload: dict) -> str:
    """把事件名与 JSON 负载格式化为一条 SSE 消息。"""
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n"


class AgentService:
    """智能伴学辅导体核心服务：意图识别、技能分发、流式回复。"""

    def __init__(self, router: IntentRouter, skills: SkillRegistry, llm) -> None:
        self._router = router
        self._skills = skills
        self._llm = llm

    async def stream_chat(
        self,
        message: str,
        scene: str | None = None,
        history: list[ChatMessage] | None = None,
    ) -> AsyncIterator[str]:
        decision = await self._router.decide(message)
        skill = self._skills.get(decision.intent)
        context = SkillContext(scene=scene, history=list(history or []))
        yield format_sse(
            "meta",
            {
                "intent": decision.intent.value,
                "skill": skill.name,
                "scene": context.scene,
                "confidence": decision.confidence,
                "fallback_used": decision.fallback_used,
                "candidates": [
                    {
                        "intent": item.intent.value,
                        "skill": item.skill,
                        "score": item.score,
                    }
                    for item in decision.candidates
                ],
                "reason": decision.reason,
            },
        )
        messages = skill.build_messages(message, context)
        async for chunk in self._llm.stream(messages):
            yield format_sse("delta", {"content": chunk})
        yield format_sse("done", {"finish_reason": "stop"})


@lru_cache
def get_agent_service() -> AgentService:
    """构建进程级单例：共享一个大模型客户端。"""
    llm = get_llm_client()
    skills = build_default_registry()
    return AgentService(router=IntentRouter(llm, skills), skills=skills, llm=llm)
