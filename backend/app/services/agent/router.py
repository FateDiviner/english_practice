"""主 Router：识别用户意图并返回 Intent 枚举。"""

from app.services.agent.client import ChatMessage, LLMClient
from app.services.agent.heuristics import keyword_classify
from app.services.agent.intent import Intent
from app.services.agent.prompts import ROUTER_PROMPT_TEMPLATE


def parse_intent(raw: str) -> Intent | None:
    """把模型输出解析为 Intent 枚举，解析失败返回 None。"""
    normalized = raw.strip().upper().strip("`'\" .。!！")
    for intent in Intent:
        if intent.value in normalized:
            return intent
    return None


class IntentRouter:
    """用大模型做意图分类；模型输出非法时回退到本地关键词规则。"""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def classify(self, message: str) -> Intent:
        prompt = ROUTER_PROMPT_TEMPLATE.format(message=message)
        chunks = [
            chunk async for chunk in self._llm.stream([ChatMessage(role="user", content=prompt)])
        ]
        return parse_intent("".join(chunks)) or keyword_classify(message)
