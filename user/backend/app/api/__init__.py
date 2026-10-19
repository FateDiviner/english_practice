"""路由控制器层：负责入参校验与 HTTP 响应格式化。"""

from app.api import auth, chat, practice, wordbooks

__all__ = ["auth", "wordbooks", "practice", "chat"]
