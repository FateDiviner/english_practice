from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.schemas.admin_profile import UserProfileOut
from app.schemas.common import ApiResponse
from app.services.profile.service import ProfileOrchestrator, get_profile_orchestrator

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_admin)],
)


@router.post("/{user_id}/profile", response_model=ApiResponse[UserProfileOut])
async def get_user_profile_endpoint(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    orchestrator: Annotated[ProfileOrchestrator, Depends(get_profile_orchestrator)],
) -> ApiResponse[UserProfileOut]:
    """按黑板顺序运行数据、习惯、诊断、规划四位专家并返回结构化画像。"""
    report = await orchestrator.analyze(session, user_id)
    return ApiResponse[UserProfileOut](code=0, message="ok", data=report)