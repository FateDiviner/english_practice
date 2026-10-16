"""学习数据备份路由：导出与导入。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from core.db import get_db
from core.models.user import User
from app.schemas.backup import BACKUP_FORMAT, BACKUP_VERSION, BackupFile, ImportResult
from app.services import backup_service

router = APIRouter(prefix="/api/user", tags=["user"])

# 备份文件大小上限：词记录与会话上限各 2000 条，正常文件远小于此值
MAX_IMPORT_BYTES = 2 * 1024 * 1024


@router.get("/export", response_model=BackupFile)
def export_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BackupFile:
    """导出当前账号的全部学习数据，文件不含任何账号标识。"""
    return backup_service.export_backup(db, user)


@router.post("/import", response_model=ImportResult)
async def import_data(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportResult:
    """把一份备份合并进当前账号。合并而非覆盖，与游客转正同语义。"""
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="备份文件过大，最大 2MB")

    try:
        payload = BackupFile.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="备份文件格式不正确，请确认文件完整未损坏"
        ) from exc

    if payload.format != BACKUP_FORMAT:
        raise HTTPException(
            status_code=422,
            detail="不是本平台的学习数据备份文件",
        )
    if payload.version != BACKUP_VERSION:
        raise HTTPException(
            status_code=422,
            detail=f"备份版本 {payload.version} 不受支持，请用当前版本重新导出",
        )

    try:
        return backup_service.import_backup(db, user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="备份文件校验未通过") from exc
