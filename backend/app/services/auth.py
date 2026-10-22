from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_CONFLICT,
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_UNAUTHENTICATED,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """按主键查询用户。"""
    return await session.get(User, user_id)


async def get_user_by_account(session: AsyncSession, account: str) -> User | None:
    """按 username 优先、email 其次查询登录账号。"""
    user = await session.scalar(select(User).where(User.username == account))
    if user is not None:
        return user

    return await session.scalar(select(User).where(User.email == account))


async def _has_identity_conflict(
    session: AsyncSession,
    username: str,
    email: str,
) -> bool:
    """检查 username/email 是否与已有用户任一登录身份冲突。"""
    identity_values = (username, email)
    user_id = await session.scalar(
        select(User.id)
        .where(
            or_(
                User.username.in_(identity_values),
                User.email.in_(identity_values),
            ),
        )
        .limit(1),
    )
    return user_id is not None


async def register_user(
    session: AsyncSession,
    username: str,
    email: str,
    password: str,
) -> User:
    """注册普通用户；任何唯一身份冲突都返回 40901。"""
    if await _has_identity_conflict(session, username, email):
        raise AppError(409, ERROR_CODE_CONFLICT, "用户名或邮箱已存在")

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "密码长度超过限制") from exc

    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        role="user",
        status="active",
    )
    session.add(user)

    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, ERROR_CODE_CONFLICT, "用户名或邮箱已存在") from exc

    return user


async def authenticate_user(session: AsyncSession, account: str, password: str) -> User:
    """校验登录凭据；密码错误返回 401，禁用账号返回 403。"""
    user = await get_user_by_account(session, account)
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "账号或密码错误")

    if user.status != "active":
        raise AppError(403, ERROR_CODE_FORBIDDEN, "账号已被禁用")

    return user
