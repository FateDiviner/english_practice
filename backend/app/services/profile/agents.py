"""Four Blackboard profile experts with deterministic fallbacks and LLM refinement."""

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.admin_profile import (
    AccuracyTrendPointOut,
    DataExpertOut,
    DiagnosisExpertOut,
    ErrorPatternOut,
    FocusWordOut,
    HabitExpertOut,
    PlannerExpertOut,
    RadarMetricOut,
    ReviewPlanItemOut,
    VocabularyBucketOut,
    WeekdayPatternOut,
    WeeklyFrequencyOut,
)
from app.services.agent.client import ChatMessage, LLMClient
from app.services.profile.blackboard import Blackboard
from app.services.profile.prompts import (
    DATA_SYSTEM_PROMPT,
    DIAGNOSIS_SYSTEM_PROMPT,
    HABIT_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    PROFILE_JSON_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)
WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _score(value: float) -> int:
    return max(0, min(100, round(value)))


def _percentage(part: float, total: float) -> float:
    return round(part / total * 100, 1) if total else 0.0


def _metric(
    key: str,
    label: str,
    score: float,
    category: str,
) -> RadarMetricOut:
    return RadarMetricOut(
        key=key,
        label=label,
        score=_score(score),
        category=category,
    )


def _extract_json_object(raw: str) -> dict | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class BaseProfileExpert(Generic[OutputT]):
    key: str
    role_prompt: str
    output_type: type[OutputT]

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    async def analyze(self, blackboard: Blackboard) -> OutputT:
        fallback = self.build_fallback(blackboard)
        if self._llm is None:
            return fallback

        refined = await self._refine(blackboard, fallback)
        if refined is None:
            return fallback
        return self.merge_refined(refined, fallback)

    def build_fallback(self, blackboard: Blackboard) -> OutputT:
        raise NotImplementedError

    def merge_refined(self, refined: OutputT, fallback: OutputT) -> OutputT:
        return refined.model_copy(update={"source": "llm"})

    async def _refine(self, blackboard: Blackboard, fallback: OutputT) -> OutputT | None:
        payload = {
            "draft": fallback.model_dump(mode="json"),
            "blackboard": blackboard.prompt_payload(),
        }
        messages = [
            ChatMessage(
                role="system",
                content=f"{PROFILE_JSON_SYSTEM_PROMPT}\n\n{self.role_prompt}",
            ),
            ChatMessage(
                role="user",
                content=json.dumps(payload, ensure_ascii=False, default=str),
            ),
        ]
        try:
            raw = "".join([chunk async for chunk in self._llm.stream(messages)])
            data = _extract_json_object(raw)
            if data is None:
                return None
            return self.output_type.model_validate(data)
        except (ValidationError, ValueError, TypeError):
            logger.warning("Profile expert %s returned invalid JSON; using fallback", self.key)
            return None
        except Exception:
            logger.exception("Profile expert %s LLM call failed; using fallback", self.key)
            return None


