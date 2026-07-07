"""Application service coordinating decision lifecycle and committee execution."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from the_committee.agents import Agent
from the_committee.chairperson import Chairperson
from the_committee.domain import (
    CORE_AGENT_ROSTER,
    AgentName,
    AgentOpinion,
    DebateRound,
    DebateRoundStatus,
    Decision,
    DecisionStatus,
    RevisedOpinion,
    Verdict,
)
from the_committee.observability import ActiveSpan, Tracer
from the_committee.persistence import DecisionRepository


class DecisionNotFoundError(LookupError):
    pass


class DecisionDetail(BaseModel):
    decision: Decision
    opinions: list[AgentOpinion] = Field(default_factory=list)
    rounds: list[DebateRound] = Field(default_factory=list)
    revised_opinions: list[RevisedOpinion] = Field(default_factory=list)
    verdict: Verdict | None = None


class CommitteeService:
    def __init__(
        self,
        repository: DecisionRepository,
        agents: tuple[Agent, ...],
        chairperson: Chairperson,
        tracer: Tracer | None = None,
    ) -> None:
        self._repository = repository
        self._agents = agents
        self._chairperson = chairperson
        self._tracer = tracer or Tracer()

    def create_decision(
        self,
        *,
        question: str,
        category: str,
        context: str | None,
        agent_roster: tuple[AgentName, ...] = CORE_AGENT_ROSTER,
    ) -> Decision:
        return self._repository.create(
            Decision(
                question=question,
                category=category,
                context=context,
                agent_roster=agent_roster,
            )
        )

    def get_decision(self, decision_id: UUID) -> DecisionDetail:
        decision = self._require_decision(decision_id)
        return DecisionDetail(
            decision=decision,
            opinions=self._repository.list_opinions(decision_id),
            rounds=[
                item
                for number in (1, 2)
                if (item := self._repository.get_round(decision_id, number)) is not None
            ],
            revised_opinions=self._repository.list_revised_opinions(decision_id),
            verdict=self._repository.get_verdict(decision_id),
        )

    def deliberate(self, decision_id: UUID) -> DecisionDetail:
        decision = self._require_decision(decision_id)
        if decision.status in {DecisionStatus.VERDICT_READY, DecisionStatus.COMPLETED}:
            return self.get_decision(decision_id)

        with self._tracer.span("decision.run", decision_id=decision_id) as run:
            return self._run_deliberation(decision, run)

    def _run_deliberation(self, decision: Decision, run: ActiveSpan) -> DecisionDetail:
        decision_id = decision.id
        selected_agents = self._selected_agents(decision)
        try:
            if decision.status == DecisionStatus.RECEIVED:
                decision = self._repository.save(
                    decision.transition_to(DecisionStatus.CONTEXT_READY)
                )
            if decision.status in {DecisionStatus.CONTEXT_READY, DecisionStatus.FAILED}:
                decision = self._repository.save(
                    decision.transition_to(DecisionStatus.DELIBERATING)
                )

            round_one = self._repository.get_round(decision_id, 1)
            if round_one is None:
                round_one = self._repository.save_round(
                    DebateRound(decision_id=decision_id, round_number=1)
                )
            if round_one.status != DebateRoundStatus.COMPLETE:
                with self._tracer.span(
                    "debate.round",
                    decision_id=decision_id,
                    trace_id=run.trace_id,
                    parent_id=run.id,
                    attributes={"round": 1},
                ) as round_span:
                    existing_agents = {
                        opinion.agent
                        for opinion in self._repository.list_opinions(decision_id)
                    }
                    for agent in selected_agents:
                        if agent.name not in existing_agents:
                            with self._tracer.span(
                                "agent.execute",
                                decision_id=decision_id,
                                trace_id=run.trace_id,
                                parent_id=round_span.id,
                                attributes={"agent": agent.name.value, "phase": "evaluate"},
                            ):
                                self._repository.add_opinion(agent.evaluate(decision))
                    round_one = self._repository.save_round(round_one.complete())

            opinions = self._repository.list_opinions(decision_id)
            round_two = self._repository.get_round(decision_id, 2)
            if round_two is None:
                round_two = self._repository.save_round(
                    DebateRound(decision_id=decision_id, round_number=2)
                )
            if round_two.status != DebateRoundStatus.COMPLETE:
                with self._tracer.span(
                    "debate.round",
                    decision_id=decision_id,
                    trace_id=run.trace_id,
                    parent_id=run.id,
                    attributes={"round": 2},
                ) as round_span:
                    revisions_by_agent = {
                        item.agent
                        for item in self._repository.list_revised_opinions(decision_id)
                    }
                    opinions_by_agent = {item.agent: item for item in opinions}
                    for agent in selected_agents:
                        if agent.name not in revisions_by_agent:
                            own = opinions_by_agent[agent.name]
                            others = tuple(
                                item for item in opinions if item.agent != agent.name
                            )
                            with self._tracer.span(
                                "agent.execute",
                                decision_id=decision_id,
                                trace_id=run.trace_id,
                                parent_id=round_span.id,
                                attributes={"agent": agent.name.value, "phase": "rebut"},
                            ):
                                self._repository.add_revised_opinion(
                                    agent.rebut(decision, own, others)
                                )
                    round_two = self._repository.save_round(round_two.complete())

            revisions = self._repository.list_revised_opinions(decision_id)
            verdict = self._repository.get_verdict(decision_id)
            if verdict is None:
                with self._tracer.span(
                    "agent.execute",
                    decision_id=decision_id,
                    trace_id=run.trace_id,
                    parent_id=run.id,
                    attributes={"agent": "chairperson", "phase": "synthesize"},
                ):
                    verdict = self._repository.save_verdict(
                        self._chairperson.synthesize(decision, opinions, revisions)
                    )
            decision = self._repository.save(
                decision.transition_to(DecisionStatus.VERDICT_READY)
            )
            return DecisionDetail(
                decision=decision,
                opinions=opinions,
                rounds=[round_one, round_two],
                revised_opinions=revisions,
                verdict=verdict,
            )
        except Exception:
            current = self._require_decision(decision_id)
            if current.status != DecisionStatus.FAILED:
                self._repository.save(current.transition_to(DecisionStatus.FAILED))
            raise

    def _selected_agents(self, decision: Decision) -> tuple[Agent, ...]:
        available = {agent.name: agent for agent in self._agents}
        missing = [name for name in decision.agent_roster if name not in available]
        if missing:
            raise ValueError(f"No implementation configured for: {', '.join(missing)}")
        return tuple(available[name] for name in decision.agent_roster)

    def _require_decision(self, decision_id: UUID) -> Decision:
        decision = self._repository.get(decision_id)
        if decision is None:
            raise DecisionNotFoundError(str(decision_id))
        return decision
