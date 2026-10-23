"""Skill 抽象基类与注册表。"""

from abc import ABC
from dataclasses import dataclass, field

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
    """Intent -> Skill 的映射，主 Router 识别意图后由此分发。"""

    def __init__(self, skills: list[Skill]) -> None:
        self._skills = {skill.intent: skill for skill in skills}

    def get(self, intent: Intent) -> Skill:
        return self._skills[intent]

    def list_intents(self) -> list[Intent]:
        return list(self._skills)
