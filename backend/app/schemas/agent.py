from pydantic import BaseModel, Field, field_validator


class AgentHistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AgentChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    scene: str | None = Field(default=None, max_length=50)
    conversation_id: int | None = Field(default=None, ge=1)
    history: list[AgentHistoryMessage] = Field(default_factory=list, max_length=20)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value
