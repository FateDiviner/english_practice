"""学习数据备份的导入 / 导出契约。

文件里绝不出现 user_id / username / password_hash：备份要在账号之间搬运，
携带账号标识既无必要也会让文件变成敏感数据。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

BACKUP_FORMAT = "english-practice-backup"
BACKUP_VERSION = 1

# 单次导入的条目上限，避免超大 payload 拖垮会话
MAX_ITEMS = 2000
MAX_MESSAGES = 200


class BackupWordRecord(BaseModel):
    """一条单词记忆状态，用 wordbook.code + word 定位。"""

    wordbook: str = Field(max_length=32)
    word: str = Field(max_length=128)
    # learning / mastered / wrong
    status: str = Field(default="learning", max_length=16)
    wrong_count: int = Field(default=0, ge=0)
    right_count: int = Field(default=0, ge=0)
    ease_stage: int = Field(default=0, ge=0, le=6)
    last_practiced: str | None = None
    next_review_at: str | None = None


class BackupSession(BaseModel):
    """一条练习结算记录。"""

    wordbook: str = Field(max_length=32)
    mode: str = Field(default="normal", max_length=16)
    total: int = Field(default=0, ge=0)
    correct: int = Field(default=0, ge=0)
    wrong: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    practiced_on: str


class BackupMessage(BaseModel):
    """一条对话记录。

    feedback 原样保留数据库里的 JSON 字符串，不做二次序列化——
    v1.2.1 的 500 正是把它当结构体强转造成的。
    """

    role: str = Field(max_length=16)
    content: str = Field(default="", max_length=20000)
    feedback: str | None = None
    created_at: str


class BackupSummary(BaseModel):
    """导出时的统计摘要，仅用于给人看，导入时不参与计算。"""

    words: int = 0
    sessions: int = 0
    messages: int = 0
    consecutive_days: int = 0


class BackupFile(BaseModel):
    """一份完整的学习数据备份。"""

    format: str = Field(max_length=64)
    version: int
    exported_at: str = ""
    summary: BackupSummary = Field(default_factory=BackupSummary)
    word_records: list[BackupWordRecord] = Field(default_factory=list, max_length=MAX_ITEMS)
    sessions: list[BackupSession] = Field(default_factory=list, max_length=MAX_ITEMS)
    chat_messages: list[BackupMessage] = Field(
        default_factory=list, max_length=MAX_MESSAGES
    )
    consecutive_days: int = Field(default=0, ge=0)
    last_checkin_date: str | None = None
    active_wordbook: str | None = Field(default=None, max_length=32)


class ImportResult(BaseModel):
    """导入结果统计，全部为 0 也可能是成功的（例如重复导入同一份文件）。"""

    records_new: int = 0
    records_merged: int = 0
    sessions_added: int = 0
    sessions_skipped: int = 0
    messages_added: int = 0
    messages_skipped: int = 0
    words_unmatched: int = 0
    consecutive_days: int = 0
