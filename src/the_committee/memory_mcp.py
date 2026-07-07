"""Personal decision memory service exposed through an MCP server."""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Any, Protocol
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from the_committee.domain import (
    AgentName,
    AgentOpinion,
    Decision,
    OutcomeMemory,
    OutcomeStatus,
    RevisedOpinion,
    Verdict,
    Vote,
)
from the_committee.observability import Tracer
from the_committee.outcomes import OutcomeService
from the_committee.persistence import (
    DecisionRepository,
    SqlAlchemyDecisionRepository,
    create_database,
)


class DecisionMemory(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Decision
    opinions: tuple[AgentOpinion, ...]
    revised_opinions: tuple[RevisedOpinion, ...]
    verdict: Verdict | None
    outcome: OutcomeMemory | None


class AgentHistory(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent: AgentName
    opinions: tuple[AgentOpinion, ...]


class RegretPatterns(BaseModel):
    model_config = ConfigDict(frozen=True)

    matching_outcomes: tuple[OutcomeMemory, ...]
    note: str


class ContextBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID
    similar_decisions: tuple[DecisionMemory, ...]


class MemoryService:
    """Application boundary used by MCP tools; agents never receive the repository."""

    def __init__(self, repository: DecisionRepository) -> None:
        self._repository = repository
        self._outcomes = OutcomeService(repository)

    def search_decisions(
        self, *, query: str | None, category: str | None, limit: int
    ) -> list[DecisionMemory]:
        normalized_query = query.casefold().strip() if query else None
        normalized_category = category.casefold().strip() if category else None
        matches: list[DecisionMemory] = []
        for decision in self._repository.list_decisions(limit=500):
            searchable = f"{decision.question} {decision.context or ''}".casefold()
            if normalized_query and normalized_query not in searchable:
                continue
            if normalized_category and decision.category.casefold() != normalized_category:
                continue
            matches.append(self.get_decision(decision.id))
            if len(matches) == limit:
                break
        return matches

    def get_decision(self, decision_id: UUID) -> DecisionMemory:
        decision = self._repository.get(decision_id)
        if decision is None:
            raise ValueError(f"Decision {decision_id} was not found")
        return DecisionMemory(
            decision=decision,
            opinions=tuple(self._repository.list_opinions(decision_id)),
            revised_opinions=tuple(self._repository.list_revised_opinions(decision_id)),
            verdict=self._repository.get_verdict(decision_id),
            outcome=self._repository.get_outcome_memory(decision_id),
        )

    def get_similar_decisions(self, decision_id: UUID, *, limit: int) -> list[DecisionMemory]:
        source = self.get_decision(decision_id).decision
        return [
            item
            for item in self.search_decisions(query=None, category=source.category, limit=limit + 1)
            if item.decision.id != decision_id
        ][:limit]

    def record_outcome(
        self,
        decision_id: UUID,
        *,
        actual_action: str,
        reflection: str,
        actual_choice: Vote | None = None,
        status: OutcomeStatus = OutcomeStatus.PENDING,
        follow_up_date: date | None = None,
        satisfaction_score: int | None = None,
        regret_score: int | None = None,
    ) -> OutcomeMemory:
        return self._outcomes.record(
            decision_id,
            actual_action=actual_action,
            actual_choice=actual_choice,
            status=status,
            follow_up_date=follow_up_date,
            satisfaction_score=satisfaction_score,
            regret_score=regret_score,
            reflection=reflection,
        )

    def get_regret_patterns(self, *, limit: int) -> RegretPatterns:
        outcomes = [
            outcome
            for decision in self._repository.list_decisions(limit=500)
            if (outcome := self._repository.get_outcome_memory(decision.id)) is not None
            and (
                (outcome.regret_score is not None and outcome.regret_score >= 6)
                or "regret" in outcome.reflection.casefold()
            )
        ][:limit]
        return RegretPatterns(
            matching_outcomes=tuple(outcomes),
            note=(
                "Keyword-based preliminary pattern; M6 adds explicit regret scoring."
                if outcomes
                else "No recorded reflections currently mention regret."
            ),
        )

    def get_agent_history(self, agent: AgentName, *, limit: int) -> AgentHistory:
        return AgentHistory(
            agent=agent,
            opinions=tuple(self._repository.list_agent_opinions(agent, limit=limit)),
        )


def create_memory_server(repository: DecisionRepository) -> FastMCP:
    service = MemoryService(repository)
    server = FastMCP(
        "The Committee Personal Memory",
        instructions=(
            "Read personal decision history through explicit tools. Outcome writes are validated "
            "and separated from read-only retrieval tools."
        ),
    )

    @server.tool()
    def search_decisions(
        query: str | None = None,
        category: str | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 10,
    ) -> list[DecisionMemory]:
        """Search decision text and optionally filter by exact category."""
        return service.search_decisions(query=query, category=category, limit=limit)

    @server.tool()
    def get_decision(decision_id: UUID) -> DecisionMemory:
        """Retrieve one decision and its complete deliberation memory."""
        return service.get_decision(decision_id)

    @server.tool()
    def get_similar_decisions(
        decision_id: UUID,
        limit: Annotated[int, Field(ge=1, le=50)] = 5,
    ) -> list[DecisionMemory]:
        """Find prior decisions in the same category."""
        return service.get_similar_decisions(decision_id, limit=limit)

    @server.tool()
    def record_outcome(
        decision_id: UUID,
        actual_action: Annotated[str, Field(min_length=1, max_length=500)],
        reflection: Annotated[str, Field(min_length=1, max_length=4_000)],
        actual_choice: Vote | None = None,
        status: OutcomeStatus = OutcomeStatus.PENDING,
        follow_up_date: date | None = None,
        satisfaction_score: Annotated[int | None, Field(ge=0, le=10)] = None,
        regret_score: Annotated[int | None, Field(ge=0, le=10)] = None,
    ) -> OutcomeMemory:
        """Record the actual action and a user-supplied outcome reflection."""
        return service.record_outcome(
            decision_id,
            actual_action=actual_action,
            reflection=reflection,
            actual_choice=actual_choice,
            status=status,
            follow_up_date=follow_up_date,
            satisfaction_score=satisfaction_score,
            regret_score=regret_score,
        )

    @server.tool()
    def get_regret_patterns(
        limit: Annotated[int, Field(ge=1, le=100)] = 10,
    ) -> RegretPatterns:
        """Return preliminary regret patterns from explicitly recorded outcomes."""
        return service.get_regret_patterns(limit=limit)

    @server.tool()
    def get_agent_history(
        agent: AgentName,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> AgentHistory:
        """Return historical first-round opinions for one committee member."""
        return service.get_agent_history(agent, limit=limit)

    return server


class McpToolCaller(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


class TransientMcpToolError(RuntimeError):
    pass


class InProcessMcpClient:
    """Test/local adapter that still exercises FastMCP registration and validation."""

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        converted: dict[str, Any] = dict(arguments)
        return await self._server.call_tool(name, converted)


class RetryingMcpToolCaller:
    """Retries explicitly transient read-tool failures."""

    def __init__(
        self,
        wrapped: McpToolCaller,
        *,
        max_attempts: int = 3,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._wrapped = wrapped
        self._max_attempts = max_attempts
        self._sleep = sleep

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._wrapped.call_tool(name, arguments)
            except TransientMcpToolError:
                if attempt == self._max_attempts:
                    raise
                await self._sleep(float(2 ** (attempt - 1)))
        raise AssertionError("Retry loop must return or raise")


class ContextPlanner:
    """Retrieves personal context only through the MCP tool-call boundary."""

    def __init__(
        self,
        client: McpToolCaller,
        *,
        similar_limit: int = 3,
        tracer: Tracer | None = None,
    ) -> None:
        self._client = client
        self._similar_limit = similar_limit
        self._tracer = tracer or Tracer()

    async def gather(self, decision: Decision) -> ContextBundle:
        with self._tracer.span(
            "context.retrieve",
            decision_id=decision.id,
            attributes={"provider": "mcp"},
        ) as span:
            raw = await self._client.call_tool(
                "get_similar_decisions",
                {"decision_id": str(decision.id), "limit": self._similar_limit},
            )
            memories = tuple(_parse_decision_memories(raw))
            span.set_attribute("result_count", len(memories))
            return ContextBundle(decision_id=decision.id, similar_decisions=memories)


def _parse_decision_memories(raw: object) -> list[DecisionMemory]:
    if isinstance(raw, dict):
        payload: object = raw.get("structuredContent", raw)
        if isinstance(payload, dict) and "result" in payload:
            payload = payload["result"]
        return TypeAdapter(list[DecisionMemory]).validate_python(payload)
    if isinstance(raw, tuple) and len(raw) == 2:
        payload = raw[1]
        if isinstance(payload, dict) and "result" in payload:
            payload = payload["result"]
        return TypeAdapter(list[DecisionMemory]).validate_python(payload)
    if isinstance(raw, list):
        for block in raw:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return TypeAdapter(list[DecisionMemory]).validate_python(json.loads(text))
    raise ValueError("MCP tool returned an unsupported payload")


def main() -> None:
    database_url = os.getenv("COMMITTEE_DATABASE_URL", "sqlite:///./committee.db")
    _, sessions = create_database(database_url)
    create_memory_server(SqlAlchemyDecisionRepository(sessions)).run(transport="stdio")


if __name__ == "__main__":
    main()
