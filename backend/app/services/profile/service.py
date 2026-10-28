"""Profile analysis orchestration and final report assembly."""

from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache

from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.admin_profile import (
    DataExpertOut,
    DiagnosisExpertOut,
    HabitExpertOut,
    PlannerExpertOut,
    ProfileAgentsOut,
    ProfileCacheOut,
    ProfileCoverageOut,
    ProfileSummaryOut,
    ProfileUserOut,
    UserProfileOut,
)
from app.services.agent.client import get_llm_client, is_mock_provider
from app.services.profile.agents import BaseProfileExpert, build_default_agents
from app.services.profile.blackboard import Blackboard, collect_blackboard
from app.services.profile.cache import TTLProfileCache
from app.services.profile.controller import BlackboardController

AGENT_SEQUENCE = ["data", "habit", "diagnosis", "planner"]
LEVEL_LABELS = {
    "excellent": "优秀",
    "good": "良好",
    "developing": "成长中",
    "needs_attention": "需重点关注",
    "insufficient_data": "数据不足",
}


def _unique(items: Sequence[str], limit: int) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _level(coverage: ProfileCoverageOut, score: float) -> str:
    if coverage.word_progress_count == 0 and coverage.practice_session_count == 0:
        return "insufficient_data"
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 55:
        return "developing"
    return "needs_attention"


def assemble_profile_report(blackboard: Blackboard) -> UserProfileOut:
    data = blackboard.artifacts.get("data")
    habit = blackboard.artifacts.get("habit")
    diagnosis = blackboard.artifacts.get("diagnosis")
    planner = blackboard.artifacts.get("planner")
    if not isinstance(data, DataExpertOut):
        raise RuntimeError("missing data expert artifact")
    if not isinstance(habit, HabitExpertOut):
        raise RuntimeError("missing habit expert artifact")
    if not isinstance(diagnosis, DiagnosisExpertOut):
        raise RuntimeError("missing diagnosis expert artifact")
    if not isinstance(planner, PlannerExpertOut):
        raise RuntimeError("missing planner expert artifact")

    practice_sessions = blackboard.practice_sessions
    coverage = ProfileCoverageOut(
        word_progress_count=len(blackboard.word_progress),
        wrong_word_count=len(blackboard.wrong_words),
        practice_session_count=len(practice_sessions),
        first_practice_at=practice_sessions[0].started_at if practice_sessions else None,
        last_practice_at=practice_sessions[-1].finished_at or practice_sessions[-1].started_at
        if practice_sessions
        else None,
    )
    radar_metrics = [
        *data.metrics,
        *habit.metrics,
        *diagnosis.metrics,
    ]
    overall_score = (
        sum(item.score for item in radar_metrics) / len(radar_metrics) if radar_metrics else 0
    )
    level = _level(coverage, overall_score)
    tags = _unique(
        [*data.tags, *habit.tags, *diagnosis.tags, *planner.tags],
        8,
    )
    highlights = _unique(
        [*data.highlights, *habit.highlights, *planner.weekly_goals[:1]],
        5,
    )
    risks = _unique([*data.risks, *habit.risks, *diagnosis.risks], 5)
    headline = (
        f"{blackboard.username} 的学情画像：{LEVEL_LABELS[level]}"
        f"，{tags[0] if tags else '等待更多学习数据'}"
    )
    generated_at = datetime.now(UTC)

    return UserProfileOut(
        user=ProfileUserOut(id=blackboard.user_id, username=blackboard.username),
        generated_at=generated_at,
        cache=ProfileCacheOut(
            hit=False,
            ttl_seconds=1,
            expires_at=generated_at,
        ),
        coverage=coverage,
        summary=ProfileSummaryOut(
            headline=headline,
            confidence=blackboard.solution_confidence,
            level=level,
            tags=tags,
            radar_metrics=radar_metrics,
            highlights=highlights,
            risks=risks,
        ),
        agents=ProfileAgentsOut(
            data=data,
            habit=habit,
            diagnosis=diagnosis,
            planner=planner,
        ),
        agent_sequence=AGENT_SEQUENCE,
    )


def _profile_trace_inputs(inputs: dict) -> dict:
    return {"user_id": inputs.get("user_id")}


class ProfileOrchestrator:
    """Controller-driven Blackboard analysis with a cached final report."""

    def __init__(
        self,
        agents: list[BaseProfileExpert],
        cache: TTLProfileCache[UserProfileOut],
        controller: BlackboardController | None = None,
    ) -> None:
        self._agents = agents
        self._cache = cache
        self._controller = controller or BlackboardController()

    @traceable(
        run_type="chain",
        name="profile.analyze",
        process_inputs=_profile_trace_inputs,
    )
    async def analyze(self, session: AsyncSession, user_id: int) -> UserProfileOut:
        blackboard = await collect_blackboard(session, user_id)
        cache_key = f"{user_id}:{blackboard.fingerprint()}"

        async def run_experts() -> UserProfileOut:
            result = await self._controller.solve(blackboard, self._agents)
            if result.missing_sources:
                raise RuntimeError(
                    f"profile knowledge sources not completed: {result.missing_sources}"
                )
            if blackboard.trace != AGENT_SEQUENCE:
                raise RuntimeError("profile expert sequence violated")
            report = assemble_profile_report(blackboard)
            blackboard.set_solution(report, result.confidence)
            return report

        report, hit, expires_at = await self._cache.get_or_create(cache_key, run_experts)
        return report.model_copy(
            update={
                "cache": ProfileCacheOut(
                    hit=hit,
                    ttl_seconds=self._cache.ttl_seconds,
                    expires_at=expires_at,
                )
            }
        )


@lru_cache
def get_profile_orchestrator() -> ProfileOrchestrator:
    settings = get_settings()
    llm = None if is_mock_provider() else get_llm_client()
    return ProfileOrchestrator(
        agents=build_default_agents(llm),
        cache=TTLProfileCache(settings.PROFILE_CACHE_TTL_SECONDS),
    )
