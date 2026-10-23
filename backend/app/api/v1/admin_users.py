from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin_user import (
    AdminUserItem,
    AdminUserListOut,
    ResetPasswordIn,
    ResetPasswordOut,
    UserStatsOut,
    UserStatusIn,
    UserStatusOut,
)
from app.schemas.common import ApiResponse
from app.services.admin_user import (
    get_user_stats,
    list_users,
    reset_password,
    update_user_status,
)

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=ApiResponse[AdminUserListOut])
async def list_users_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    status: Annotated[Literal["active", "disabled"] | None, Query()] = None,
) -> ApiResponse[AdminUserListOut]:
    """分页返回用户，支持用户名/邮箱搜索和状态筛选。"""
    rows, total = await list_users(
        session,
        page=page,
        page_size=page_size,
        keyword=keyword.strip() if keyword else None,
        status=status,
    )
    return ApiResponse[AdminUserListOut](
        code=0,
        message="ok",
        data=AdminUserListOut(
            items=[
                AdminUserItem(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    role=user.role,
                    status=user.status,
                    created_at=user.created_at,
                    total_practiced=total_practiced,
                )
                for user, total_practiced in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.patch("/{user_id}/status", response_model=ApiResponse[UserStatusOut])
async def update_user_status_endpoint(
    user_id: int,
    payload: UserStatusIn,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[UserStatusOut]:
    """启用或禁用用户。"""
    user = await update_user_status(session, current_admin.id, user_id, payload.status)
    return ApiResponse[UserStatusOut](
        code=0,
        message="ok",
        data=UserStatusOut(id=user.id, status=user.status),
    )


@router.post("/{user_id}/reset-password", response_model=ApiResponse[ResetPasswordOut])
async def reset_password_endpoint(
    user_id: int,
    payload: ResetPasswordIn,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[ResetPasswordOut]:
    """管理员重置指定用户密码。"""
    await reset_password(session, current_admin.id, user_id, payload.new_password)
    return ApiResponse[ResetPasswordOut](
        code=0,
        message="ok",
        data=ResetPasswordOut(reset=True),
    )


@router.get("/{user_id}/stats", response_model=ApiResponse[UserStatsOut])
async def get_user_stats_endpoint(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[UserStatsOut]:
    """返回指定用户的学习概览。"""
    result = await get_user_stats(session, user_id)
    return ApiResponse[UserStatsOut](
        code=0,
        message="ok",
        data=UserStatsOut(
            total_practiced=result.total_practiced,
            accuracy=result.accuracy,
            streak_days=result.streak_days,
            mastered_words=result.mastered_words,
            wrong_words_count=result.wrong_words_count,
        ),
    )