class DataExpert(BaseProfileExpert[DataExpertOut]):
    key = "data"
    role_prompt = DATA_SYSTEM_PROMPT
    output_type = DataExpertOut

    def build_fallback(self, blackboard: Blackboard) -> DataExpertOut:
        sessions = [item for item in blackboard.practice_sessions if item.total_count > 0]
        if sessions:
            total_answers = sum(item.total_count for item in sessions)
            correct_answers = sum(item.correct_count for item in sessions)
        else:
            total_answers = sum(
                item.correct_count + item.wrong_count for item in blackboard.word_progress
            )
            correct_answers = sum(item.correct_count for item in blackboard.word_progress)
        accuracy = _percentage(correct_answers, total_answers)

        weekly: dict[date, list[int]] = defaultdict(lambda: [0, 0])
        for item in sessions:
            week_start = item.started_at.date() - timedelta(days=item.started_at.weekday())
            weekly[week_start][0] += item.total_count
            weekly[week_start][1] += item.correct_count
        trend = [
            AccuracyTrendPointOut(
                period=week_start.strftime("%m-%d"),
                accuracy=_percentage(correct, total),
                session_count=sum(
                    1
                    for item in sessions
                    if item.started_at.date() - timedelta(days=item.started_at.weekday())
                    == week_start
                ),
            )
            for week_start, (total, correct) in sorted(weekly.items())[-8:]
        ]

        mastery_counts = Counter(
            item.mastery_level for item in blackboard.word_progress
        )
        total_words = len(blackboard.word_progress)
        distribution = [
            VocabularyBucketOut(
                label=label,
                count=mastery_counts.get(level, 0),
                percentage=_percentage(mastery_counts.get(level, 0), total_words),
            )
            for level, label in ((0, "新词"), (1, "学习中"), (2, "已掌握"))
        ]
        mastered = mastery_counts.get(2, 0)
        vocabulary_score = min(100, total_words * 2)
        mastery_score = _percentage(mastered, total_words)
        metrics = [
            _metric("accuracy", "正确率", accuracy, "data"),
            _metric("vocabulary", "词汇覆盖", vocabulary_score, "data"),
            _metric("mastery", "词汇掌握", mastery_score, "data"),
        ]

        tags: list[str] = []
        highlights: list[str] = []
        risks: list[str] = []
        if total_answers == 0:
            tags.append("样本不足")
            risks.append("暂无有效答题数据，正确率结论仅供参考")
        elif accuracy >= 85:
            tags.append("正确率优秀")
            highlights.append(f"整体正确率达到 {accuracy:.1f}%")
        elif accuracy < 60:
            tags.append("正确率待提升")
            risks.append(f"整体正确率仅 {accuracy:.1f}%")
        else:
            tags.append("正确率稳定")

        if len(trend) >= 2:
            delta = trend[-1].accuracy - trend[0].accuracy
            if delta >= 5:
                tags.append("趋势上升")
                highlights.append(f"近期正确率较前期提升 {delta:.1f} 个百分点")
            elif delta <= -5:
                tags.append("趋势回落")
                risks.append(f"近期正确率较前期下降 {abs(delta):.1f} 个百分点")

        if total_words == 0:
            risks.append("尚未形成词汇掌握记录")
        elif mastery_score >= 60:
            tags.append("掌握度较高")
            highlights.append(f"已掌握 {mastered}/{total_words} 个记录词")
        else:
            risks.append(f"已掌握词占比为 {mastery_score:.1f}%")

        summary = (
            f"累计有效答题 {total_answers} 次，整体正确率 {accuracy:.1f}%；"
            f"当前覆盖 {total_words} 个学习词，其中已掌握 {mastered} 个。"
        )
        return DataExpertOut(
            source="heuristic",
            summary=summary,
            tags=tags[:5],
            accuracy_trend=trend,
            vocabulary_distribution=distribution,
            metrics=metrics,
            highlights=highlights,
            risks=risks,
        )

    def merge_refined(
        self,
        refined: DataExpertOut,
        fallback: DataExpertOut,
    ) -> DataExpertOut:
        return fallback.model_copy(
            update={
                "source": "llm",
                "summary": refined.summary,
                "tags": refined.tags[:5],
                "highlights": refined.highlights,
                "risks": refined.risks,
            }
        )


