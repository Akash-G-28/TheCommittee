from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from the_committee.agents import deterministic_agents
from the_committee.chairperson import Chairperson
from the_committee.domain import AgentName
from the_committee.memory_mcp import (
    ContextPlanner,
    DecisionMemory,
    InProcessMcpClient,
    MemoryService,
    RetryingMcpToolCaller,
    TransientMcpToolError,
    create_memory_server,
)
from the_committee.observability import InMemorySpanSink, Tracer
from the_committee.orchestration import CommitteeService
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


def setup_memory(tmp_path: Path) -> tuple[CommitteeService, MemoryService, FastMCP]:
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'memory.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyDecisionRepository(sessions)
    committee = CommitteeService(repository, deterministic_agents(), Chairperson())
    return committee, MemoryService(repository), create_memory_server(repository)


def test_mcp_server_registers_explicit_typed_tool_contracts(tmp_path: Path) -> None:
    _, _, raw_server = setup_memory(tmp_path)
    server = raw_server
    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "search_decisions",
        "get_decision",
        "get_similar_decisions",
        "record_outcome",
        "get_regret_patterns",
        "get_agent_history",
    }
    record_tool = next(tool for tool in tools if tool.name == "record_outcome")
    assert {
        "decision_id",
        "actual_action",
        "reflection",
    } <= set(record_tool.inputSchema["properties"])


def test_memory_tools_read_write_and_agent_history(tmp_path: Path) -> None:
    committee, memory, _ = setup_memory(tmp_path)
    decision = committee.create_decision(
        question="Should I take a weekend trip?", category="travel", context=None
    )
    committee.deliberate(decision.id)

    outcome = memory.record_outcome(
        decision.id,
        actual_action="I went",
        reflection="No regret; the trip was restorative.",
    )
    found = memory.search_decisions(query="weekend", category="travel", limit=10)
    history = memory.get_agent_history(AgentName.WALLET, limit=10)
    patterns = memory.get_regret_patterns(limit=10)

    assert found[0].outcome == outcome
    assert len(history.opinions) == 1
    assert patterns.matching_outcomes == (outcome,)


def test_context_planner_retrieves_similar_decisions_through_mcp(tmp_path: Path) -> None:
    committee, _, raw_server = setup_memory(tmp_path)
    prior = committee.create_decision(
        question="Should I visit Jaipur?", category="travel", context=None
    )
    current = committee.create_decision(
        question="Should I visit Kochi?", category="travel", context=None
    )
    committee.deliberate(prior.id)
    server = raw_server
    sink = InMemorySpanSink()
    planner = ContextPlanner(InProcessMcpClient(server), tracer=Tracer(sink))

    bundle = asyncio.run(planner.gather(current))

    parsed = TypeAdapter(tuple[DecisionMemory, ...]).validate_python(bundle.similar_decisions)
    assert [item.decision.id for item in parsed] == [prior.id]
    span = sink.snapshot()[0]
    assert span.name == "context.retrieve"
    assert span.attributes == {"provider": "mcp", "result_count": 1}


class FlakyClient:
    def __init__(self) -> None:
        self.calls = 0

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls += 1
        if self.calls < 3:
            raise TransientMcpToolError("temporary transport failure")
        return {"ok": True}


def test_mcp_read_retry_policy_recovers_transient_failure() -> None:
    client = FlakyClient()
    delays: list[float] = []

    async def record_delay(delay: float) -> None:
        delays.append(delay)

    retrying = RetryingMcpToolCaller(client, max_attempts=3, sleep=record_delay)

    result = asyncio.run(retrying.call_tool("search_decisions", {}))

    assert result == {"ok": True}
    assert client.calls == 3
    assert delays == [1.0, 2.0]


def test_memory_write_rejects_unknown_decision(tmp_path: Path) -> None:
    _, memory, _ = setup_memory(tmp_path)

    with pytest.raises(ValueError, match="not found"):
        memory.record_outcome(
            UUID("00000000-0000-0000-0000-000000000000"),
            actual_action="Nothing",
            reflection="No decision existed.",
        )
