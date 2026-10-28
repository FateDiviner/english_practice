"""Skill B：口语对练——特定场景多轮英文对话并纠错。"""

from app.services.agent.intent import Intent
from app.services.agent.prompts import ORAL_PRACTICE_SYSTEM_PROMPT
from app.services.agent.skills.base import Skill, SkillContext

ORAL_SCENES: dict[str, str] = {
    "restaurant": "餐厅点餐，你是服务员，引导顾客完成点餐",
    "interview": "求职面试，你是面试官，进行简短英文面试",
    "hotel": "酒店入住，你是前台，协助办理入住",
    "airport": "机场值机，你是值机柜台工作人员",
}

DEFAULT_SCENE = "restaurant"


class OralPracticeSkill(Skill):
    intent = Intent.ORAL_PRACTICE
    name = "oral_practice"
    description = "在特定场景下与用户进行多轮英文对话并纠错"

    def system_prompt(self, context: SkillContext) -> str:
        scene = resolve_scene(context.scene)
        return ORAL_PRACTICE_SYSTEM_PROMPT.format(scene=scene)


def resolve_scene(scene: str | None) -> str:
    """把请求中的场景标识解析为中文场景描述，未知场景回退默认点餐。"""
    if not scene:
        return ORAL_SCENES[DEFAULT_SCENE]
    return ORAL_SCENES.get(scene, ORAL_SCENES[DEFAULT_SCENE])
