"""SQLAlchemy models and repository implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from the_committee.domain import (
    AgentName,
    AgentOpinion,
    DebateRound,
    DebateRoundStatus,
    Decision,
    DecisionStatus,
    OutcomeMemory,
    OutcomeStatus,
    RevisedOpinion,
    Verdict,
    Vote,
)


class Base(DeclarativeBase):
    pass


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(80))
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_roster_json: Mapped[str] = mapped_column(
        Text, default='["wallet", "future_me", "chaos"]'
    )
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opinions: Mapped[list[OpinionRecord]] = relationship(cascade="all, delete-orphan")
    verdict: Mapped[VerdictRecord | None] = relationship(cascade="all, delete-orphan")


class OpinionRecord(Base):
    __tablename__ = "opinions"
    __table_args__ = (UniqueConstraint("decision_id", "agent", name="uq_opinion_decision_agent"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(32))
    vote: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    key_factors_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerdictRecord(Base):
    __tablename__ = "verdicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), unique=True
    )
    vote: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    deciding_factor: Mapped[str] = mapped_column(String(500))
    minority_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DebateRoundRecord(Base):
    __tablename__ = "debate_rounds"
    __table_args__ = (
        UniqueConstraint("decision_id", "round_number", name="uq_debate_round_decision_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    round_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevisedOpinionRecord(Base):
    __tablename__ = "revised_opinions"
    __table_args__ = (
        UniqueConstraint("decision_id", "agent", name="uq_revision_decision_agent"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(32))
    original_vote: Mapped[str] = mapped_column(String(16))
    vote: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    rebuttal: Mapped[str] = mapped_column(Text)
    evidence_that_would_change: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutcomeMemoryRecord(Base):
    __tablename__ = "outcome_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), unique=True
    )
    actual_action: Mapped[str] = mapped_column(String(500))
    actual_choice: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=OutcomeStatus.PENDING.value)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    satisfaction_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regret_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reflection: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DecisionRepository(Protocol):
    def create(self, decision: Decision) -> Decision: ...
    def get(self, decision_id: UUID) -> Decision | None: ...
    def save(self, decision: Decision) -> Decision: ...
    def add_opinion(self, opinion: AgentOpinion) -> AgentOpinion: ...
    def list_opinions(self, decision_id: UUID) -> list[AgentOpinion]: ...
    def save_verdict(self, verdict: Verdict) -> Verdict: ...
    def get_verdict(self, decision_id: UUID) -> Verdict | None: ...
    def save_round(self, debate_round: DebateRound) -> DebateRound: ...
    def get_round(self, decision_id: UUID, round_number: int) -> DebateRound | None: ...
    def add_revised_opinion(self, opinion: RevisedOpinion) -> RevisedOpinion: ...
    def list_revised_opinions(self, decision_id: UUID) -> list[RevisedOpinion]: ...
    def list_decisions(self, limit: int = 100) -> list[Decision]: ...
    def list_agent_opinions(self, agent: AgentName, limit: int = 100) -> list[AgentOpinion]: ...
    def save_outcome_memory(self, outcome: OutcomeMemory) -> OutcomeMemory: ...
    def get_outcome_memory(self, decision_id: UUID) -> OutcomeMemory | None: ...
    def list_outcome_memories(self) -> list[OutcomeMemory]: ...


class SqlAlchemyDecisionRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create(self, decision: Decision) -> Decision:
        with self._session_factory() as session:
            session.add(_decision_record(decision))
            session.commit()
        return decision

    def get(self, decision_id: UUID) -> Decision | None:
        with self._session_factory() as session:
            record = session.get(DecisionRecord, str(decision_id))
            return _decision_domain(record) if record else None

    def save(self, decision: Decision) -> Decision:
        with self._session_factory() as session:
            record = session.get(DecisionRecord, str(decision.id))
            if record is None:
                raise KeyError(decision.id)
            record.question = decision.question
            record.category = decision.category
            record.context = decision.context
            record.agent_roster_json = json.dumps(decision.agent_roster)
            record.status = decision.status.value
            record.updated_at = decision.updated_at
            session.commit()
        return decision

    def add_opinion(self, opinion: AgentOpinion) -> AgentOpinion:
        with self._session_factory() as session:
            existing = session.query(OpinionRecord).filter_by(
                decision_id=str(opinion.decision_id), agent=opinion.agent.value
            ).one_or_none()
            if existing is not None:
                return _opinion_domain(existing)
            session.add(_opinion_record(opinion))
            session.commit()
        return opinion

    def list_opinions(self, decision_id: UUID) -> list[AgentOpinion]:
        with self._session_factory() as session:
            records = (
                session.query(OpinionRecord)
                .filter_by(decision_id=str(decision_id))
                .order_by(OpinionRecord.agent)
                .all()
            )
            return [_opinion_domain(record) for record in records]

    def save_verdict(self, verdict: Verdict) -> Verdict:
        with self._session_factory() as session:
            existing = session.query(VerdictRecord).filter_by(
                decision_id=str(verdict.decision_id)
            ).one_or_none()
            if existing is not None:
                return _verdict_domain(existing)
            session.add(_verdict_record(verdict))
            session.commit()
        return verdict

    def get_verdict(self, decision_id: UUID) -> Verdict | None:
        with self._session_factory() as session:
            record = session.query(VerdictRecord).filter_by(
                decision_id=str(decision_id)
            ).one_or_none()
            return _verdict_domain(record) if record else None

    def save_round(self, debate_round: DebateRound) -> DebateRound:
        with self._session_factory() as session:
            existing = (
                session.query(DebateRoundRecord)
                .filter_by(
                    decision_id=str(debate_round.decision_id),
                    round_number=debate_round.round_number,
                )
                .one_or_none()
            )
            if existing is None:
                session.add(_round_record(debate_round))
            else:
                existing.status = debate_round.status.value
                existing.completed_at = debate_round.completed_at
            session.commit()
        return debate_round

    def get_round(self, decision_id: UUID, round_number: int) -> DebateRound | None:
        with self._session_factory() as session:
            record = (
                session.query(DebateRoundRecord)
                .filter_by(decision_id=str(decision_id), round_number=round_number)
                .one_or_none()
            )
            return _round_domain(record) if record else None

    def add_revised_opinion(self, opinion: RevisedOpinion) -> RevisedOpinion:
        with self._session_factory() as session:
            existing = (
                session.query(RevisedOpinionRecord)
                .filter_by(decision_id=str(opinion.decision_id), agent=opinion.agent.value)
                .one_or_none()
            )
            if existing is not None:
                return _revised_opinion_domain(existing)
            session.add(_revised_opinion_record(opinion))
            session.commit()
        return opinion

    def list_revised_opinions(self, decision_id: UUID) -> list[RevisedOpinion]:
        with self._session_factory() as session:
            records = (
                session.query(RevisedOpinionRecord)
                .filter_by(decision_id=str(decision_id))
                .order_by(RevisedOpinionRecord.agent)
                .all()
            )
            return [_revised_opinion_domain(record) for record in records]

    def list_decisions(self, limit: int = 100) -> list[Decision]:
        with self._session_factory() as session:
            records = (
                session.query(DecisionRecord)
                .order_by(DecisionRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [_decision_domain(record) for record in records]

    def list_agent_opinions(
        self, agent: AgentName, limit: int = 100
    ) -> list[AgentOpinion]:
        with self._session_factory() as session:
            records = (
                session.query(OpinionRecord)
                .filter_by(agent=agent.value)
                .order_by(OpinionRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [_opinion_domain(record) for record in records]

    def save_outcome_memory(self, outcome: OutcomeMemory) -> OutcomeMemory:
        saved = outcome
        with self._session_factory() as session:
            existing = (
                session.query(OutcomeMemoryRecord)
                .filter_by(decision_id=str(outcome.decision_id))
                .one_or_none()
            )
            if existing is None:
                session.add(_outcome_memory_record(outcome))
            else:
                saved = outcome.model_copy(update={"id": UUID(existing.id)})
                existing.actual_action = outcome.actual_action
                existing.actual_choice = (
                    outcome.actual_choice.value if outcome.actual_choice else None
                )
                existing.status = outcome.status.value
                existing.follow_up_date = outcome.follow_up_date
                existing.satisfaction_score = outcome.satisfaction_score
                existing.regret_score = outcome.regret_score
                existing.reflection = outcome.reflection
                existing.recorded_at = outcome.recorded_at
                existing.resolved_at = outcome.resolved_at
            session.commit()
        return saved

    def get_outcome_memory(self, decision_id: UUID) -> OutcomeMemory | None:
        with self._session_factory() as session:
            record = (
                session.query(OutcomeMemoryRecord)
                .filter_by(decision_id=str(decision_id))
                .one_or_none()
            )
            return _outcome_memory_domain(record) if record else None

    def list_outcome_memories(self) -> list[OutcomeMemory]:
        with self._session_factory() as session:
            records = (
                session.query(OutcomeMemoryRecord)
                .order_by(OutcomeMemoryRecord.recorded_at.desc())
                .all()
            )
            return [_outcome_memory_domain(record) for record in records]


def create_database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    return engine, sessionmaker(engine, expire_on_commit=False)


def _decision_record(item: Decision) -> DecisionRecord:
    return DecisionRecord(
        id=str(item.id),
        question=item.question,
        category=item.category,
        context=item.context,
        agent_roster_json=json.dumps(item.agent_roster),
        status=item.status.value,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _decision_domain(item: DecisionRecord) -> Decision:
    return Decision(
        id=UUID(item.id),
        question=item.question,
        category=item.category,
        context=item.context,
        agent_roster=tuple(AgentName(name) for name in json.loads(item.agent_roster_json)),
        status=DecisionStatus(item.status),
        created_at=_as_utc(item.created_at),
        updated_at=_as_utc(item.updated_at),
    )


def _opinion_record(item: AgentOpinion) -> OpinionRecord:
    return OpinionRecord(
        id=str(item.id),
        decision_id=str(item.decision_id),
        agent=item.agent.value,
        vote=item.vote.value,
        confidence=item.confidence,
        summary=item.summary,
        key_factors_json=json.dumps(item.key_factors),
        created_at=_as_utc(item.created_at),
    )


def _opinion_domain(item: OpinionRecord) -> AgentOpinion:
    return AgentOpinion(
        id=UUID(item.id),
        decision_id=UUID(item.decision_id),
        agent=AgentName(item.agent),
        vote=Vote(item.vote),
        confidence=item.confidence,
        summary=item.summary,
        key_factors=tuple(json.loads(item.key_factors_json)),
        created_at=_as_utc(item.created_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _verdict_record(item: Verdict) -> VerdictRecord:
    return VerdictRecord(
        id=str(item.id),
        decision_id=str(item.decision_id),
        vote=item.vote.value,
        confidence=item.confidence,
        summary=item.summary,
        deciding_factor=item.deciding_factor,
        minority_report=item.minority_report,
        created_at=item.created_at,
    )


def _verdict_domain(item: VerdictRecord) -> Verdict:
    return Verdict(
        id=UUID(item.id),
        decision_id=UUID(item.decision_id),
        vote=Vote(item.vote),
        confidence=item.confidence,
        summary=item.summary,
        deciding_factor=item.deciding_factor,
        minority_report=item.minority_report,
        created_at=_as_utc(item.created_at),
    )


def _round_record(item: DebateRound) -> DebateRoundRecord:
    return DebateRoundRecord(
        id=str(item.id),
        decision_id=str(item.decision_id),
        round_number=item.round_number,
        status=item.status.value,
        created_at=item.created_at,
        completed_at=item.completed_at,
    )


def _round_domain(item: DebateRoundRecord) -> DebateRound:
    return DebateRound(
        id=UUID(item.id),
        decision_id=UUID(item.decision_id),
        round_number=item.round_number,
        status=DebateRoundStatus(item.status),
        created_at=_as_utc(item.created_at),
        completed_at=_as_utc(item.completed_at) if item.completed_at else None,
    )


def _revised_opinion_record(item: RevisedOpinion) -> RevisedOpinionRecord:
    return RevisedOpinionRecord(
        id=str(item.id),
        decision_id=str(item.decision_id),
        agent=item.agent.value,
        original_vote=item.original_vote.value,
        vote=item.vote.value,
        confidence=item.confidence,
        rebuttal=item.rebuttal,
        evidence_that_would_change=item.evidence_that_would_change,
        created_at=item.created_at,
    )


def _revised_opinion_domain(item: RevisedOpinionRecord) -> RevisedOpinion:
    return RevisedOpinion(
        id=UUID(item.id),
        decision_id=UUID(item.decision_id),
        agent=AgentName(item.agent),
        original_vote=Vote(item.original_vote),
        vote=Vote(item.vote),
        confidence=item.confidence,
        rebuttal=item.rebuttal,
        evidence_that_would_change=item.evidence_that_would_change,
        created_at=_as_utc(item.created_at),
    )


def _outcome_memory_record(item: OutcomeMemory) -> OutcomeMemoryRecord:
    return OutcomeMemoryRecord(
        id=str(item.id),
        decision_id=str(item.decision_id),
        actual_action=item.actual_action,
        actual_choice=item.actual_choice.value if item.actual_choice else None,
        status=item.status.value,
        follow_up_date=item.follow_up_date,
        satisfaction_score=item.satisfaction_score,
        regret_score=item.regret_score,
        reflection=item.reflection,
        recorded_at=item.recorded_at,
        resolved_at=item.resolved_at,
    )


def _outcome_memory_domain(item: OutcomeMemoryRecord) -> OutcomeMemory:
    return OutcomeMemory(
        id=UUID(item.id),
        decision_id=UUID(item.decision_id),
        actual_action=item.actual_action,
        actual_choice=Vote(item.actual_choice) if item.actual_choice else None,
        status=OutcomeStatus(item.status),
        follow_up_date=item.follow_up_date,
        satisfaction_score=item.satisfaction_score,
        regret_score=item.regret_score,
        reflection=item.reflection,
        recorded_at=_as_utc(item.recorded_at),
        resolved_at=_as_utc(item.resolved_at) if item.resolved_at else None,
    )
