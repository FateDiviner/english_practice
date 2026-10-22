from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.practice import QuestionHintOut, QuestionOut, SessionCreateIn, SessionCreateOut
from app.services.practice import create_session

router = APIRouter(
    prefix="/practice",
    tags=["practice"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/sessions", response_model=ApiResponse[SessionCreateOut])
async def create_session_endpoint(
    payload: SessionCreateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[SessionCreateOut]:
    """创建练习会话；响应绝不返回 spelling 或例句。"""
    practice_session, words, notice = await create_session(
        session=session,
        user_id=current_user.id,
        wordbook_id=payload.wordbook_id,
        mode=payload.mode,
        count=payload.count,
        strict_mode=payload.strict_mode,
    )
    questions = [
        QuestionOut(
            word_id=word.id,
            phonetic_uk=word.phonetic_uk,
            phonetic_us=word.phonetic_us,
            meaning_cn=word.meaning_cn,
            part_of_speech=word.part_of_speech,
            hint=QuestionHintOut(length=len(word.spelling)),
        )
        for word in words
    ]
    return ApiResponse[SessionCreateOut](
        code=0,
        message="ok",
        data=SessionCreateOut(
            session_id=practice_session.id,
            total=len(questions),
            questions=questions,
            notice=notice,
        ),
    )
