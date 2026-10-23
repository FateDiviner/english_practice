from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_BAD_REQUEST,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.core.security import hash_password
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.user import User
from app.services.stats import OverviewResult, get_overview


async def list_users(
    session: AsyncSession,
    page: int,
    page_size: int,
    keyword: str | None,
    status: Literal["active", "disabled"] | None,
) -> tuple[list[tuple[User, int]], int]:
    """分页查询用户，并用聚合子查询一次取得每人累计练习量。"""
    conditions = []
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(User.username.like(pattern), User.email.like(pattern)))
    if status:
        conditions.append(User.status == status)

    practice_counts = (
        select(
            PracticeSession.user_id.label("user_id"),
            func.count(PracticeRecord.id).label("total_practiced"),
        )
        .join(PracticeRecord, PracticeRecord.session_id == PracticeSession.id)
        .group_by(PracticeSession.user_id)
        .subquery()
    )
    rows = await session.execute(
        select(User, func.coalesce(practice_counts.c.total_practiced, 0))
        .outerjoin(practice_counts, practice_counts.c.user_id == User.id)
        .where(*conditions)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = await session.scalar(select(func.count(User.id)).where(*conditions)) or 0
    return [(user, int(total_practiced)) for user, total_practiced in rows], int(total)


async def _require_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "用户不存在")
    return user


async def update_user_status(
    session: AsyncSession,
    admin_id: int,
    target_user_id: int,
    status: Literal["active", "disabled"],
) -> User:
    """更新用户状态；管理员不能禁用自己。"""
    if admin_id == target_user_id and status == "disabled":
        raise AppError(400, ERROR_CODE_BAD_REQUEST, "不能禁用自己")
    user = await _require_user(session, target_user_id)
    user.status = status
    await session.commit()
    await session.refresh(user)
    return user


async def reset_password(
    session: AsyncSession,
    _admin_id: int,
    target_user_id: int,
    new_password: str,
) -> None:
    """由管理员为用户重置密码，并保存 bcrypt 哈希。"""
    if len(new_password) < 8:
        raise AppError(422, ERROR_CODE_VALIDATION, "密码长度不能少于 8 位")
    user = await _require_user(session, target_user_id)
    try:
        user.password_hash = hash_password(new_password)
    except ValueError as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "密码长度超过限制") from exc
    await session.commit()


async def get_user_stats(session: AsyncSession, target_user_id: int) -> OverviewResult:
    """复用个人统计逻辑返回指定用户的学习概览。"""
    await _require_user(session, target_user_id)
    return await get_overview(session, target_user_id)
