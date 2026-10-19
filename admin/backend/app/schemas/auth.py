"""管理端认证契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminRegisterRequest(BaseModel):
    """管理员注册。

    invite_code 仅在配置了 ADMIN_INVITE_CODE 时才需要；
    未配置时退化为「首个管理员」规则。
    """

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    invite_code: str | None = Field(default=None, max_length=128)


class AdminLoginRequest(BaseModel):
    """管理端登录。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class AdminUserOut(BaseModel):
    """管理端视角的用户信息。

    刻意不含 password_hash——它在任何管理接口响应里都不该出现。
    """

    id: int
    username: str
    is_guest: bool
    role: str
    status: str
    active_wordbook_id: int | None = None
    consecutive_days: int = 0
    created_at: str
    # 最近一次活跃（练习会话）；从未练习过为 None
    last_practiced_at: str | None = None
    practice_count: int = 0


class AdminAuthResponse(BaseModel):
    """注册 / 登录统一响应。"""

    access_token: str
    token_type: str = "bearer"
    user: AdminUserOut
