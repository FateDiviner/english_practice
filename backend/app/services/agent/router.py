"""主 Router：为注册技能评分，并返回带置信度的路由决策。"""

import json
import logging
import re
from dataclasses import dataclass

from app.services.agent.client import ChatMessage, LLMClient
from app.services.agent.heuristics import keyword_classify
from app.services.agent.intent import Intent
from app.services.agent.prompts import ROUTER_SCORE_PROMPT_TEMPLATE
from app.services.agent.skills.base import SkillRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteCandidate:
    intent: Intent
    skill: str
    score: int


@dataclass(frozen=True)
class RouteDecision:
    intent: Intent
    skill: str
    confidence: int
    candidates: list[RouteCandidate]
    fallback_used: bool
    reason: str | None = None


def parse_intent(raw: str) -> Intent | None:
    """把模型输出解析为 Intent 枚举，解析失败返回 None。"""
    normalized = raw.strip().upper().strip("`'\" .。!！")
    for intent in Intent:
        if intent.value in normalized:
            return intent
    return None


def _parse_score_payload(
    raw: str,
    registry: SkillRegistry,
) -> tuple[dict[Intent, int], str | None] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    score_payload = payload.get("scores", payload)
    if not isinstance(score_payload, dict):
        return None

    scores: dict[Intent, int] = {}
    for raw_intent, raw_score in score_payload.items():
        intent = parse_intent(str(raw_intent))
        if intent is None or not registry.has(intent):
            continue
        try:
            score = int(float(raw_score))
        except (TypeError, ValueError):
            continue
        scores[intent] = max(0, min(100, score))

    if not scores:
        return None
    for intent in registry.list_intents():
        scores.setdefault(intent, 0)

    reason = payload.get("reason")
    return scores, reason if isinstance(reason, str) else None


def _fallback_scores(message: str, registry: SkillRegistry) -> dict[Intent, int]:
    selected = keyword_classify(message)
    scores = {intent: 5 for intent in registry.list_intents()}
    scores[registry.default_intent] = max(scores.get(registry.default_intent, 0), 35)
    if registry.has(selected):
        scores[selected] = 90
    else:
        scores[registry.default_intent] = 90
    return scores


def _build_decision(
    scores: dict[Intent, int],
    registry: SkillRegistry,
    *,
    fallback_used: bool,
    reason: str | None,
) -> RouteDecision:
    candidates = sorted(
        [
            RouteCandidate(intent=intent, skill=registry.get(intent).name, score=score)
            for intent, score in scores.items()
        ],
        key=lambda item: (item.score, item.intent == registry.default_intent),
        reverse=True,
    )
    best = candidates[0] if candidates else None
    if best is None or not registry.has(best.intent):
        intent = registry.default_intent
        confidence = 0
    else:
        intent = best.intent
        confidence = best.score
    return RouteDecision(
        intent=intent,
        skill=registry.get(intent).name,
        confidence=confidence,
        candidates=candidates,
        fallback_used=fallback_used,
        reason=reason,
    )


class IntentRouter:
    """LLM 多技能评分路由；模型调用或解析失败时回退到本地关键词规则。"""

    def __init__(self, llm: LLMClient, skills: SkillRegistry) -> None:
        self._llm = llm
        self._skills = skills

    async def decide(self, message: str) -> RouteDecision:
        prompt = ROUTER_SCORE_PROMPT_TEMPLATE.format(
            skills_desc=self._skills.describe_for_router(),
            json_example=json.dumps(self._skills.score_schema(), ensure_ascii=False),
            message=message,
        )
        try:
            chunks = [
                chunk
                async for chunk in self._llm.stream(
                    [ChatMessage(role="user", content=prompt)]
                )
            ]
            parsed = _parse_score_payload("".join(chunks), self._skills)
        except Exception:
            logger.exception("LLM routing failed; falling back to keyword rules")
            parsed = None

        if parsed is not None:
            scores, reason = parsed
            return _build_decision(
                scores,
                self._skills,
                fallback_used=False,
                reason=reason,
            )

        return _build_decision(
            _fallback_scores(message, self._skills),
            self._skills,
            fallback_used=True,
            reason="LLM 路由输出无效，已使用本地关键词规则",
        )

    async def classify(self, message: str) -> Intent:
        """兼容只需要意图枚举的调用方。"""
        return (await self.decide(message)).intent

    async def route(self, message: str) -> str:
        """返回命中的技能名称，便于调试或非流式调用。"""
        return (await self.decide(message)).skill
