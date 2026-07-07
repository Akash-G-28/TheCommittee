"""FastAPI composition root and HTTP routes."""

from __future__ import annotations

import os
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from the_committee.a2a_wallet import build_wallet_agent
from the_committee.agents import available_agents
from the_committee.chairperson import Chairperson
from the_committee.domain import (
    CORE_AGENT_ROSTER,
    AgentName,
    Decision,
    OutcomeMemory,
    OutcomeStatus,
    Vote,
)
from the_committee.observability import InMemorySpanSink, Tracer
from the_committee.orchestration import CommitteeService, DecisionDetail, DecisionNotFoundError
from the_committee.outcomes import OutcomeService, PerformanceReport
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


class CreateDecisionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    category: str = Field(default="general", min_length=1, max_length=80)
    context: str | None = Field(default=None, max_length=4_000)
    agent_roster: tuple[AgentName, ...] = Field(
        default=CORE_AGENT_ROSTER, min_length=3, max_length=3
    )

    @model_validator(mode="after")
    def validate_agent_roster(self) -> CreateDecisionRequest:
        if len(set(self.agent_roster)) != len(self.agent_roster):
            raise ValueError("agent_roster must contain three distinct agents")
        return self


class HealthResponse(BaseModel):
    status: str


class RecordOutcomeRequest(BaseModel):
    actual_action: str = Field(min_length=1, max_length=500)
    actual_choice: Vote | None = None
    status: OutcomeStatus = OutcomeStatus.PENDING
    follow_up_date: date | None = None
    satisfaction_score: int | None = Field(default=None, ge=0, le=10)
    regret_score: int | None = Field(default=None, ge=0, le=10)
    reflection: str = Field(min_length=1, max_length=4_000)


def create_app(database_url: str | None = None, *, initialize_schema: bool = True) -> FastAPI:
    app = FastAPI(title="The Committee", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    url = database_url
    if url is None:
        url = os.getenv("COMMITTEE_DATABASE_URL") or "sqlite:///./committee.db"
    engine, session_factory = create_database(url)
    if initialize_schema:
        Base.metadata.create_all(engine)
    repository = SqlAlchemyDecisionRepository(session_factory)
    span_sink = InMemorySpanSink()
    app.state.trace_sink = span_sink
    agents = available_agents()
    wallet_url = os.getenv("COMMITTEE_WALLET_A2A_URL")
    if wallet_url:
        remote_wallet = build_wallet_agent(
            remote_url=wallet_url,
            timeout_seconds=float(os.getenv("COMMITTEE_WALLET_A2A_TIMEOUT_SECONDS", "5")),
        )
        agents = tuple(
            remote_wallet if agent.name == AgentName.WALLET else agent for agent in agents
        )
    app.state.service = CommitteeService(repository, agents, Chairperson(), Tracer(span_sink))
    app.state.outcomes = OutcomeService(repository)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/decisions", response_model=Decision, status_code=status.HTTP_201_CREATED)
    def create_decision(
        payload: CreateDecisionRequest,
        service: Annotated[CommitteeService, Depends(_get_service)],
    ) -> Decision:
        return service.create_decision(
            question=payload.question,
            category=payload.category,
            context=payload.context,
            agent_roster=payload.agent_roster,
        )

    @app.get("/decisions/{decision_id}", response_model=DecisionDetail)
    def get_decision(
        decision_id: UUID,
        service: Annotated[CommitteeService, Depends(_get_service)],
    ) -> DecisionDetail:
        return _or_404(service, decision_id)

    @app.post("/decisions/{decision_id}/deliberate", response_model=DecisionDetail)
    def deliberate(
        decision_id: UUID,
        service: Annotated[CommitteeService, Depends(_get_service)],
    ) -> DecisionDetail:
        try:
            return service.deliberate(decision_id)
        except DecisionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Decision not found") from exc

    @app.post("/decisions/{decision_id}/outcome", response_model=OutcomeMemory)
    def record_outcome(
        decision_id: UUID,
        payload: RecordOutcomeRequest,
        outcomes: Annotated[OutcomeService, Depends(_get_outcome_service)],
    ) -> OutcomeMemory:
        try:
            return outcomes.record(
                decision_id,
                actual_action=payload.actual_action,
                actual_choice=payload.actual_choice,
                status=payload.status,
                follow_up_date=payload.follow_up_date,
                satisfaction_score=payload.satisfaction_score,
                regret_score=payload.regret_score,
                reflection=payload.reflection,
            )
        except ValueError as exc:
            message = str(exc)
            code = 404 if "not found" in message else 422
            raise HTTPException(status_code=code, detail=message) from exc

    @app.get("/committee/performance", response_model=PerformanceReport)
    def committee_performance(
        outcomes: Annotated[OutcomeService, Depends(_get_outcome_service)],
        category: str | None = None,
    ) -> PerformanceReport:
        return outcomes.performance(category=category)

    return app


def _cors_origins() -> list[str]:
    configured = os.getenv("COMMITTEE_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:4173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5173",
    ]


def _get_service(request: Request) -> CommitteeService:
    service: CommitteeService = request.app.state.service
    return service


def _get_outcome_service(request: Request) -> OutcomeService:
    service: OutcomeService = request.app.state.outcomes
    return service


def _or_404(service: CommitteeService, decision_id: UUID) -> DecisionDetail:
    try:
        return service.get_decision(decision_id)
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Decision not found") from exc


app = create_app(initialize_schema=False)