class HabitExpert(BaseProfileExpert[HabitExpertOut]):
    key = "habit"
    role_prompt = HABIT_SYSTEM_PROMPT
    output_type = HabitExpertOut

    def build_fallback(self, blackboard: Blackboard) -> HabitExpertOut:
        sessions = blackboard.practice_sessions
        active_dates = sorted({item.started_at.date() for item in sessions})
        durations = [
            (item.finished_at - item.started_at).total_seconds() / 60
            for item in sessions
            if item.finished_at is not None
            and item.finished_at > item.started_at
            and (item.finished_at - item.started_at) <= timedelta(hours=6)
        ]
        total_duration = round(sum(durations), 1)
        average_duration = round(total_duration / len(durations), 1) if durations else 0.0

        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())
        week_starts = [
            current_week_start - timedelta(weeks=offset) for offset in range(7, -1, -1)
        ]
        weekly_frequency: list[WeeklyFrequencyOut] = []
        for week_start in week_starts:
            week_end = week_start + timedelta(days=7)
            week_dates = {item for item in active_dates if week_start <= item < week_end}
            weekly_frequency.append(
                WeeklyFrequencyOut(
                    week=week_start.strftime("%m-%d"),
                    sessions=sum(
                        1
                        for item in sessions
                        if week_start <= item.started_at.date() < week_end
                    ),
                    active_days=len(week_dates),
                )
            )

        weekday_counts = Counter(item.weekday() for item in active_dates)
        total_active_days = max(1, len(active_dates))
        checkin_pattern = [
            WeekdayPatternOut(
                weekday=label,
                sessions=weekday_counts.get(index, 0),
                percentage=_percentage(weekday_counts.get(index, 0), total_active_days),
            )
            for index, label in enumerate(WEEKDAY_LABELS)
        ]

        current_streak = self._current_streak(active_dates, today)
        longest_streak = self._longest_streak(active_dates)
        preferred_slot = self._preferred_time_slot(sessions)

        recent_start = today - timedelta(days=27)
        recent_sessions = [item for item in sessions if item.started_at.date() >= recent_start]
        recent_active_days = len({item.started_at.date() for item in recent_sessions})
        frequency_score = min(100, round(len(recent_sessions) / 20 * 100))
        duration_score = min(100, round(average_duration / 20 * 100))
        consistency_score = min(100, round(recent_active_days / 20 * 100))
        metrics = [
            _metric("frequency", "学习频率", frequency_score, "habit"),
            _metric("duration", "练习时长", duration_score, "habit"),
            _metric("consistency", "打卡稳定", consistency_score, "habit"),
        ]

        tags: list[str] = []
        highlights: list[str] = []
        risks: list[str] = []
        if not sessions:
            tags.append("暂无练习")
            risks.append("尚无练习会话，无法判断学习习惯")
        else:
            if current_streak >= 3:
                tags.append("连续打卡")
                highlights.append(f"当前已连续学习 {current_streak} 天")
            if consistency_score >= 70:
                tags.append("习惯稳定")
            elif consistency_score < 40:
                tags.append("频率偏低")
                risks.append("近 4 周学习频率偏低，建议固定练习日")
            if average_duration > 30:
                risks.append("单次练习时长偏长，注意拆分复习任务")
            elif 0 < average_duration < 8:
                risks.append("单次练习时长偏短，可逐步延长到 15 分钟")
            if preferred_slot != "暂无规律":
                tags.append(f"{preferred_slot}活跃")

        summary = (
            f"共完成 {len(sessions)} 次练习，平均每次 {average_duration:.1f} 分钟；"
            f"总活跃 {len(active_dates)} 天，当前连续 {current_streak} 天，"
            f"偏好时段为{preferred_slot}。"
        )
        return HabitExpertOut(
            source="heuristic",
            summary=summary,
            tags=tags[:5],
            weekly_frequency=weekly_frequency,
            checkin_pattern=checkin_pattern,
            average_duration_minutes=average_duration,
            total_duration_minutes=total_duration,
            active_days=len(active_dates),
            current_streak_days=current_streak,
            longest_streak_days=longest_streak,
            preferred_time_slot=preferred_slot,
            metrics=metrics,
            highlights=highlights,
            risks=risks,
        )

    @staticmethod
    def _current_streak(active_dates: list[date], today: date) -> int:
        if not active_dates:
            return 0
        active = set(active_dates)
        cursor = today if today in active else today - timedelta(days=1)
        if cursor not in active:
            return 0
        streak = 0
        while cursor in active:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @staticmethod
    def _longest_streak(active_dates: list[date]) -> int:
        if not active_dates:
            return 0
        longest = current = 1
        for previous, current_date in zip(active_dates, active_dates[1:], strict=False):
            current = current + 1 if current_date == previous + timedelta(days=1) else 1
            longest = max(longest, current)
        return longest

    @staticmethod
    def _preferred_time_slot(sessions) -> str:
        if not sessions:
            return "暂无规律"
        slots = Counter()
        for item in sessions:
            hour = item.started_at.hour
            if 5 <= hour < 12:
                slots["上午"] += 1
            elif 12 <= hour < 18:
                slots["下午"] += 1
            elif 18 <= hour < 23:
                slots["晚间"] += 1
            else:
                slots["夜间"] += 1
        return slots.most_common(1)[0][0]

    def merge_refined(
        self,
        refined: HabitExpertOut,
        fallback: HabitExpertOut,
    ) -> HabitExpertOut:
        return fallback.model_copy(
            update={
                "source": "llm",
                "summary": refined.summary,
                "tags": refined.tags[:5],
                "highlights": refined.highlights,
                "risks": refined.risks,
            }
        )


