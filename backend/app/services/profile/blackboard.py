"""Blackboard state shared by the profile analysis expert agents."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.models.practice_session import PracticeSession
from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord

PROFILE_ANALYSIS_VERSION = "profile-blackboard-v2"


@dataclass(frozen=True)
class WordProgressSnapshot:
    word_id: int
    spelling: str
    mastery_level: int
    correct_count: int
    wrong_count: int
    last_result: str | None
    last_practiced_at: datetime | None


@dataclass(frozen=True)
class WrongWordSnapshot:
    word_id: int
    spelling: str
    wrong_count: int
    resolved: bool
    last_wrong_at: datetime | None


@dataclass(frozen=True)
class PracticeSessionSnapshot:
    id: int
    started_at: datetime
    finished_at: datetime | None
    total_count: int
    correct_count: int
    status: str


@dataclass
class BlackboardEntry:
    """One complete knowledge-source contribution on the shared blackboard."""

    id: str
    source: str
    agent_key: str
    content: BaseModel | dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = field(default_factory=list)

    def content_json(self) -> Any:
        if isinstance(self.content, BaseModel):
            return self.content.model_dump(mode="json")
        return self.content

    def preview(self, limit: int = 120) -> str:
        content = json.dumps(self.content_json(), ensure_ascii=False, default=str)
        return content[:limit] + ("..." if len(content) > limit else "")


@dataclass
class Blackboard:
    """Mutable shared context: raw learning facts plus expert artifacts."""

    user_id: int
    username: str
    user_created_at: datetime
    word_progress: list[WordProgressSnapshot]
    wrong_words: list[WrongWordSnapshot]
    practice_sessions: list[PracticeSessionSnapshot]
    entries: list[BlackboardEntry] = field(default_factory=list)
    artifacts: dict[str, BaseModel] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    problem_tags: list[str] = field(
        default_factory=lambda: ["data", "habit", "diagnosis", "planner"]
    )
    solution: BaseModel | dict[str, Any] | None = None
    solution_confidence: float = 0.0

    def write(self, entry: BlackboardEntry) -> None:
        """Append one knowledge-source contribution with bounded confidence."""
        entry.confidence = max(0.0, min(1.0, entry.confidence))
        self.entries.append(entry)

    def read(self, tags: list[str] | None = None) -> list[BlackboardEntry]:
        """Read all entries, or entries containing any requested tag."""
        if not tags:
            return list(self.entries)
        requested = set(tags)
        return [entry for entry in self.entries if requested & set(entry.tags)]

    def write_artifact(self, agent_key: str, output: BaseModel) -> None:
        """Publish structured expert output for later agents and prompt building."""
        self.artifacts[agent_key] = output
        self.trace.append(agent_key)

    def get_unique_sources(self) -> set[str]:
        return {entry.agent_key for entry in self.entries}

    def get_summary(self, limit: int = 120) -> str:
        if not self.entries:
            return "黑板当前为空，暂无专家贡献。"
        return "\n".join(
            f"[{entry.source}] {entry.preview(limit)} (置信度: {entry.confidence:.2f})"
            for entry in self.entries
        )

    def set_solution(
        self,
        solution: BaseModel | dict[str, Any],
        confidence: float,
    ) -> None:
        self.solution = solution
        self.solution_confidence = max(0.0, min(1.0, confidence))

    def fingerprint(self) -> str:
        """Hash the facts that affect analysis, so changed data gets a new cache key."""
        payload = {
            "version": PROFILE_ANALYSIS_VERSION,
            "user_id": self.user_id,
            "word_progress": [item.__dict__ for item in self.word_progress],
            "wrong_words": [item.__dict__ for item in self.wrong_words],
            "practice_sessions": [item.__dict__ for item in self.practice_sessions],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def prompt_payload(self, max_items: int = 80) -> dict[str, Any]:
        """Keep prompts bounded while deterministic calculators still use all facts."""
        previous = {key: value.model_dump(mode="json") for key, value in self.artifacts.items()}
        return {
            "user": {"id": self.user_id, "username": self.username},
            "word_progress": [
                item.__dict__
                for item in sorted(
                    self.word_progress,
                    key=lambda item: item.last_practiced_at or datetime.min,
                    reverse=True,
                )[:max_items]
            ],
            "wrong_words": [
                item.__dict__
                for item in sorted(
                    self.wrong_words,
                    key=lambda item: item.wrong_count,
                    reverse=True,
                )[:max_items]
            ],
            "practice_sessions": [item.__dict__ for item in self.practice_sessions[-max_items:]],
            "blackboard_summary": self.get_summary(limit=200),
            "previous_expert_analysis": previous,
        }


async def collect_blackboard(session: AsyncSession, user_id: int) -> Blackboard:
    """Load the three required learning-data sources into one shared context."""
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "用户不存在")

    progress_rows = (
        await session.execute(
            select(WordProgress, Word)
            .join(Word, Word.id == WordProgress.word_id)
            .where(WordProgress.user_id == user_id)
            .order_by(WordProgress.last_practiced_at.desc(), WordProgress.id.desc())
        )
    ).all()
    wrong_rows = (
        await session.execute(
            select(WrongWord, Word)
            .join(Word, Word.id == WrongWord.word_id)
            .where(WrongWord.user_id == user_id)
            .order_by(WrongWord.wrong_count.desc(), WrongWord.last_wrong_at.desc())
        )
    ).all()
    sessions = list(
        await session.scalars(
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id)
            .order_by(PracticeSession.started_at.asc(), PracticeSession.id.asc())
        )
    )

    return Blackboard(
        user_id=user.id,
        username=user.username,
        user_created_at=user.created_at,
        word_progress=[
            WordProgressSnapshot(
                word_id=progress.word_id,
                spelling=word.spelling,
                mastery_level=progress.mastery_level,
                correct_count=progress.correct_count,
                wrong_count=progress.wrong_count,
                last_result=progress.last_result,
                last_practiced_at=progress.last_practiced_at,
            )
            for progress, word in progress_rows
        ],
        wrong_words=[
            WrongWordSnapshot(
                word_id=wrong.word_id,
                spelling=word.spelling,
                wrong_count=wrong.wrong_count,
                resolved=wrong.resolved,
                last_wrong_at=wrong.last_wrong_at,
            )
            for wrong, word in wrong_rows
        ],
        practice_sessions=[
            PracticeSessionSnapshot(
                id=item.id,
                started_at=item.started_at,
                finished_at=item.finished_at,
                total_count=item.total_count,
                correct_count=item.correct_count,
                status=item.status,
            )
            for item in sessions
        ],
    )
