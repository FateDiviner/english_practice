from typing import Literal

from pydantic import BaseModel


class SessionCreateIn(BaseModel):
    wordbook_id: int | None = None
    mode: Literal["normal", "wrong_only"]
    count: Literal[10, 20, 50] = 20
    strict_mode: bool = True


class QuestionHintOut(BaseModel):
    first_letter: str
    length: int


class QuestionOut(BaseModel):
    word_id: int
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    hint: QuestionHintOut


class SessionCreateOut(BaseModel):
    session_id: int
    total: int
    questions: list[QuestionOut]
    notice: str | None = None
