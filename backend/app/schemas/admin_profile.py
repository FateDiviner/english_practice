from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AgentSource = Literal["llm", "heuristic"]


class RadarMetricOut(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    category: Literal["data", "habit", "diagnosis", "planner"]


class AccuracyTrendPointOut(BaseModel):
    period: str
    accuracy: float = Field(ge=0, le=100)
    session_count: int = Field(ge=0)


class VocabularyBucketOut(BaseModel):
    label: str
    count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)


class DataExpertOut(BaseModel):
    source: AgentSource
    confidence: float = Field(ge=0, le=1)
    summary: str
    tags: list[str]
    accuracy_trend: list[AccuracyTrendPointOut]
    vocabulary_distribution: list[VocabularyBucketOut]
    metrics: list[RadarMetricOut]
    highlights: list[str]
    risks: list[str]


class WeeklyFrequencyOut(BaseModel):
    week: str
    sessions: int = Field(ge=0)
    active_days: int = Field(ge=0)


class WeekdayPatternOut(BaseModel):
    weekday: str
    sessions: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)


class HabitExpertOut(BaseModel):
    source: AgentSource
    confidence: float = Field(ge=0, le=1)
    summary: str
    tags: list[str]
    weekly_frequency: list[WeeklyFrequencyOut]
    checkin_pattern: list[WeekdayPatternOut]
    average_duration_minutes: float = Field(ge=0)
    total_duration_minutes: float = Field(ge=0)
    active_days: int = Field(ge=0)
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    preferred_time_slot: str
    metrics: list[RadarMetricOut]
    highlights: list[str]
    risks: list[str]


class ErrorPatternOut(BaseModel):
    kind: Literal["length", "prefix", "repetition", "status"]
    label: str
    evidence: str
    hit_count: int = Field(ge=0)
    severity: Literal["low", "medium", "high"]


class FocusWordOut(BaseModel):
    word_id: int
    spelling: str
    wrong_count: int = Field(ge=0)
    resolved: bool


class DiagnosisExpertOut(BaseModel):
    source: AgentSource
    confidence: float = Field(ge=0, le=1)
    summary: str
    tags: list[str]
    error_patterns: list[ErrorPatternOut]
    focus_words: list[FocusWordOut]
    metrics: list[RadarMetricOut]
    risks: list[str]


class ReviewPlanItemOut(BaseModel):
    day: int = Field(ge=1, le=7)
    title: str
    activity: str
    word_count: int = Field(ge=0)
    focus_words: list[str]


class PlannerExpertOut(BaseModel):
    source: AgentSource
    confidence: float = Field(ge=0, le=1)
    summary: str
    tags: list[str]
    review_plan: list[ReviewPlanItemOut]
    weekly_goals: list[str]
    recommendations: list[str]
    metrics: list[RadarMetricOut]


class ProfileUserOut(BaseModel):
    id: int
    username: str


class ProfileCoverageOut(BaseModel):
    word_progress_count: int = Field(ge=0)
    wrong_word_count: int = Field(ge=0)
    practice_session_count: int = Field(ge=0)
    first_practice_at: datetime | None
    last_practice_at: datetime | None


class ProfileSummaryOut(BaseModel):
    headline: str
    confidence: float = Field(ge=0, le=1)
    level: Literal["excellent", "good", "developing", "needs_attention", "insufficient_data"]
    tags: list[str]
    radar_metrics: list[RadarMetricOut]
    highlights: list[str]
    risks: list[str]


class ProfileCacheOut(BaseModel):
    hit: bool
    ttl_seconds: int = Field(ge=1)
    expires_at: datetime


class ProfileAgentsOut(BaseModel):
    data: DataExpertOut
    habit: HabitExpertOut
    diagnosis: DiagnosisExpertOut
    planner: PlannerExpertOut


class UserProfileOut(BaseModel):
    user: ProfileUserOut
    generated_at: datetime
    cache: ProfileCacheOut
    coverage: ProfileCoverageOut
    summary: ProfileSummaryOut
    agents: ProfileAgentsOut
    agent_sequence: list[Literal["data", "habit", "diagnosis", "planner"]]
