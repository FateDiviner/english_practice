"""Skill 技能包：每个 Skill 处理一种意图。"""

from app.services.agent.skills.base import Skill, SkillContext, SkillRegistry
from app.services.agent.skills.explain_word import ExplainWordSkill
from app.services.agent.skills.grammar import GrammarSkill
from app.services.agent.skills.oral_practice import OralPracticeSkill


def build_default_registry() -> SkillRegistry:
    """注册全部技能，供 AgentService 按意图分发。"""
    return SkillRegistry([ExplainWordSkill(), GrammarSkill(), OralPracticeSkill()])


__all__ = [
    "ExplainWordSkill",
    "GrammarSkill",
    "OralPracticeSkill",
    "Skill",
    "SkillContext",
    "SkillRegistry",
    "build_default_registry",
]
