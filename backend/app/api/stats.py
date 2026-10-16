"""学习看板路由：连续打卡、今日进度与近期趋势。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from core.db import get_db
from core.models.user import User
from app.schemas.stats import StatsOverview
from app.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
def overview(
    days: int = Query(default=7, ge=1, le=30, description="趋势展示天数"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsOverview:
    """学习看板概览：连续打卡、今日进度、近 N 天趋势与累计掌握。"""
    return StatsOverview(**stats_service.build_overview(db, user.id, days))
