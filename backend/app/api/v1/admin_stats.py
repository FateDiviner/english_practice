from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin_stats import AdminOverviewOut
from app.schemas.common import ApiResponse
from app.services.admin_stats import get_admin_overview

router = APIRouter(
    prefix="/admin",
    tags=["admin-stats"],
    dependencies=[Depends(require_admin)],
)


@router.get("/overview", response_model=ApiResponse[AdminOverviewOut])
async def get_admin_overview_endpoint(
    _current_user: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[AdminOverviewOut]:
    """返回管理员数据概览。"""
    data = await get_admin_overview(session)
    return ApiResponse[AdminOverviewOut](
        code=0,
        message="ok",
        data=AdminOverviewOut(**data),
    )
