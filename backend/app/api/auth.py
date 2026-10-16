"""认证路由：注册、登录、游客体验与数据迁移。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from core.db import get_db
from core.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserInfo
from core.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _guest_id_from_request(request: Request) -> int | None:
    """从请求头读取游客令牌，用于登录 / 注册后自动迁移数据。"""
    raw = request.headers.get("X-Guest-Id", "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=auth_service.issue_token(user),
        user=UserInfo.model_validate(user),
        migrated=bool(user.__dict__.get("migrated", False)),
    )


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """注册正式账号；若携带游客身份则自动迁移历史进度。"""
    guest_id = _guest_id_from_request(request)
    try:
        user = auth_service.register(db, payload.username, payload.password, guest_id)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """账号密码登录；若当前为游客会话则自动迁移历史进度。"""
    guest_id = _guest_id_from_request(request)
    try:
        user = auth_service.login(db, payload.username, payload.password, guest_id)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _auth_response(user)


@router.post("/guest", response_model=AuthResponse)
def guest(db: Session = Depends(get_db)) -> AuthResponse:
    """一键游客体验：立即创建临时账号并签发令牌。"""
    user = auth_service.create_guest(db)
    return _auth_response(user)


@router.get("/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user)) -> UserInfo:
    """获取当前登录用户信息。"""
    return UserInfo.model_validate(user)
