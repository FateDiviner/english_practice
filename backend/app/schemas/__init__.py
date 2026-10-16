"""Pydantic 请求 / 响应模型集中导出。"""

from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserInfo,
)
from app.schemas.backup import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    BackupFile,
    ImportResult,
)
from app.schemas.chat import ChatSendRequest, FeedbackBlock, MessageOut
from app.schemas.stats import (
    DailyStat,
    LearningTotals,
    RecentSession,
    StatsOverview,
)
from app.schemas.practice import (
    HintRequest,
    HintResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    SettlementResponse,
    SubmitRequest,
    SubmitResponse,
    WrongBookResponse,
)
from app.schemas.word import WordBookOut, WordOut, WordBookProgress

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "UserInfo",
    "WordBookOut",
    "WordOut",
    "WordBookProgress",
    "PracticeStartRequest",
    "HintRequest",
    "HintResponse",
    "PracticeStartResponse",
    "SubmitRequest",
    "SubmitResponse",
    "SettlementResponse",
    "WrongBookResponse",
    "ChatSendRequest",
    "MessageOut",
    "FeedbackBlock",
    "BackupFile",
    "ImportResult",
    "DailyStat",
    "RecentSession",
    "LearningTotals",
    "StatsOverview",
]
