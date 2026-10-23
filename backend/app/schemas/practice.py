from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SessionCreateIn(BaseModel):
    wordbook_id: int | None = None
    mode: Literal["normal", "wrong_only"]
    count: Literal[10, 20, 50] = 20
    strict_mode: bool = True


class QuestionHintOut(BaseModel):
    length: int


class QuestionOut(BaseModel):
    word_id: int
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    audio_url: str | None
    hint: QuestionHintOut


class SessionCreateOut(BaseModel):
    session_id: int
    total: int
    questions: list[QuestionOut]
    notice: str | None = None


class AnswerIn(BaseModel):
    word_id: int
    user_input: str = Field(max_length=100)
    used_hint: bool = False


class AnswerOut(BaseModel):
    is_correct: bool
    mastery_level: int
    correct_spelling: str | None = None
    example_en: str | None = None
    example_cn: str | None = None


class SessionFinishOut(BaseModel):
    session_id: int
    total: int
    correct: int
    accuracy: float
    duration_seconds: int


class SessionRecordOut(BaseModel):
    word_id: int
    is_correct: bool
    user_input: str


class SessionDetailOut(BaseModel):
    session_id: int
    mode: Literal["normal", "wrong_only"]
    total: int
    correct: int
    accuracy: float
    duration_seconds: int
    status: Literal["ongoing", "finished"]
    started_at: datetime
    finished_at: datetime | None
    records: list[SessionRecordOut]
