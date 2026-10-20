"""管理端词条关系路由。

与词库路由分开：关系边的生命周期与词书/词条不同，且检索侧（graph retriever）
会按词批量取邻居，值得单独一个模块。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models.relation import RELATIONS
from app.models.user import User
from app.schemas.admin import (
    WordRelationCreateRequest,
    WordRelationOut,
    WordRelationUpdateRequest,
)
from app.services import relation_service
from app.services.admin_errors import AdminError

router = APIRouter(prefix="/api/admin", tags=["admin-relations"])


def _guard(fn, *args, **kwargs):
    """把管理端业务错误统一转成 HTTP 响应。"""
    try:
        return fn(*args, **kwargs)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/relations/types")
def relation_types() -> dict:
    """前端下拉框用，避免把关系枚举硬编码在两处。"""
    return {"types": list(RELATIONS)}


@router.get("/words/{word_id}/relations", response_model=list[WordRelationOut])
def list_route(
    word_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[WordRelationOut]:
    """列出某个词条的全部关系边。"""
    return relation_service.list_relations(db, word_id)


@router.post("/words/{word_id}/relations", response_model=WordRelationOut)
def create_route(
    word_id: int,
    payload: WordRelationCreateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordRelationOut:
    """给词条加一条关系边。"""
    relation = _guard(relation_service.create_relation, db, admin, word_id, payload, request)
    return relation_service.to_relation_out(relation)


@router.patch("/relations/{relation_id}", response_model=WordRelationOut)
def update_route(
    relation_id: int,
    payload: WordRelationUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WordRelationOut:
    """编辑关系边。"""
    relation = _guard(
        relation_service.update_relation, db, admin, relation_id, payload, request
    )
    return relation_service.to_relation_out(relation)


@router.delete("/relations/{relation_id}")
def delete_route(
    relation_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """删除关系边。不影响用户的练习记录。"""
    _guard(relation_service.delete_relation, db, admin, relation_id, request)
    return {"deleted": True}
