from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.practice import (
    AnswerIn,
    AnswerOut,
    QuestionHintOut,
    QuestionOut,
    SessionCreateIn,
    SessionCreateOut,
)
from app.services.practice import answer_question, create_session

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


@router.post(
    "/sessions/{session_id}/answer",
    response_model=ApiResponse[AnswerOut],
    response_model_exclude_none=True,
)
async def answer_question_endpoint(
    session_id: int,
    payload: AnswerIn,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[AnswerOut]:
    """提交单题答案；重复提交返回首次结果，不重复计分。"""
    result = await answer_question(
        session=session,
        user_id=current_user.id,
        session_id=session_id,
        word_id=payload.word_id,
        user_input=payload.user_input,
        used_hint=payload.used_hint,
    )
    return ApiResponse[AnswerOut](
        code=0,
        message="ok",
        data=AnswerOut(
            is_correct=result.is_correct,
            mastery_level=result.mastery_level,
            correct_spelling=result.correct_spelling,
            example_en=result.example_en,
            example_cn=result.example_cn,
        ),
    )
