from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AiConversationCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    scene: str | None = Field(default=None, max_length=50)

    @field_validator("title", "scene", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class AiMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AiConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    scene: str | None
    created_at: datetime
    updated_at: datetime


class AiConversationListItem(AiConversationOut):
    message_count: int


class AiConversationListOut(BaseModel):
    items: list[AiConversationListItem]
    total: int
    page: int
    page_size: int


class AiConversationDetailOut(AiConversationOut):
    messages: list[AiMessageOut]


class AiConversationDeleteOut(BaseModel):
    deleted: bool
