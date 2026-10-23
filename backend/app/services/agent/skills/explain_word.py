"""Skill A：单词解析——词根词缀、例句、记忆法。"""

from app.services.agent.intent import Intent
from app.services.agent.prompts import EXPLAIN_WORD_SYSTEM_PROMPT
from app.services.agent.skills.base import Skill, SkillContext


class ExplainWordSkill(Skill):
    intent = Intent.EXPLAIN_WORD
    name = "explain_word"
    description = "解析英文单词的词根词缀、例句与记忆方法"

    def system_prompt(self, context: SkillContext) -> str:
        return EXPLAIN_WORD_SYSTEM_PROMPT
