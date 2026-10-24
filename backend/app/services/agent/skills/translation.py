"""Skill：中英翻译——保留语气与格式，并补充关键用词。"""

from app.services.agent.intent import Intent
from app.services.agent.prompts import TRANSLATION_SYSTEM_PROMPT
from app.services.agent.skills.base import Skill, SkillContext


class TranslationSkill(Skill):
    intent = Intent.TRANSLATION
    name = "translation"
    description = "处理英译汉、汉译英，保留语气并提供关键用词说明"

    def system_prompt(self, context: SkillContext) -> str:
        return TRANSLATION_SYSTEM_PROMPT
