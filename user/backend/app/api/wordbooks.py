"""词书中心路由：列表、进度统计与激活词书。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_current_user
from core.db import get_db
from core.models.user import User
from core.constants import STATUS_ACTIVE
from core.models.wordbook import WordBook
from app.schemas.word import WordBookOut, WordBookProgress
from app.services import scheduler

router = APIRouter(prefix="/api/wordbooks", tags=["wordbooks"])


@router.get("", response_model=list[WordBookOut])
def list_wordbooks(db: Session = Depends(get_db)) -> list[WordBookOut]:
    """列出全部内置官方词书。"""
    # 下架词书对用户完全不可见
    rows = db.scalars(
        select(WordBook)
        .where(WordBook.status == STATUS_ACTIVE)
        .order_by(WordBook.id)
    ).all()
    return [WordBookOut.model_validate(row) for row in rows]


@router.get("/{wordbook_id}/progress", response_model=WordBookProgress)
def wordbook_progress(
    wordbook_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordBookProgress:
    """统计当前用户在某词书上的学习进度。"""
    if db.get(WordBook, wordbook_id) is None:
        raise HTTPException(status_code=404, detail="词书不存在")
    stats = scheduler.compute_progress(db, _user.id, wordbook_id)
    return WordBookProgress(**stats)


@router.post("/{wordbook_id}/activate", response_model=WordBookOut)
def activate_wordbook(
    wordbook_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordBookOut:
    """切换当前正在激活练习的词书。"""
    book = db.get(WordBook, wordbook_id)
    if book is None:
        raise HTTPException(status_code=404, detail="词书不存在")
    if book.status != STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="该词书已下架，无法激活")
    user.active_wordbook_id = book.id
    db.commit()
    db.refresh(user)
    return WordBookOut.model_validate(book)
