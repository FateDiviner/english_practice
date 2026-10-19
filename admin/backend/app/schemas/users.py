"""管理端用户管理契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.auth import AdminUserOut


class AdminCreateUserRequest(BaseModel):
    """新增用户（管理端代建）。"""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    # user: 普通用户 / admin: 管理员
    role: str = Field(default="user", pattern="^(user|admin)$")


class AdminUpdateUserRequest(BaseModel):
    """启用 / 封禁 / 调整角色，至少给一项。"""

    role: str | None = Field(default=None, pattern="^(user|admin)$")
    # active: 启用 / banned: 封禁
    status: str | None = Field(default=None, pattern="^(active|banned)$")


class AdminUserListPage(BaseModel):
    """分页结果。"""

    total: int
    items: list[AdminUserOut] = Field(default_factory=list)
