"""管理端业务错误。

与认证层的 AuthError 分开：AuthError 语义仅限登录注册（邀请码、密码、重名），
不要复用到词库与用户管理，否则调用方无法从状态码区分「登录失败」和
「你没有权限删这个用户」。
"""

from __future__ import annotations


class AdminError(Exception):
    """管理端业务错误，携带 HTTP 状态码，由 API 层的 _guard 统一转换。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
