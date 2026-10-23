from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.stats import StatsDailyItem, StatsDailyOut, StatsOverviewOut
from app.services.stats import get_daily, get_overview

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/overview", response_model=ApiResponse[StatsOverviewOut])
async def get_overview_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[StatsOverviewOut]:
    """返回当前用户的累计练习概览。"""
    result = await get_overview(session, current_user.id)
    return ApiResponse[StatsOverviewOut](
        code=0,
        message="ok",
        data=StatsOverviewOut(
            total_practiced=result.total_practiced,
            accuracy=result.accuracy,
            streak_days=result.streak_days,
            mastered_words=result.mastered_words,
            wrong_words_count=result.wrong_words_count,
        ),
    )


@router.get("/daily", response_model=ApiResponse[StatsDailyOut])
async def get_daily_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> ApiResponse[StatsDailyOut]:
    """按 APP_TIMEZONE 自然日返回当前用户每日答题量。"""
    rows = await get_daily(session, current_user.id, date_from, date_to)
    return ApiResponse[StatsDailyOut](
        code=0,
        message="ok",
        data=StatsDailyOut(
            items=[
                StatsDailyItem(
                    date=row.date,
                    answered=row.answered,
                    correct=row.correct,
                )
                for row in rows
            ],
        ),
    )