class DiagnosisExpert(BaseProfileExpert[DiagnosisExpertOut]):
    key = "diagnosis"
    role_prompt = DIAGNOSIS_SYSTEM_PROMPT
    output_type = DiagnosisExpertOut

    def build_fallback(self, blackboard: Blackboard) -> DiagnosisExpertOut:
        wrong_words = blackboard.wrong_words
        total_wrong_hits = sum(max(1, item.wrong_count) for item in wrong_words)
        patterns: list[ErrorPatternOut] = []

        length_groups: dict[str, int] = defaultdict(int)
        for item in wrong_words:
            length = len(item.spelling)
            if length <= 4:
                bucket = "1-4 字母"
            elif length <= 6:
                bucket = "5-6 字母"
            elif length <= 9:
                bucket = "7-9 字母"
            else:
                bucket = "10+ 字母"
            length_groups[bucket] += max(1, item.wrong_count)

        top_length, top_length_hits = self._top_group(length_groups)
        length_share = top_length_hits / total_wrong_hits if total_wrong_hits else 0.0
        if top_length and length_share >= 0.25:
            patterns.append(
                ErrorPatternOut(
                    kind="length",
                    label=f"{top_length}单词易错",
                    evidence=(
                        f"{top_length}单词产生 {top_length_hits}/{total_wrong_hits} 次错误，"
                        f"占 {length_share * 100:.1f}%"
                    ),
                    hit_count=top_length_hits,
                    severity=self._severity(length_share),
                )
            )

        prefix_groups: dict[str, int] = defaultdict(int)
        for item in wrong_words:
            spelling = item.spelling.lower()
            if len(spelling) >= 3 and spelling[:2].isalpha():
                prefix_groups[f"{spelling[:2]}-"] += max(1, item.wrong_count)
        top_prefix, top_prefix_hits = self._top_group(prefix_groups)
        prefix_share = top_prefix_hits / total_wrong_hits if total_wrong_hits else 0.0
        if top_prefix and top_prefix_hits >= 2 and prefix_share >= 0.25:
            patterns.append(
                ErrorPatternOut(
                    kind="prefix",
                    label=f"{top_prefix} 前缀薄弱",
                    evidence=(
                        f"前缀为 {top_prefix} 的错词产生 {top_prefix_hits}/{total_wrong_hits} "
                        f"次错误，占 {prefix_share * 100:.1f}%"
                    ),
                    hit_count=top_prefix_hits,
                    severity=self._severity(prefix_share),
                )
            )

        repeated_hits = sum(
            max(1, item.wrong_count) for item in wrong_words if item.wrong_count >= 2
        )
        repeated_share = repeated_hits / total_wrong_hits if total_wrong_hits else 0.0
        if repeated_hits:
            patterns.append(
                ErrorPatternOut(
                    kind="repetition",
                    label="重复错误",
                    evidence=(
                        f"有 {sum(1 for item in wrong_words if item.wrong_count >= 2)} 个词"
                        f"被重复答错，累计 {repeated_hits} 次"
                    ),
                    hit_count=repeated_hits,
                    severity=self._severity(repeated_share),
                )
            )

        unresolved = [item for item in wrong_words if not item.resolved]
        unresolved_share = len(unresolved) / len(wrong_words) if wrong_words else 0.0
        if unresolved:
            patterns.append(
                ErrorPatternOut(
                    kind="status",
                    label="未解决错词",
                    evidence=f"错词本中仍有 {len(unresolved)} 个未解决词",
                    hit_count=len(unresolved),
                    severity=self._severity(unresolved_share),
                )
            )

        focus_words = [
            FocusWordOut(
                word_id=item.word_id,
                spelling=item.spelling,
                wrong_count=item.wrong_count,
                resolved=item.resolved,
            )
            for item in sorted(
                wrong_words,
                key=lambda item: (
                    item.resolved,
                    -item.wrong_count,
                    -(item.last_wrong_at or datetime(1970, 1, 1)).timestamp(),
                ),
            )[:10]
        ]
        error_control = _score(100 - unresolved_share * 60 - repeated_share * 40)
        pattern_stability = _score(100 - length_share * 50 - prefix_share * 50)
        metrics = [
            _metric("error_control", "错词控制", error_control, "diagnosis"),
            _metric("pattern_stability", "错误分散", pattern_stability, "diagnosis"),
        ]

        tags = [item.label for item in patterns[:4]]
        risks = [item.evidence for item in patterns if item.severity != "low"][:3]
        if not wrong_words:
            tags.append("错词较少")
            summary = "当前错词本为空，暂未发现稳定的长度或前缀错误模式。"
        else:
            summary = (
                f"错词本共 {len(wrong_words)} 个词、累计 {total_wrong_hits} 次错误；"
                f"未解决 {len(unresolved)} 个，高频错词为"
                f"{'、'.join(item.spelling for item in focus_words[:3]) or '暂无'}。"
            )
        return DiagnosisExpertOut(
            source="heuristic",
            summary=summary,
            tags=tags[:5],
            error_patterns=patterns,
            focus_words=focus_words,
            metrics=metrics,
            risks=risks,
        )

    @staticmethod
    def _top_group(groups: dict[str, int]) -> tuple[str | None, int]:
        if not groups:
            return None, 0
        return max(groups.items(), key=lambda item: item[1])

    @staticmethod
    def _severity(share: float) -> str:
        if share >= 0.5:
            return "high"
        if share >= 0.3:
            return "medium"
        return "low"

    def merge_refined(
        self,
        refined: DiagnosisExpertOut,
        fallback: DiagnosisExpertOut,
    ) -> DiagnosisExpertOut:
        return fallback.model_copy(
            update={
                "source": "llm",
                "summary": refined.summary,
                "tags": refined.tags[:5],
                "risks": refined.risks,
            }
        )


