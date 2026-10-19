"""审计日志查询契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    """一条审计记录。"""

    id: int
    actor_id: int | None = None
    actor_name: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    # JSON 字符串，前端自行解析展示；服务端不保证结构，只保证可解析
    detail: str | None = None
    affected_rows: int = 0
    ip: str | None = None
    user_agent: str | None = None
    created_at: str


class AuditLogPage(BaseModel):
    """分页结果。"""

    total: int
    items: list[AuditLogOut] = Field(default_factory=list)
