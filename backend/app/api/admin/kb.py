"""管理端知识库路由：上传、列表、删除。

上传走 multipart，解析与切块同步完成（失败要当场报错），向量化留给
索引阶段异步做——否则一个大 PDF 会让上传请求挂十几秒。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models.user import User
from app.schemas.admin import KbDocumentOut
from app.services import kb_service
from app.services.admin_errors import AdminError

router = APIRouter(prefix="/api/admin/kb", tags=["admin-kb"])


def _guard(fn, *args, **kwargs):
    """把管理端业务错误统一转成 HTTP 响应。"""
    try:
        return fn(*args, **kwargs)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/formats")
def formats() -> dict:
    """前端上传控件的 accept 与提示文案取值，避免格式清单硬编码两处。"""
    return {
        "extensions": sorted(kb_service.SUPPORTED),
        "max_bytes": kb_service.settings.kb_max_upload_bytes,
    }


@router.get("/documents", response_model=list[KbDocumentOut])
def list_route(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[KbDocumentOut]:
    """全部文档，含失败的——失败要让人看得见原因，而不是凭空消失。"""
    return kb_service.list_documents(db)


@router.post("/documents", response_model=KbDocumentOut)
async def upload_route(
    request: Request,
    file: UploadFile = File(..., description="md / txt / pdf / docx"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> KbDocumentOut:
    """上传并解析一份资料。解析失败当场返回 422，不会静默入库空内容。"""
    data = await file.read()
    document = _guard(
        kb_service.create_document, db, admin, file.filename or "unnamed", data, request
    )
    return kb_service.to_document_out(document)


@router.delete("/documents/{document_id}")
def delete_route(
    document_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """删除文档，切块随级联清除。向量在索引阶段同步清掉。"""
    _guard(kb_service.delete_document, db, admin, document_id, request)
    return {"deleted": True}
