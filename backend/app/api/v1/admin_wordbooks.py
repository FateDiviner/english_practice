from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.wordbook import (
    WordbookCreateIn,
    WordbookDeleteOut,
    WordbookListItem,
    WordbookListOut,
    WordbookOut,
    WordbookUpdateIn,
)
from app.services.wordbook import (
    create_wordbook,
    delete_wordbook,
    list_wordbooks,
    update_wordbook,
)

router = APIRouter(
    prefix="/admin/wordbooks",
    tags=["admin-wordbooks"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "",
    response_model=ApiResponse[WordbookOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_wordbook_endpoint(
    payload: WordbookCreateIn,
    current_user: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordbookOut]:
    """创建词书。"""
    wordbook = await create_wordbook(session, payload, current_user.id)
    return ApiResponse[WordbookOut](
        code=0,
        message="ok",
        data=WordbookOut.model_validate(wordbook),
    )


@router.put("/{wordbook_id}", response_model=ApiResponse[WordbookOut])
async def update_wordbook_endpoint(
    wordbook_id: int,
    payload: WordbookUpdateIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordbookOut]:
    """更新词书字段。"""
    wordbook = await update_wordbook(session, wordbook_id, payload)
    return ApiResponse[WordbookOut](
        code=0,
        message="ok",
        data=WordbookOut.model_validate(wordbook),
    )


@router.delete("/{wordbook_id}", response_model=ApiResponse[WordbookDeleteOut])
async def delete_wordbook_endpoint(
    wordbook_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[WordbookDeleteOut]:
    """删除空词书；存在单词时返回冲突，不做级联删除。"""
    await delete_wordbook(session, wordbook_id)
    return ApiResponse[WordbookDeleteOut](
        code=0, message="ok", data=WordbookDeleteOut(deleted=True)
    )


@router.get("", response_model=ApiResponse[WordbookListOut])
async def list_wordbooks_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[WordbookListOut]:
    """分页返回词书及每本词书的单词数。"""
    rows, total = await list_wordbooks(session, page=page, page_size=page_size)
    items = [
        WordbookListItem(
            id=wordbook.id,
            name=wordbook.name,
            description=wordbook.description,
            level=wordbook.level,
            status=wordbook.status,
            created_by=wordbook.created_by,
            word_count=word_count,
            created_at=wordbook.created_at,
            updated_at=wordbook.updated_at,
        )
        for wordbook, word_count in rows
    ]
    return ApiResponse[WordbookListOut](
        code=0,
        message="ok",
        data=WordbookListOut(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )
