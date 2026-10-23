from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.wrong_word import (
    WrongWordItem,
    WrongWordListOut,
    WrongWordRemoveOut,
)
from app.services.wrong_word import list_wrong_words, remove_wrong_word

router = APIRouter(
    prefix="/wrong-words",
    tags=["wrong-words"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ApiResponse[WrongWordListOut])
async def list_wrong_words_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    resolved: bool = False,
) -> ApiResponse[WrongWordListOut]:
    """分页返回当前用户错词，默认筛选 resolved=false。"""
    rows, total = await list_wrong_words(
        session,
        current_user.id,
        page,
        page_size,
        resolved,
    )
    items = [
        WrongWordItem(
            word_id=word.id,
            spelling=word.spelling,
            phonetic_uk=word.phonetic_uk,
            phonetic_us=word.phonetic_us,
            meaning_cn=word.meaning_cn,
            wrong_count=wrong_word.wrong_count,
            last_wrong_at=wrong_word.last_wrong_at,
            resolved=wrong_word.resolved,
        )
        for wrong_word, word in rows
    ]
    return ApiResponse[WrongWordListOut](
        code=0,
        message="ok",
        data=WrongWordListOut(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.delete("/{word_id}", response_model=ApiResponse[WrongWordRemoveOut])
async def remove_wrong_word_endpoint(
    word_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WrongWordRemoveOut]:
    """移除当前用户自己的错词。"""
    await remove_wrong_word(session, current_user.id, word_id)
    return ApiResponse[WrongWordRemoveOut](
        code=0,
        message="ok",
        data=WrongWordRemoveOut(removed=True),
    )
