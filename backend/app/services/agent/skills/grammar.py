"""Skill：语法答疑——规则讲解、例句、句子纠错。"""

from app.services.agent.intent import Intent
from app.services.agent.prompts import GRAMMAR_SYSTEM_PROMPT
from app.services.agent.skills.base import Skill, SkillContext


class GrammarSkill(Skill):
    intent = Intent.GRAMMAR
    name = "grammar"
    description = "解答英语语法问题并批改英文句子"

    def system_prompt(self, context: SkillContext) -> str:
        return GRAMMAR_SYSTEM_PROMPT
