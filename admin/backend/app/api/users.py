"""管理端用户管理路由：查询、新增、启用/封禁/改角色、删除。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.schemas.users import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AdminUserListPage,
)
from app.services.user_admin_service import (
    create_user as create_user_service,
    list_users,
    remove_user,
    update_user,
)
from core.deps import require_admin
from core.db import get_db
from core.models.user import User
from app.services import AdminError

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


@router.get("", response_model=AdminUserListPage)
def list_users_route(
    search: str | None = Query(default=None, max_length=64, description="按用户名模糊匹配"),
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    status: str | None = Query(default=None, pattern="^(active|banned)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserListPage:
    """分页查询用户。"""
    return list_users(db, search=search, role=role, status=status, limit=limit, offset=offset)


@router.post("", response_model=dict)
def create_user_route(
    payload: AdminCreateUserRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """管理端代建用户。"""
    try:
        user = create_user_service(db, admin, payload, request)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"id": user.id, "username": user.username, "role": user.role}


@router.patch("/{user_id}", response_model=dict)
def update_user_route(
    user_id: int,
    payload: AdminUpdateUserRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """启用 / 封禁 / 调整角色。"""
    try:
        user = update_user(db, admin, user_id, payload, request)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"id": user.id, "username": user.username, "role": user.role, "status": user.status}


@router.delete("/{user_id}", response_model=dict)
def delete_user_route(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """删除用户及其全部练习数据（外键级联）。"""
    try:
        affected = remove_user(db, admin, user_id, request)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"deleted": True, "affected_rows": affected}
