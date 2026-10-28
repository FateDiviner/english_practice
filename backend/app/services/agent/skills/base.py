"""Skill 抽象基类与注册表。"""

from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from app.services.agent.client import ChatMessage
from app.services.agent.intent import Intent


@dataclass
class SkillContext:
    """Skill 处理时需要的上下文（如口语场景、多轮历史）。"""

    scene: str | None = None
    history: list[ChatMessage] = field(default_factory=list)


class Skill(ABC):
    """技能基类：每种意图一个实现，负责构造发给大模型的消息列表。"""

    intent: Intent
    name: str
    description: str

    def build_messages(self, user_message: str, context: SkillContext) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=self.system_prompt(context))]
        messages.extend(context.history)
        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def system_prompt(self, context: SkillContext) -> str:
        raise NotImplementedError


class SkillRegistry:
    """Intent -> Skill 的映射，同时为 Router 动态提供技能说明。"""

    def __init__(
        self,
        skills: list[Skill],
        default_intent: Intent | None = None,
    ) -> None:
        if not skills:
            raise ValueError("at least one skill is required")
        self._skills: dict[Intent, Skill] = {}
        self._default_intent: Intent | None = None
        for skill in skills:
            self.register(skill)
        if default_intent is not None and default_intent in self._skills:
            self._default_intent = default_intent
        if self._default_intent is None:
            self._default_intent = next(iter(self._skills))

    def register(self, skill: Skill, *, as_default: bool = False) -> None:
        """动态注册技能；重复意图会报错，避免静默覆盖。"""
        if skill.intent in self._skills:
            raise ValueError(f"skill intent already registered: {skill.intent.value}")
        self._skills[skill.intent] = skill
        if as_default or self._default_intent is None:
            self._default_intent = skill.intent

    def get(self, intent: Intent) -> Skill:
        """返回指定技能；未知意图回退到默认技能。"""
        return self._skills.get(intent, self._skills[self._default_intent])

    def get_by_name(self, name: str) -> Skill | None:
        normalized = name.strip().lower()
        return next(
            (skill for skill in self._skills.values() if skill.name == normalized),
            None,
        )

    def has(self, intent: Intent) -> bool:
        return intent in self._skills

    def list_intents(self) -> list[Intent]:
        return list(self._skills)

    def describe_for_router(self) -> str:
        return "\n".join(
            f"- {skill.intent.value} ({skill.name}): {skill.description}"
            for skill in self._skills.values()
        )

    def score_schema(self) -> dict[str, Any]:
        return {
            "scores": {intent.value: 0 for intent in self._skills},
            "reason": "简短说明路由依据",
        }

    @property
    def default_intent(self) -> Intent:
        return self._default_intent
