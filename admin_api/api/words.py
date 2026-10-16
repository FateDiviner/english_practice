"""管理端词库路由：词书、词条、批量导入与导出。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from admin_api.schemas.words import (
    ImportResult,
    WordAdminOut,
    WordPage,
    WordbookAdminOut,
    WordbookUpdateRequest,
    WordbookUpsertRequest,
    WordUpsertRequest,
)
from admin_api.services import AdminError
from admin_api.services.word_admin_service import (
    create_word,
    create_wordbook,
    export_book,
    import_books,
    list_wordbooks,
    list_words,
    purge_word,
    set_word_status,
    to_word_out,
    to_wordbook_out,
    update_word,
    update_wordbook,
)
from core.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from core.db import get_db
from core.deps import require_admin
from core.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin-words"])

# 导入文件体积上限：一本 5000 词的书约 1.5MB 文本
MAX_IMPORT_BYTES = 2 * 1024 * 1024


def _guard(fn, *args, **kwargs):
    """把管理端业务错误统一转成 HTTP 响应。"""
    try:
        return fn(*args, **kwargs)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# --------------------------- 词书 ---------------------------


@router.get("/wordbooks", response_model=list[WordbookAdminOut])
def wordbooks(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """全部词书，含已下架的——管理端要看得见自己下架过什么。"""
    return list_wordbooks(db)


@router.post("/wordbooks", response_model=WordbookAdminOut)
def create_book(
    payload: WordbookUpsertRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    book = _guard(create_wordbook, db, admin, payload, request)
    return to_wordbook_out(db, book)


@router.patch("/wordbooks/{book_id}", response_model=WordbookAdminOut)
def update_book(
    book_id: int,
    payload: WordbookUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    book = _guard(update_wordbook, db, admin, book_id, payload, request)
    return to_wordbook_out(db, book)


# --------------------------- 导入 / 导出 ---------------------------


@router.post("/wordbooks/import", response_model=ImportResult)
async def import_route(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportResult:
    """批量导入：先校验，任一条不通过则整批不写库。"""
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="导入文件过大，最大 2MB")

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="导入文件不是有效 JSON") from exc

    result = _guard(import_books, db, admin, payload, request)
    if not result.applied:
        # 校验失败：一条都没写，issues 直接告诉使用者错在第几条哪个词
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"导入文件校验未通过，共 {len(result.issues)} 处问题，未写入任何数据"
                ),
                "issues": [issue.model_dump() for issue in result.issues],
            },
        )
    return result


@router.get("/wordbooks/{book_id}/export")
def export_route(
    book_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """导出为 data/*.json 同构结构，可写回仓库做版本管理。"""
    return _guard(export_book, db, book_id)


# --------------------------- 词条 ---------------------------


@router.get("/wordbooks/{book_id}/words", response_model=WordPage)
def words(
    book_id: int,
    search: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, pattern="^(active|archived)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordPage:
    return _guard(
        list_words, db, book_id, search=search, status=status, limit=limit, offset=offset
    )


@router.post("/wordbooks/{book_id}/words", response_model=WordAdminOut)
def create_word_route(
    book_id: int,
    payload: WordUpsertRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordAdminOut:
    word = _guard(create_word, db, admin, book_id, payload, request)
    return to_word_out(word)


@router.patch("/words/{word_id}", response_model=WordAdminOut)
def update_word_route(
    word_id: int,
    payload: WordUpsertRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordAdminOut:
    word = _guard(update_word, db, admin, word_id, payload, request)
    return to_word_out(word)


@router.put("/words/{word_id}/status", response_model=WordAdminOut)
def set_status_route(
    word_id: int,
    status: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordAdminOut:
    """上架 / 下架单个词条（软删除）。"""
    if status not in (STATUS_ACTIVE, STATUS_ARCHIVED):
        raise HTTPException(status_code=422, detail="status 只能是 active 或 archived")
    word = _guard(set_word_status, db, admin, word_id, status, request)
    return to_word_out(word)


@router.delete("/words/{word_id}")
def purge_route(
    word_id: int,
    request: Request,
    purge: bool = Query(default=False, description="true 表示物理删除，仅零引用时允许"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """默认下架；仅在零用户引用时才允许物理删除。"""
    if not purge:
        _guard(set_word_status, db, admin, word_id, STATUS_ARCHIVED, request)
        return {"archived": True}

    _guard(purge_word, db, admin, word_id, request)
    return {"purged": True}
