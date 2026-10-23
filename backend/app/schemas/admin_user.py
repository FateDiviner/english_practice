from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.stats import StatsOverviewOut


class AdminUserItem(BaseModel):
    id: int
    username: str
    email: str
    role: Literal["user", "admin"]
    status: Literal["active", "disabled"]
    created_at: datetime
    total_practiced: int


class AdminUserListOut(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class UserStatusIn(BaseModel):
    status: Literal["active", "disabled"]


class UserStatusOut(BaseModel):
    id: int
    status: Literal["active", "disabled"]


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)


class ResetPasswordOut(BaseModel):
    reset: bool


class UserStatsOut(StatsOverviewOut):
    pass
