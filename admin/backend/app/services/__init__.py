"""管理端业务逻辑：账号管理、审计留痕与词库维护。

AdminError 是管理端专用的业务错误，由路由层转成 HTTP 响应。
core 的 AuthError 语义限定在认证（邀请码、密码、重名），不要复用到词库等操作上。
"""

from __future__ import annotations


class AdminError(Exception):
    """管理端业务错误，携带 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
