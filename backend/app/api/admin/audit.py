"""管理端审计日志查询路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut, AuditLogPage

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    action: str | None = Query(default=None, max_length=64, description="按动作筛选"),
    actor_id: int | None = Query(default=None, description="按操作人筛选"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    """分页查询审计日志，按时间倒序。"""
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)

    total = db.scalar(
        select(func.count(AuditLog.id)).where(*filters) if filters else select(func.count(AuditLog.id))
    )
    rows = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        AuditLogOut(
            id=row.id,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            detail=row.detail,
            affected_rows=row.affected_rows,
            ip=row.ip,
            user_agent=row.user_agent,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    return AuditLogPage(total=total or 0, items=items)
