"""Controller for the profile Blackboard architecture."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from app.services.profile.blackboard import Blackboard, BlackboardEntry


class KnowledgeSource(Protocol):
    """A domain expert that reads and writes only through the blackboard."""

    key: str
    name: str
    expertise: tuple[str, ...]
    depends_on: tuple[str, ...]
    priority: int

    async def analyze(self, blackboard: Blackboard) -> BaseModel: ...


@dataclass(frozen=True)
class ControllerResult:
    iterations: int
    solved: bool
    confidence: float
    missing_sources: list[str]


class BlackboardController:
    """Select eligible knowledge sources, run them and evaluate the solution."""

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold

    @staticmethod
    def _match_score(source: KnowledgeSource, problem_tags: Sequence[str]) -> float:
        if not problem_tags:
            return 0.5
        overlap = set(source.expertise) & set(problem_tags)
        return len(overlap) / len(problem_tags)

    def select_next_ks(
        self,
        problem_tags: Sequence[str],
        knowledge_sources: Sequence[KnowledgeSource],
        blackboard: Blackboard,
    ) -> KnowledgeSource | None:
        """Prefer unspoken, highly relevant sources whose dependencies are ready."""
        completed = set(blackboard.trace)
        eligible = [
            source
            for source in knowledge_sources
            if source.key not in completed and set(source.depends_on).issubset(completed)
        ]
        if not eligible:
            return None

        ranked = sorted(
            eligible,
            key=lambda source: (
                self._match_score(source, problem_tags) * 0.5
                + min(max(source.priority, 0), 100) / 100 * 0.3
                + 0.2
            ),
            reverse=True,
        )
        return ranked[0]

    def evaluate_solution(
        self,
        knowledge_sources: Sequence[KnowledgeSource],
        blackboard: Blackboard,
    ) -> tuple[bool, float, list[str]]:
        entries = {entry.agent_key: entry for entry in blackboard.entries}
        required = [source.key for source in knowledge_sources]
        missing = [key for key in required if key not in entries]
        if missing:
            return False, 0.0, missing
        confidence = sum(entries[key].confidence for key in required) / len(required)
        return confidence >= self.threshold, round(confidence, 3), []

    async def solve(
        self,
        blackboard: Blackboard,
        knowledge_sources: Sequence[KnowledgeSource],
        max_iterations: int | None = None,
    ) -> ControllerResult:
        rounds = max_iterations or max(1, len(knowledge_sources))
        iterations = 0
        for _ in range(rounds):
            source = self.select_next_ks(
                blackboard.problem_tags,
                knowledge_sources,
                blackboard,
            )
            if source is None:
                break
            output = await source.analyze(blackboard)
            entry = BlackboardEntry(
                id=f"{source.key}_{len(blackboard.entries)}",
                source=source.name,
                agent_key=source.key,
                content=output,
                confidence=float(getattr(output, "confidence", 0.5)),
                tags=list(source.expertise),
            )
            blackboard.write(entry)
            blackboard.write_artifact(source.key, output)
            iterations += 1

        solved, confidence, missing = self.evaluate_solution(
            knowledge_sources,
            blackboard,
        )
        blackboard.solution_confidence = confidence
        return ControllerResult(
            iterations=iterations,
            solved=solved,
            confidence=confidence,
            missing_sources=missing,
        )
