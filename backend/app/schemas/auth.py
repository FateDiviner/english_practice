"""认证相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册入参。"""

    username: str = Field(min_length=3, max_length=64, description="用户名")
    password: str = Field(min_length=6, max_length=72, description="密码")


class LoginRequest(BaseModel):
    """登录入参。"""

    username: str = Field(min_length=1, max_length=64, description="用户名")
    password: str = Field(min_length=1, max_length=72, description="密码")


class UserInfo(BaseModel):
    """用户公开信息，绝不回传密码哈希。"""

    id: int
    username: str
    is_guest: bool
    active_wordbook_id: int | None = None
    consecutive_days: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """注册 / 登录 / 游客模式统一响应体。"""

    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    # 游客账号转正时是否完成历史数据迁移
    migrated: bool = False
