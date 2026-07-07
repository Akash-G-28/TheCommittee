from __future__ import annotations

from pathlib import Path

import pytest

from the_committee.agents import Agent, deterministic_agents
from the_committee.chairperson import Chairperson
from the_committee.domain import (
    AgentName,
    AgentOpinion,
    DebateRoundStatus,
    Decision,
    DecisionStatus,
    RevisedOpinion,
)
from the_committee.orchestration import CommitteeService
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


class FailOnceOnRebuttal:
    def __init__(self, wrapped: Agent) -> None:
        self.name = wrapped.name
        self._wrapped = wrapped
        self._failed = False

    def evaluate(self, decision: Decision) -> AgentOpinion:
        return self._wrapped.evaluate(decision)

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        if not self._failed:
            self._failed = True
            raise RuntimeError("simulated round-two interruption")
        return self._wrapped.rebut(decision, own_opinion, other_opinions)


def make_service(tmp_path: Path, agents: tuple[Agent, ...]) -> CommitteeService:
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'debate.db'}")
    Base.metadata.create_all(engine)
    return CommitteeService(SqlAlchemyDecisionRepository(sessions), agents, Chairperson())


def test_two_round_debate_is_persisted_and_retry_safe(service: CommitteeService) -> None:
    decision = service.create_decision(
        question="Should I take a career course?", category="career", context=None
    )

    first = service.deliberate(decision.id)
    second = service.deliberate(decision.id)

    assert [round_.status for round_ in first.rounds] == [
        DebateRoundStatus.COMPLETE,
        DebateRoundStatus.COMPLETE,
    ]
    assert len(first.revised_opinions) == 3
    assert {item.id for item in first.revised_opinions} == {
        item.id for item in second.revised_opinions
    }


def test_partial_round_failure_resumes_without_duplicate_work(tmp_path: Path) -> None:
    wallet, future_me, chaos = deterministic_agents()
    failing_agents: tuple[Agent, ...] = (
        wallet,
        FailOnceOnRebuttal(future_me),
        chaos,
    )
    service = make_service(tmp_path, failing_agents)
    decision = service.create_decision(
        question="Should I try a weekend trip?", category="travel", context=None
    )

    with pytest.raises(RuntimeError, match="interruption"):
        service.deliberate(decision.id)
    interrupted = service.get_decision(decision.id)
    assert interrupted.decision.status == DecisionStatus.FAILED
    assert len(interrupted.opinions) == 3
    assert len(interrupted.revised_opinions) == 1

    recovered = service.deliberate(decision.id)

    assert recovered.decision.status == DecisionStatus.VERDICT_READY
    assert len(recovered.opinions) == 3
    assert len(recovered.revised_opinions) == 3


def test_agent_execution_order_does_not_change_final_votes(tmp_path: Path) -> None:
    agents = deterministic_agents()
    forward = make_service(tmp_path / "forward", agents)
    reverse = make_service(tmp_path / "reverse", tuple(reversed(agents)))
    first = forward.create_decision(
        question="Should I buy a 28,000 ergonomic chair?",
        category="purchase",
        context="It may improve my health.",
    )
    second = reverse.create_decision(
        question=first.question, category=first.category, context=first.context
    )

    forward_result = forward.deliberate(first.id)
    reverse_result = reverse.deliberate(second.id)

    assert forward_result.verdict is not None
    assert reverse_result.verdict is not None
    assert forward_result.verdict.vote == reverse_result.verdict.vote
    assert {
        (item.agent, item.vote) for item in forward_result.revised_opinions
    } == {(item.agent, item.vote) for item in reverse_result.revised_opinions}
    assert {item.agent for item in forward_result.opinions} == {
        AgentName.WALLET,
        AgentName.FUTURE_ME,
        AgentName.CHAOS,
    }
