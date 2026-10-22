from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_UNAUTHENTICATED,
    AppError,
)
from app.core.security import TokenDecodeError, decode_access_token
from app.db.session import get_session
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """解析 Bearer Token，并从数据库读取当前有效用户。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "未登录或登录已过期")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError, TokenDecodeError) as exc:
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "未登录或登录已过期") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "未登录或登录已过期")

    if user.status != "active":
        raise AppError(403, ERROR_CODE_FORBIDDEN, "账号已被禁用")

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """只允许管理员访问受保护的管理端接口。"""
    if current_user.role != "admin":
        raise AppError(403, ERROR_CODE_FORBIDDEN, "无管理员权限")

    return current_user
