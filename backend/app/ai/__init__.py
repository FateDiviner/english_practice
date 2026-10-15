"""AI 伴学模块导出。"""

from app.ai.client import AIError, stream_chat
from app.ai.corrections import feedback_from_json, feedback_to_json, parse_feedback
from app.ai.prompts import PRESETS, build_messages

__all__ = [
    "AIError",
    "stream_chat",
    "parse_feedback",
    "feedback_to_json",
    "feedback_from_json",
    "build_messages",
    "PRESETS",
]
