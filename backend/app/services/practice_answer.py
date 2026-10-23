from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_BAD_REQUEST,
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_NOT_FOUND,
    AppError,
)
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord
from app.services.grading import CONSECUTIVE_CORRECT_TO_MASTER, is_correct_answer


@dataclass(frozen=True)
class AnswerResult:
    is_correct: bool
    mastery_level: int
    correct_spelling: str | None
    example_en: str | None
    example_cn: str | None


def _build_answer_result(
    is_correct: bool,
    mastery_level: int,
    word: Word | None,
) -> AnswerResult:
    if is_correct or word is None:
        return AnswerResult(
            is_correct=is_correct,
            mastery_level=mastery_level,
            correct_spelling=None,
            example_en=None,
            example_cn=None,
        )

    return AnswerResult(
        is_correct=False,
        mastery_level=mastery_level,
        correct_spelling=word.spelling,
        example_en=word.example_en,
        example_cn=word.example_cn,
    )


async def _find_existing_answer(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    word_id: int,
) -> AnswerResult | None:
    record = await session.scalar(
        select(PracticeRecord).where(
            PracticeRecord.session_id == session_id,
            PracticeRecord.word_id == word_id,
        ),
    )
    if record is None:
        return None

    word = await session.get(Word, word_id)
    progress = await session.scalar(
        select(WordProgress).where(
            WordProgress.user_id == user_id,
            WordProgress.word_id == word_id,
        ),
    )
    mastery_level = progress.mastery_level if progress is not None else 0
    return _build_answer_result(record.is_correct, mastery_level, word)


async def answer_question(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    word_id: int,
    user_input: str,
    used_hint: bool,
) -> AnswerResult:
    """处理单题作答，重复提交直接返回首次结果。"""
    practice_session = await session.scalar(
        select(PracticeSession).where(PracticeSession.id == session_id).with_for_update(),
    )
    if practice_session is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "练习会话不存在")
    if practice_session.user_id != user_id:
        raise AppError(403, ERROR_CODE_FORBIDDEN, "无权访问该练习会话")
    if practice_session.status != "ongoing":
        raise AppError(400, ERROR_CODE_BAD_REQUEST, "练习会话已结束")

    existing_result = await _find_existing_answer(session, user_id, session_id, word_id)
    if existing_result is not None:
        return existing_result

    session_question = await session.scalar(
        select(SessionQuestion.id).where(
            SessionQuestion.session_id == session_id,
            SessionQuestion.word_id == word_id,
        ),
    )
    if session_question is None:
        raise AppError(400, ERROR_CODE_BAD_REQUEST, "单词不属于当前练习会话")

    word = await session.get(Word, word_id)
    if word is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "单词不存在")

    is_correct = is_correct_answer(
        user_input,
        word.spelling,
        strict_mode=practice_session.strict_mode,
    )
    progress = await session.scalar(
        select(WordProgress)
        .where(
            WordProgress.user_id == user_id,
            WordProgress.word_id == word_id,
        )
        .with_for_update(),
    )
    if progress is None:
        progress = WordProgress(
            user_id=user_id,
            word_id=word_id,
            mastery_level=0,
            correct_count=0,
            wrong_count=0,
            consecutive_correct=0,
        )
        session.add(progress)

    now = datetime.now(UTC).replace(tzinfo=None)
    if is_correct:
        progress.correct_count += 1
        progress.consecutive_correct += 1
        progress.last_result = "correct"
        if progress.consecutive_correct >= CONSECUTIVE_CORRECT_TO_MASTER:
            progress.mastery_level = 2
        practice_session.correct_count += 1
    else:
        progress.wrong_count += 1
        progress.consecutive_correct = 0
        progress.last_result = "wrong"
        progress.mastery_level = 1

        wrong_word = await session.scalar(
            select(WrongWord)
            .where(
                WrongWord.user_id == user_id,
                WrongWord.word_id == word_id,
            )
            .with_for_update(),
        )
        if wrong_word is None:
            session.add(
                WrongWord(
                    user_id=user_id,
                    word_id=word_id,
                    wrong_count=1,
                    last_wrong_at=now,
                    resolved=False,
                ),
            )
        else:
            wrong_word.wrong_count += 1
            wrong_word.last_wrong_at = now
            wrong_word.resolved = False
            wrong_word.resolved_at = None

    progress.last_practiced_at = now
    session.add(
        PracticeRecord(
            session_id=session_id,
            word_id=word_id,
            user_input=user_input,
            is_correct=is_correct,
            used_hint=used_hint,
        ),
    )
    mastery_level = progress.mastery_level

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate_result = await _find_existing_answer(
            session,
            user_id,
            session_id,
            word_id,
        )
        if duplicate_result is not None:
            return duplicate_result
        raise
    except Exception:
        await session.rollback()
        raise

    return _build_answer_result(is_correct, mastery_level, word)
