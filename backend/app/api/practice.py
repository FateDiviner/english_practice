"""默写练习路由：开场、提示、提交、结算与错题本。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from core.db import get_db
from core.models.user import User
from core.constants import STATUS_ACTIVE
from core.models.wordbook import WordBook
from app.schemas.practice import (
    HintRequest,
    HintResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    ReviewQueueResponse,
    SettlementResponse,
    SubmitRequest,
    SubmitResponse,
    WrongBookResponse,
)
from app.services import practice_service, scheduler

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _ensure_book(db: Session, wordbook_id: int) -> WordBook:
    book = db.get(WordBook, wordbook_id)
    if book is None:
        raise HTTPException(status_code=404, detail="词书不存在")
    # 已下架的词书不能再开局；进行中的会话不受影响，用户可以答完
    if book.status != STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="该词书已下架")
    return book


@router.post("/start", response_model=PracticeStartResponse)
def start(payload: PracticeStartRequest, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)) -> PracticeStartResponse:
    """开启一组默写练习。"""
    _ensure_book(db, payload.wordbook_id)
    try:
        return practice_service.start_session(
            db, user.id, payload.wordbook_id, payload.size, payload.mode
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "wrong_book":
            detail = "错题本为空，先去默写几组吧"
        elif reason == "review":
            detail = "暂无到期词，今天的复习任务已完成"
        else:
            detail = "该词书暂无单词"
        raise HTTPException(status_code=400, detail=detail) from exc


@router.post("/hint", response_model=HintResponse)
def hint(payload: HintRequest, user: User = Depends(get_current_user),
         db: Session = Depends(get_db)) -> HintResponse:
    """获取首字母提示（Tab 触发）。"""
    try:
        return practice_service.get_hint(db, user.id, payload.session_id, payload.word_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="会话或单词不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="无权访问该练习会话") from exc


@router.post("/submit", response_model=SubmitResponse)
def submit(payload: SubmitRequest, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> SubmitResponse:
    """提交一次拼写并即时校验。"""
    try:
        return practice_service.submit_answer(
            db,
            user.id,
            payload.session_id,
            payload.word_id,
            payload.answer,
            payload.skipped,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="会话或单词不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="无权访问该练习会话") from exc


@router.post("/finish", response_model=SettlementResponse)
def finish(session_id: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> SettlementResponse:
    """结算一组练习。"""
    try:
        return practice_service.finish_session(db, user.id, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="练习会话不存在或已过期") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="无权访问该练习会话") from exc


@router.get("/review-queue", response_model=ReviewQueueResponse)
def review_queue(
    wordbook_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    """统计某词书今日待复习的词，供词书中心入口展示。"""
    _ensure_book(db, wordbook_id)
    return ReviewQueueResponse(
        **scheduler.build_review_queue(db, user.id, wordbook_id)
    )


@router.get("/wrong-book", response_model=WrongBookResponse)
def wrong_book(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> WrongBookResponse:
    """查看错题本（生词本）。"""
    return practice_service.list_wrong_book(db, user.id)
