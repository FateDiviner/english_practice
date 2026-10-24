from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.word import UserWordItem, UserWordListOut
from app.schemas.wordbook import (
    UserWordbookDetail,
    UserWordbookItem,
    UserWordbookListOut,
    UserWordbookProgress,
)
from app.services.wordbook import (
    get_published_wordbook_detail,
    list_published_wordbooks,
    list_published_words,
)

router = APIRouter(
    prefix="/wordbooks",
    tags=["wordbooks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ApiResponse[UserWordbookListOut])
async def list_wordbooks_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[UserWordbookListOut]:
    """分页返回所有 published 词书及当前用户的学习进度。"""
    rows, total = await list_published_wordbooks(session, page, page_size, current_user.id)
    items = [
        UserWordbookItem(
            id=wordbook.id,
            name=wordbook.name,
            description=wordbook.description,
            level=wordbook.level,
            word_count=word_count,
            my_progress=UserWordbookProgress(mastered=mastered_count, total=word_count),
        )
        for wordbook, word_count, mastered_count in rows
    ]
    return ApiResponse[UserWordbookListOut](
        code=0,
        message="ok",
        data=UserWordbookListOut(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/{wordbook_id}", response_model=ApiResponse[UserWordbookDetail])
async def get_wordbook_endpoint(
    wordbook_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[UserWordbookDetail]:
    """返回 published 词书详情；draft/archived 按不存在处理。"""
    wordbook, word_count = await get_published_wordbook_detail(session, wordbook_id)
    return ApiResponse[UserWordbookDetail](
        code=0,
        message="ok",
        data=UserWordbookDetail(
            id=wordbook.id,
            name=wordbook.name,
            description=wordbook.description,
            level=wordbook.level,
            word_count=word_count,
        ),
    )


@router.get("/{wordbook_id}/words", response_model=ApiResponse[UserWordListOut])
async def list_wordbook_words_endpoint(
    wordbook_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    mastery: Annotated[int | None, Query(ge=0, le=2)] = None,
) -> ApiResponse[UserWordListOut]:
    """分页返回 published 词书单词及当前用户的掌握度。"""
    words, total = await list_published_words(
        session,
        wordbook_id=wordbook_id,
        page=page,
        page_size=page_size,
        user_id=current_user.id,
        mastery=mastery,
    )
    return ApiResponse[UserWordListOut](
        code=0,
        message="ok",
        data=UserWordListOut(
            items=[
                UserWordItem(
                    id=word.id,
                    spelling=word.spelling,
                    phonetic_uk=word.phonetic_uk,
                    phonetic_us=word.phonetic_us,
                    meaning_cn=word.meaning_cn,
                    part_of_speech=word.part_of_speech,
                    audio_url=word.audio_url,
                    mastery_level=mastery_level,
                )
                for word, mastery_level in words
            ],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )
