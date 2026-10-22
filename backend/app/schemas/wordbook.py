from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WordbookStatus = Literal["draft", "published", "archived"]


class WordbookCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    level: str | None = Field(default=None, max_length=20)
    status: WordbookStatus = "draft"

    @field_validator("name", "level", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class WordbookUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    level: str | None = Field(default=None, max_length=20)
    status: WordbookStatus | None = None

    @field_validator("name", "level", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class WordbookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    level: str | None
    status: WordbookStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class WordbookListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    level: str | None
    status: WordbookStatus
    created_by: int
    word_count: int
    created_at: datetime
    updated_at: datetime


class WordbookListOut(BaseModel):
    items: list[WordbookListItem]
    total: int
    page: int
    page_size: int


class WordbookDeleteOut(BaseModel):
    deleted: bool


class UserWordbookProgress(BaseModel):
    mastered: int
    total: int


class UserWordbookItem(BaseModel):
    id: int
    name: str
    description: str | None
    level: str | None
    word_count: int
    my_progress: UserWordbookProgress


class UserWordbookDetail(BaseModel):
    id: int
    name: str
    description: str | None
    level: str | None
    word_count: int


class UserWordbookListOut(BaseModel):
    items: list[UserWordbookItem]
    total: int
    page: int
    page_size: int
