"""Blackboard state shared by the profile analysis expert agents."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
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

PROFILE_ANALYSIS_VERSION = "profile-blackboard-v1"


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
class Blackboard:
    """Mutable shared context: raw learning facts plus expert artifacts."""

    user_id: int
    username: str
    user_created_at: datetime
    word_progress: list[WordProgressSnapshot]
    wrong_words: list[WrongWordSnapshot]
    practice_sessions: list[PracticeSessionSnapshot]
    artifacts: dict[str, BaseModel] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)

    def write_artifact(self, agent_key: str, output: BaseModel) -> None:
        """Publish an expert result so subsequent experts can read it."""
        self.artifacts[agent_key] = output
        self.trace.append(agent_key)

    def artifact_json(self, agent_key: str) -> dict[str, Any] | None:
        artifact = self.artifacts.get(agent_key)
        return artifact.model_dump(mode="json") if artifact is not None else None

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
        previous = {
            key: value.model_dump(mode="json") for key, value in self.artifacts.items()
        }
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
            "practice_sessions": [
                item.__dict__ for item in self.practice_sessions[-max_items:]
            ],
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