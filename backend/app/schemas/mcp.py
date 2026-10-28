from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

McpChangeStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "executed",
    "failed",
    "expired",
    "cancelled",
]


class McpChangeOut(BaseModel):
    id: int
    action_type: str
    target_type: str | None
    target_id: int | None
    payload: dict[str, Any]
    summary: str
    reason: str | None
    status: McpChangeStatus
    requested_by: int
    requested_by_username: str | None = None
    approved_by: int | None
    client_name: str | None
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    expires_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None


class McpChangeListOut(BaseModel):
    items: list[McpChangeOut]
    total: int
    page: int
    page_size: int


class RejectChangeIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
