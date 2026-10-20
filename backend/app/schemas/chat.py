"""AI 伴学对话相关模型。"""

from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class ChatSendRequest(BaseModel):
    """发送一条对话消息。"""

    content: str = Field(min_length=1, max_length=4000, description="用户输入")
    # explain_word / grammar_check / free_chat 快捷药丸指令
    preset: str | None = Field(default=None, max_length=32)
    # 可选上下文，如刚默写拼错的单词，便于 AI 精准答疑
    context: str | None = Field(default=None, max_length=500)


class ChatSource(BaseModel):
    """一条可展示的引用来源。"""

    index: int = Field(ge=1)
    kind: str = Field(max_length=32)
    label: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=64)


class AgentMetadata(BaseModel):
    """聊天消息的 Agent / RAG 执行摘要，不包含隐藏推理。"""

    mode: Literal["agent", "chat"] = "chat"
    rounds: int = Field(default=0, ge=0)
    tools: list[str] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    fallback: str | None = None
    elapsed_ms: int = Field(default=0, ge=0)


class FeedbackBlock(BaseModel):
    """实时纠错结构化区块，对应 AGENTS.md 的 [语法指正] / [地道表达]。"""

    grammar: str = ""
    polish: list[str] = Field(default_factory=list)


class MessageOut(BaseModel):
    """单条消息。"""

    id: int
    role: str
    content: str
    feedback: FeedbackBlock | None = None
    metadata: AgentMetadata | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
