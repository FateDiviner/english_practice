"""管理端用户管理：查询、代建、启用/封禁/改角色、删除。

三条硬性约束：
1. 不能对自己封禁、降级或删除——否则一次误操作就把管理员锁在门外
2. 系统必须始终保留至少一个管理员
3. 每个写操作都与审计同事务提交，业务失败则审计一起回滚
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin_api.schemas.users import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AdminUserListPage,
)
from admin_api.schemas.auth import AdminUserOut
from admin_api.services import AdminError, audit_service
from core.models.chat import ChatMessage
from core.constants import USER_STATUS_ACTIVE, USER_STATUS_BANNED
from core.models.record import UserWordRecord
from core.models.session import PracticeSessionRecord
from core.models.user import User
from core.services.auth_service import (
    AuthError,
    create_user as create_core_user,
    get_user_by_username,
)

ADMIN_ROLE = "admin"
BANNED_STATUS = USER_STATUS_BANNED


def _activity(db: Session, user_ids: list[int]) -> dict[int, tuple[int, "str | None"]]:
    """批量取活跃数据，避免列表页出现 N+1 查询。"""
    if not user_ids:
        return {}
    rows = db.execute(
        select(
            PracticeSessionRecord.user_id,
            func.count(PracticeSessionRecord.id),
            func.max(PracticeSessionRecord.created_at),
        )
        .where(PracticeSessionRecord.user_id.in_(user_ids))
        .group_by(PracticeSessionRecord.user_id)
    ).all()
    return {row[0]: (row[1], row[2].isoformat() if row[2] else None) for row in rows}


def to_admin_user(user: User, db: Session) -> AdminUserOut:
    """单个用户转管理端视图。"""
    activity = _activity(db, [user.id]).get(user.id, (0, None))
    return AdminUserOut(
        id=user.id,
        username=user.username,
        is_guest=user.is_guest,
        role=user.role,
        status=user.status,
        active_wordbook_id=user.active_wordbook_id,
        consecutive_days=user.consecutive_days or 0,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_practiced_at=activity[1],
        practice_count=activity[0],
    )


def list_users(
    db: Session,
    *,
    search: str | None = None,
    role: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminUserListPage:
    """分页查询用户。"""
    filters = []
    if search:
        filters.append(User.username.ilike(f"%{search.strip()}%"))
    if role:
        filters.append(User.role == role)
    if status:
        filters.append(User.status == status)

    total = db.scalar(
        select(func.count(User.id)).where(*filters) if filters else select(func.count(User.id))
    )
    rows = list(
        db.scalars(
            select(User).where(*filters).order_by(User.id.desc()).offset(offset).limit(limit)
        ).all()
    )
    activity = _activity(db, [row.id for row in rows])

    items = [
        AdminUserOut(
            id=row.id,
            username=row.username,
            is_guest=row.is_guest,
            role=row.role,
            status=row.status,
            active_wordbook_id=row.active_wordbook_id,
            consecutive_days=row.consecutive_days or 0,
            created_at=row.created_at.isoformat() if row.created_at else "",
            last_practiced_at=activity.get(row.id, (0, None))[1],
            practice_count=activity.get(row.id, (0, None))[0],
        )
        for row in rows
    ]
    return AdminUserListPage(total=total or 0, items=items)


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == ADMIN_ROLE)) or 0


def create_user(
    db: Session, admin: User, payload: AdminCreateUserRequest, request: Request | None = None
) -> User:
    """管理端代建用户。"""
    if get_user_by_username(db, payload.username):
        raise AdminError("用户名已被注册", status_code=409)
    if len(payload.username.strip()) < 3:
        raise AdminError("用户名至少 3 个字符")

    user = create_core_user(db, payload.username.strip(), payload.password)
    user.role = payload.role
    audit_service.record(
        db,
        actor=admin,
        action="user.create",
        target_type="user",
        target_id=user.id,
        detail={"username": user.username, "role": user.role},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    admin: User,
    user_id: int,
    payload: AdminUpdateUserRequest,
    request: Request | None = None,
) -> User:
    """启用 / 封禁 / 调整角色。"""
    target = db.get(User, user_id)
    if target is None:
        raise AdminError("用户不存在", status_code=404)
    if payload.role is None and payload.status is None:
        raise AdminError("没有需要更新的字段", status_code=400)

    # 先判「最后一个管理员」再判「不能对自己」：两条都指向同一件事——
    # 别把自己锁在门外——但 409 会告诉调用方真正的原因和解决办法。
    would_demote = (
        payload.role is not None
        and target.role == ADMIN_ROLE
        and payload.role != ADMIN_ROLE
    )
    would_ban = (
        payload.status is not None
        and target.role == ADMIN_ROLE
        and payload.status != USER_STATUS_ACTIVE
    )
    if (would_demote or would_ban) and _admin_count(db) <= 1:
        raise AdminError("系统必须保留至少一个管理员", status_code=409)

    if target.id == admin.id:
        raise AdminError("不能对自己执行该操作", status_code=400)

    changes: dict[str, str] = {}
    if payload.role is not None and payload.role != target.role:
        changes["role"] = f"{target.role} -> {payload.role}"
        target.role = payload.role

    if payload.status is not None and payload.status != target.status:
        action = (
            "user.unban" if payload.status == USER_STATUS_ACTIVE else "user.ban"
        )
        changes["status"] = f"{target.status} -> {payload.status}"
        target.status = payload.status
        audit_service.record(
            db,
            actor=admin,
            action=action,
            target_type="user",
            target_id=target.id,
            detail={"username": target.username, **changes},
            affected_rows=1,
            request=request,
        )

    if "role" in changes:
        audit_service.record(
            db,
            actor=admin,
            action="user.role_change",
            target_type="user",
            target_id=target.id,
            detail={"username": target.username, **changes},
            affected_rows=1,
            request=request,
        )

    db.commit()
    db.refresh(target)
    return target


def remove_user(
    db: Session, admin: User, user_id: int, request: Request | None = None
) -> int:
    """删除用户，返回连带删除的行数（词状态 + 练习会话 + 对话）。"""
    target = db.get(User, user_id)
    if target is None:
        raise AdminError("用户不存在", status_code=404)
    if target.id == admin.id:
        raise AdminError("不能删除自己", status_code=400)
    if target.role == ADMIN_ROLE and _admin_count(db) <= 1:
        raise AdminError("系统必须保留至少一个管理员", status_code=409)

    # 外键是 ON DELETE CASCADE，这里先算出影响面再删，审计才能如实记录
    def _count(model) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(model).where(model.user_id == target.id)
            )
            or 0
        )

    affected = _count(UserWordRecord) + _count(PracticeSessionRecord) + _count(ChatMessage)

    audit_service.record(
        db,
        actor=admin,
        action="user.delete",
        target_type="user",
        target_id=target.id,
        detail={
            "username": target.username,
            "is_guest": target.is_guest,
            "role": target.role,
        },
        affected_rows=affected,
        request=request,
    )
    db.delete(target)
    db.commit()
    return affected
