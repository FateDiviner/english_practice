from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WordCreateIn(BaseModel):
    spelling: str = Field(min_length=1, max_length=100)
    phonetic_uk: str | None = Field(default=None, max_length=100)
    phonetic_us: str | None = Field(default=None, max_length=100)
    meaning_cn: str | None = Field(default=None, max_length=255)
    part_of_speech: str | None = Field(default=None, max_length=20)
    example_en: str | None = None
    example_cn: str | None = None
    audio_url: str | None = Field(default=None, max_length=255)
    sort_order: int = 0

    @field_validator("spelling", mode="before")
    @classmethod
    def strip_spelling(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class WordUpdateIn(BaseModel):
    spelling: str | None = Field(default=None, min_length=1, max_length=100)
    phonetic_uk: str | None = Field(default=None, max_length=100)
    phonetic_us: str | None = Field(default=None, max_length=100)
    meaning_cn: str | None = Field(default=None, max_length=255)
    part_of_speech: str | None = Field(default=None, max_length=20)
    example_en: str | None = None
    example_cn: str | None = None
    audio_url: str | None = Field(default=None, max_length=255)
    sort_order: int | None = None

    @field_validator("spelling", mode="before")
    @classmethod
    def strip_spelling(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class WordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wordbook_id: int
    spelling: str
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    example_en: str | None
    example_cn: str | None
    audio_url: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class WordListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wordbook_id: int
    spelling: str
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    example_en: str | None
    example_cn: str | None
    audio_url: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class WordListOut(BaseModel):
    items: list[WordListItem]
    total: int
    page: int
    page_size: int


class WordDeleteOut(BaseModel):
    deleted: bool


class UserWordItem(BaseModel):
    id: int
    spelling: str
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    mastery_level: int | None = None


class UserWordListOut(BaseModel):
    items: list[UserWordItem]
    total: int
    page: int
    page_size: int
