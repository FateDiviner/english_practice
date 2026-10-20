"""管理端路由。全部路由都要求管理员身份，由 require_admin 依赖把关。"""

from app.api.admin import audit, kb, rag, relations, users, words

__all__ = ["users", "words", "relations", "kb", "rag", "audit"]
