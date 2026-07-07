"""Outcome follow-up and committee performance scoring."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from the_committee.domain import (
    AgentName,
    OutcomeMemory,
    OutcomeStatus,
    Vote,
    utc_now,
)
from the_committee.persistence import DecisionRepository


class AgentScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID
    category: str
    agent: AgentName
    final_vote: Vote
    confidence: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)


class AgentPerformance(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    agent: AgentName
    resolved_count: int
    accuracy: float = Field(ge=0, le=1)


class CalibrationBucket(BaseModel):
    model_config = ConfigDict(frozen=True)

    lower_bound: float
    upper_bound: float
    sample_count: int
    mean_confidence: float
    mean_score: float
    calibration_gap: float


class PerformanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    resolved_decisions: int
    agent_performance: tuple[AgentPerformance, ...]
    calibration: tuple[CalibrationBucket, ...]
    methodology: str


class OutcomeService:
    def __init__(self, repository: DecisionRepository) -> None:
        self._repository = repository

    def record(
        self,
        decision_id: UUID,
        *,
        actual_action: str,
        actual_choice: Vote | None,
        status: OutcomeStatus,
        follow_up_date: date | None,
        satisfaction_score: int | None,
        regret_score: int | None,
        reflection: str,
    ) -> OutcomeMemory:
        if self._repository.get(decision_id) is None:
            raise ValueError(f"Decision {decision_id} was not found")
        existing = self._repository.get_outcome_memory(decision_id)
        outcome = OutcomeMemory(
            id=existing.id if existing else uuid4(),
            decision_id=decision_id,
            actual_action=actual_action,
            actual_choice=actual_choice,
            status=status,
            follow_up_date=follow_up_date,
            satisfaction_score=satisfaction_score,
            regret_score=regret_score,
            reflection=reflection,
            recorded_at=existing.recorded_at if existing else utc_now(),
            resolved_at=utc_now() if status == OutcomeStatus.RESOLVED else None,
        )
        return self._repository.save_outcome_memory(outcome)

    def score_decision(self, decision_id: UUID) -> list[AgentScore]:
        decision = self._repository.get(decision_id)
        outcome = self._repository.get_outcome_memory(decision_id)
        if decision is None or outcome is None or outcome.status != OutcomeStatus.RESOLVED:
            return []
        if outcome.actual_choice is None:
            return []

        revisions = {
            item.agent: item for item in self._repository.list_revised_opinions(decision_id)
        }
        scores: list[AgentScore] = []
        for opinion in self._repository.list_opinions(decision_id):
            revision = revisions.get(opinion.agent)
            final_vote = revision.vote if revision else opinion.vote
            confidence = revision.confidence if revision else opinion.confidence
            scores.append(
                AgentScore(
                    decision_id=decision_id,
                    category=decision.category,
                    agent=opinion.agent,
                    final_vote=final_vote,
                    confidence=confidence,
                    score=_score_vote(final_vote, outcome),
                )
            )
        return scores

    def performance(self, *, category: str | None = None) -> PerformanceReport:
        all_scores: list[AgentScore] = []
        resolved_ids: set[UUID] = set()
        for outcome in self._repository.list_outcome_memories():
            if outcome.status != OutcomeStatus.RESOLVED:
                continue
            decision = self._repository.get(outcome.decision_id)
            if decision is None or (category and decision.category != category):
                continue
            resolved_ids.add(outcome.decision_id)
            all_scores.extend(self.score_decision(outcome.decision_id))

        grouped: dict[tuple[str, AgentName], list[float]] = defaultdict(list)
        for score in all_scores:
            grouped[(score.category, score.agent)].append(score.score)
        performance = tuple(
            AgentPerformance(
                category=group_category,
                agent=agent,
                resolved_count=len(values),
                accuracy=round(sum(values) / len(values), 3),
            )
            for (group_category, agent), values in sorted(
                grouped.items(), key=lambda item: (item[0][0], item[0][1].value)
            )
        )
        return PerformanceReport(
            resolved_decisions=len(resolved_ids),
            agent_performance=performance,
            calibration=_calibration(all_scores),
            methodology=(
                "Final post-rebuttal votes are scored. For a satisfying low-regret outcome, "
                "matching the user's actual choice scores 1; opposing scores 0; MAYBE scores "
                "0.5. For an unsatisfying or high-regret outcome the direction is reversed. "
                "Mixed outcomes score all positions 0.5, and unresolved decisions are excluded."
            ),
        )


def _score_vote(vote: Vote, outcome: OutcomeMemory) -> float:
    assert outcome.actual_choice is not None
    assert outcome.satisfaction_score is not None
    assert outcome.regret_score is not None
    positive = outcome.satisfaction_score >= 6 and outcome.regret_score <= 4
    negative = outcome.satisfaction_score <= 4 or outcome.regret_score >= 6
    if not positive and not negative:
        return 0.5
    if vote == Vote.MAYBE or outcome.actual_choice == Vote.MAYBE:
        return 0.5
    matches = vote == outcome.actual_choice
    return float(matches if positive else not matches)


def _calibration(scores: list[AgentScore]) -> tuple[CalibrationBucket, ...]:
    buckets: dict[int, list[AgentScore]] = defaultdict(list)
    for score in scores:
        bucket = min(int(score.confidence * 5), 4)
        buckets[bucket].append(score)
    result: list[CalibrationBucket] = []
    for bucket, values in sorted(buckets.items()):
        mean_confidence = sum(item.confidence for item in values) / len(values)
        mean_score = sum(item.score for item in values) / len(values)
        result.append(
            CalibrationBucket(
                lower_bound=bucket / 5,
                upper_bound=(bucket + 1) / 5,
                sample_count=len(values),
                mean_confidence=round(mean_confidence, 3),
                mean_score=round(mean_score, 3),
                calibration_gap=round(abs(mean_confidence - mean_score), 3),
            )
        )
    return tuple(result)
