"""管理端认证路由：管理员注册、登录与身份查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from admin_api.schemas.auth import (
    AdminAuthResponse,
    AdminLoginRequest,
    AdminRegisterRequest,
    AdminUserOut,
)
from admin_api.services.admin_auth_service import register_admin
from admin_api.services.user_admin_service import to_admin_user
from core.db import get_db
from core.deps import get_current_user
from core.models.user import User
from core.services.auth_service import AuthError, issue_token, login as core_login

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


@router.post("/register", response_model=AdminAuthResponse)
def register(payload: AdminRegisterRequest, db: Session = Depends(get_db)) -> AdminAuthResponse:
    """注册管理员。

    配置了 ADMIN_INVITE_CODE 时必须提供该码；未配置时退化为「首个管理员」规则——
    系统里已存在管理员就不再放行，避免注册接口变成抢注管理员的入口。
    """
    try:
        user = register_admin(db, payload.username, payload.password, payload.invite_code)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return AdminAuthResponse(access_token=issue_token(user), user=to_admin_user(user, db))


@router.post("/login", response_model=AdminAuthResponse)
def login(
    payload: AdminLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminAuthResponse:
    """管理端登录。被封禁的账号在这里就会被拒。"""
    guest_header = (request.headers.get("X-Guest-Id") or "").strip()
    guest_id = int(guest_header) if guest_header.isdigit() else None
    try:
        user = core_login(db, payload.username, payload.password, guest_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return AdminAuthResponse(access_token=issue_token(user), user=to_admin_user(user, db))


@router.get("/me", response_model=AdminUserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminUserOut:
    """当前登录身份，前端据此决定是否放行管理页面。"""
    return to_admin_user(user, db)
