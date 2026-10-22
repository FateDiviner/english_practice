from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.schemas.common import ApiResponse
from app.schemas.word import (
    WordCreateIn,
    WordDeleteOut,
    WordListItem,
    WordListOut,
    WordOut,
    WordUpdateIn,
)
from app.services.word import create_word, delete_word, list_words, update_word

router = APIRouter(
    prefix="/admin",
    tags=["admin-words"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "/wordbooks/{wordbook_id}/words",
    response_model=ApiResponse[WordOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_word_endpoint(
    wordbook_id: int,
    payload: WordCreateIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordOut]:
    """在指定词书中创建单词。"""
    word = await create_word(session, wordbook_id, payload)
    return ApiResponse[WordOut](code=0, message="ok", data=WordOut.model_validate(word))


@router.put("/words/{word_id}", response_model=ApiResponse[WordOut])
async def update_word_endpoint(
    word_id: int,
    payload: WordUpdateIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordOut]:
    """更新单词字段。"""
    word = await update_word(session, word_id, payload)
    return ApiResponse[WordOut](code=0, message="ok", data=WordOut.model_validate(word))


@router.delete("/words/{word_id}", response_model=ApiResponse[WordDeleteOut])
async def delete_word_endpoint(
    word_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordDeleteOut]:
    """删除单个单词。"""
    await delete_word(session, word_id)
    return ApiResponse[WordDeleteOut](
        code=0,
        message="ok",
        data=WordDeleteOut(deleted=True),
    )


@router.get(
    "/wordbooks/{wordbook_id}/words",
    response_model=ApiResponse[WordListOut],
)
async def list_words_endpoint(
    wordbook_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
) -> ApiResponse[WordListOut]:
    """按词书分页查询，支持 spelling 关键字模糊搜索。"""
    items, total = await list_words(
        session,
        wordbook_id=wordbook_id,
        page=page,
        page_size=page_size,
        keyword=keyword.strip() if keyword else None,
    )
    return ApiResponse[WordListOut](
        code=0,
        message="ok",
        data=WordListOut(
            items=[WordListItem.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )
