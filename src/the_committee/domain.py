"""Pure domain models and state transition rules."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class DecisionStatus(StrEnum):
    RECEIVED = "RECEIVED"
    CONTEXT_READY = "CONTEXT_READY"
    DELIBERATING = "DELIBERATING"
    VERDICT_READY = "VERDICT_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Vote(StrEnum):
    YES = "YES"
    NO = "NO"
    MAYBE = "MAYBE"


class AgentName(StrEnum):
    WALLET = "wallet"
    FUTURE_ME = "future_me"
    CHAOS = "chaos"
    SKEPTIC = "skeptic"
    HEART = "heart"


CORE_AGENT_ROSTER = (
    AgentName.WALLET,
    AgentName.FUTURE_ME,
    AgentName.CHAOS,
)


class DebateRoundStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"


class OutcomeStatus(StrEnum):
    PENDING = "PENDING"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    RESOLVED = "RESOLVED"


class InvalidStateTransition(ValueError):
    """Raised when a decision attempts an unsupported lifecycle transition."""


ALLOWED_TRANSITIONS: dict[DecisionStatus, frozenset[DecisionStatus]] = {
    DecisionStatus.RECEIVED: frozenset({DecisionStatus.CONTEXT_READY, DecisionStatus.FAILED}),
    DecisionStatus.CONTEXT_READY: frozenset(
        {DecisionStatus.DELIBERATING, DecisionStatus.FAILED}
    ),
    DecisionStatus.DELIBERATING: frozenset(
        {DecisionStatus.VERDICT_READY, DecisionStatus.FAILED}
    ),
    DecisionStatus.VERDICT_READY: frozenset(
        {DecisionStatus.COMPLETED, DecisionStatus.FAILED}
    ),
    DecisionStatus.COMPLETED: frozenset(),
    DecisionStatus.FAILED: frozenset({DecisionStatus.DELIBERATING}),
}


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    question: str = Field(min_length=3, max_length=500)
    category: str = Field(default="general", min_length=1, max_length=80)
    context: str | None = Field(default=None, max_length=4_000)
    agent_roster: tuple[AgentName, ...] = Field(
        default=CORE_AGENT_ROSTER, min_length=3, max_length=3
    )
    status: DecisionStatus = DecisionStatus.RECEIVED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_agent_roster(self) -> Decision:
        if len(set(self.agent_roster)) != len(self.agent_roster):
            raise ValueError("agent_roster must contain three distinct agents")
        return self

    def transition_to(self, target: DecisionStatus) -> Decision:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateTransition(f"Cannot transition from {self.status} to {target}")
        return self.model_copy(update={"status": target, "updated_at": utc_now()})


class AgentOpinion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    agent: AgentName
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=1_000)
    key_factors: tuple[str, ...] = Field(min_length=1, max_length=8)
    created_at: datetime = Field(default_factory=utc_now)


class RevisedOpinion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    agent: AgentName
    original_vote: Vote
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    rebuttal: str = Field(min_length=1, max_length=1_500)
    evidence_that_would_change: str = Field(min_length=1, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)


class DebateRound(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    round_number: int = Field(ge=1, le=2)
    status: DebateRoundStatus = DebateRoundStatus.IN_PROGRESS
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    def complete(self) -> DebateRound:
        return self.model_copy(
            update={"status": DebateRoundStatus.COMPLETE, "completed_at": utc_now()}
        )


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=2_000)
    deciding_factor: str = Field(min_length=1, max_length=500)
    minority_report: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)


class OutcomeMemory(BaseModel):
    """Minimal outcome note used by the MCP memory boundary before M6 scoring."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    actual_action: str = Field(min_length=1, max_length=500)
    actual_choice: Vote | None = None
    status: OutcomeStatus = OutcomeStatus.PENDING
    follow_up_date: date | None = None
    satisfaction_score: int | None = Field(default=None, ge=0, le=10)
    regret_score: int | None = Field(default=None, ge=0, le=10)
    reflection: str = Field(min_length=1, max_length=4_000)
    recorded_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def require_resolution_scores(self) -> OutcomeMemory:
        if self.status == OutcomeStatus.RESOLVED and (
            self.actual_choice is None
            or self.satisfaction_score is None
            or self.regret_score is None
        ):
            raise ValueError(
                "Resolved outcomes require actual_choice, satisfaction_score, and regret_score"
            )
        return self