class PlannerExpert(BaseProfileExpert[PlannerExpertOut]):
    key = "planner"
    role_prompt = PLANNER_SYSTEM_PROMPT
    output_type = PlannerExpertOut

    def build_fallback(self, blackboard: Blackboard) -> PlannerExpertOut:
        data = blackboard.artifacts.get("data")
        habit = blackboard.artifacts.get("habit")
        diagnosis = blackboard.artifacts.get("diagnosis")
        if not all(
            isinstance(item, expected)
            for item, expected in (
                (data, DataExpertOut),
                (habit, HabitExpertOut),
                (diagnosis, DiagnosisExpertOut),
            )
        ):
            raise RuntimeError("planner requires data, habit and diagnosis artifacts")

        assert isinstance(data, DataExpertOut)
        assert isinstance(habit, HabitExpertOut)
        assert isinstance(diagnosis, DiagnosisExpertOut)

        focus = [item.spelling for item in diagnosis.focus_words[:7]]
        if not focus:
            focus = [
                item.spelling
                for item in sorted(
                    blackboard.word_progress,
                    key=lambda item: (item.mastery_level, -item.wrong_count),
                )[:7]
            ]
        if not focus:
            focus = ["基础词汇"]

        plan_templates = [
            ("错词重练", "复习错词本中的高频词，先听音再默写，完成后订正"),
            ("前缀辨析", "按前缀分组整理易错词，用词根联想进行区分"),
            ("短时默写", "进行一次 10 分钟限时默写，记录正确率"),
            ("词汇扩展", "学习一组新词并完成两轮即时回忆"),
            ("错题回顾", "复盘本周错词，标记已解决和仍需强化项"),
            ("限时练习", "完成一次 15 分钟综合练习，保持正常答题节奏"),
            ("周测与复盘", "完成周测，比较本周正确率并调整下周目标"),
        ]
        review_plan = [
            ReviewPlanItemOut(
                day=index,
                title=title,
                activity=activity,
                word_count=10 if index in (1, 3, 5, 6, 7) else 8,
                focus_words=[focus[(index - 1 + offset) % len(focus)] for offset in range(2)],
            )
            for index, (title, activity) in enumerate(plan_templates, start=1)
        ]

        accuracy_metric = next(
            (item.score for item in data.metrics if item.key == "accuracy"),
            0,
        )
        consistency_metric = next(
            (item.score for item in habit.metrics if item.key == "consistency"),
            0,
        )
        weekly_sessions = max(
            3,
            min(6, round(sum(item.sessions for item in habit.weekly_frequency[-4:]) / 4)),
        )
        target_accuracy = min(95, max(accuracy_metric + 5, 60))
        weekly_goals = [
            f"本周完成至少 {weekly_sessions} 次练习",
            f"优先复习 {min(30, max(10, len(focus) * 3))} 个错词",
            f"将整体正确率提升到 {target_accuracy}% 左右",
        ]

        recommendations: list[str] = []
        if accuracy_metric < 70:
            recommendations.append("先保证短时默写正确率，再逐步增加新词数量")
        if consistency_metric < 60:
            recommendations.append("固定 3 个学习时段，优先建立稳定打卡而非拉长单次时长")
        if diagnosis.error_patterns:
            recommendations.append(f"优先处理“{diagnosis.error_patterns[0].label}”")
        if habit.average_duration_minutes > 30:
            recommendations.append("将单次练习拆成 2 个 15 分钟任务，降低疲劳")
        elif 0 < habit.average_duration_minutes < 8:
            recommendations.append("单次练习逐步延长到 15 分钟，增加有效回忆次数")
        recommendations.append(f"本周核心词：{'、'.join(focus[:5])}")

        metric_scores = [
            item.score
            for item in [*data.metrics, *habit.metrics, *diagnosis.metrics]
        ]
        readiness = sum(metric_scores) / len(metric_scores) if metric_scores else 0
        metrics = [
            _metric("plan_readiness", "规划就绪度", readiness, "planner"),
            _metric(
                "review_coverage",
                "复习覆盖",
                min(100, len(focus) * 12 + 30),
                "planner",
            ),
        ]
        tags = ["7 天计划", "错词优先"]
        if consistency_metric < 60:
            tags.append("习惯巩固")
        if accuracy_metric < 70:
            tags.append("正确率提升")

        primary_pattern = (
            diagnosis.error_patterns[0].label if diagnosis.error_patterns else "错词较少"
        )
        summary = (
            f"结合正确率 {accuracy_metric}%、打卡稳定度 {consistency_metric}% 和"
            f"首要诊断“{primary_pattern}”，规划 7 天轻量复习节奏，核心覆盖 {len(focus)} 个词。"
        )
        return PlannerExpertOut(
            source="heuristic",
            summary=summary,
            tags=tags[:5],
            review_plan=review_plan,
            weekly_goals=weekly_goals,
            recommendations=recommendations[:5],
            metrics=metrics,
        )

    def merge_refined(
        self,
        refined: PlannerExpertOut,
        fallback: PlannerExpertOut,
    ) -> PlannerExpertOut:
        valid_plan = [item.day for item in refined.review_plan] == list(range(1, 8))
        return fallback.model_copy(
            update={
                "source": "llm",
                "summary": refined.summary,
                "tags": refined.tags[:5] or fallback.tags,
                "review_plan": refined.review_plan if valid_plan else fallback.review_plan,
                "weekly_goals": refined.weekly_goals or fallback.weekly_goals,
                "recommendations": refined.recommendations or fallback.recommendations,
            }
        )


def build_default_agents(llm: LLMClient | None) -> list[BaseProfileExpert]:
    return [
        DataExpert(llm),
        HabitExpert(llm),
        DiagnosisExpert(llm),
        PlannerExpert(llm),
    ]