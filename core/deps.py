"""API 依赖注入：当前登录用户解析。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.db import get_db
from core.constants import USER_STATUS_ACTIVE
from core.models.user import User
from core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization 头解析 JWT 并加载用户。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效，请重新登录",
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证格式错误",
        ) from None

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号不存在或已被注销",
        )
    # 封禁即时生效：JWT 本身无状态，但每次请求都查库，状态一改旧令牌立刻作废
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁",
        )
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理端专用：仅管理员可通过。

    权限判定只在后端，前端隐藏入口不算权限；游客即使拿到令牌也永远是 403。
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
