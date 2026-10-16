"""审计留痕服务。

record() 只往会话里 add，**不 commit**——调用方必须在同一个事务里提交，
保证「业务写入」与「审计写入」要么同时成功要么同时失败。
"""

from __future__ import annotations

import json

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User

# 这些字段一旦进入 detail 就等于把凭据写进了日志，直接拒绝
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "content",
        "messages",
    }
)


class AuditError(ValueError):
    """审计写入被拒绝，通常是因为 detail 里混进了敏感字段。"""


def _assert_no_secrets(detail: dict | None) -> None:
    if not detail:
        return
    for key in detail:
        if str(key).lower() in SENSITIVE_KEYS:
            raise AuditError(f"审计 detail 不得包含敏感字段: {key}")


def record(
    db: Session,
    *,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: int | str | None = None,
    detail: dict | None = None,
    affected_rows: int = 0,
    request: Request | None = None,
) -> AuditLog:
    """在当前事务里写一条审计。调用方负责 commit。"""
    _assert_no_secrets(detail)

    ip = None
    user_agent = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = (request.headers.get("user-agent") or "")[:255] or None

    entry = AuditLog(
        actor_id=actor.id,
        actor_name=actor.username,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        affected_rows=affected_rows,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry
