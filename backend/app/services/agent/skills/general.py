"""Skill：通用兜底——处理其他问答与非学习类请求。"""

from app.services.agent.intent import Intent
from app.services.agent.prompts import GENERAL_SYSTEM_PROMPT
from app.services.agent.skills.base import Skill, SkillContext


class GeneralSkill(Skill):
    intent = Intent.GENERAL
    name = "general"
    description = "处理普通问答、闲聊和无法归入其他技能的问题"

    def system_prompt(self, context: SkillContext) -> str:
        return GENERAL_SYSTEM_PROMPT
