"""Skill 技能包：每个 Skill 处理一种意图。"""

from app.services.agent.intent import Intent
from app.services.agent.skills.base import Skill, SkillContext, SkillRegistry
from app.services.agent.skills.explain_word import ExplainWordSkill
from app.services.agent.skills.general import GeneralSkill
from app.services.agent.skills.grammar import GrammarSkill
from app.services.agent.skills.oral_practice import OralPracticeSkill
from app.services.agent.skills.translation import TranslationSkill


def build_default_registry() -> SkillRegistry:
    """注册全部技能，并指定 GENERAL 为默认兜底。"""
    return SkillRegistry(
        [
            ExplainWordSkill(),
            GrammarSkill(),
            OralPracticeSkill(),
            TranslationSkill(),
            GeneralSkill(),
        ],
        default_intent=Intent.GENERAL,
    )


__all__ = [
    "ExplainWordSkill",
    "GeneralSkill",
    "GrammarSkill",
    "OralPracticeSkill",
    "Skill",
    "SkillContext",
    "SkillRegistry",
    "TranslationSkill",
    "build_default_registry",
]
