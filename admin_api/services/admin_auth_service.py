"""管理端注册：邀请码与「首个管理员」规则。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models.user import User
from core.services.auth_service import (
    AuthError,
    create_user,
    get_user_by_username,
)

ADMIN_ROLE = "admin"


def register_admin(db: Session, username: str, password: str, invite_code: str | None) -> User:
    """创建一个管理员账号。

    两条硬约束，任一不满足都拒绝：
    1. 配置了 ADMIN_INVITE_CODE -> 必须提供且匹配；
    2. 未配置 -> 系统里已经存在管理员就拒绝，只能由现有管理员代建。
    """
    configured = (get_settings().admin_invite_code or "").strip()

    if configured:
        if not invite_code or invite_code.strip() != configured:
            raise AuthError("邀请码不正确", status_code=403)
    else:
        existing = db.scalar(select(User.id).where(User.role == ADMIN_ROLE).limit(1))
        if existing is not None:
            raise AuthError(
                "系统已有管理员，请让现有管理员在管理端为你创建账号",
                status_code=409,
            )

    if get_user_by_username(db, username):
        raise AuthError("用户名已被注册", status_code=409)
    if len(username.strip()) < 3:
        raise AuthError("用户名至少 3 个字符")

    user = create_user(db, username.strip(), password)
    user.role = ADMIN_ROLE
    db.commit()
    db.refresh(user)
    return user
