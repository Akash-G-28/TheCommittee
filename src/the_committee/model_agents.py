"""Optional structured-output, model-backed committee implementations."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from the_committee.agents import Agent, ChaosAgent, FutureMeAgent, WalletAgent
from the_committee.chairperson import Chairperson
from the_committee.domain import (
    AgentName,
    AgentOpinion,
    Decision,
    RevisedOpinion,
    Verdict,
    Vote,
)
from the_committee.model_provider import (
    ModelProvider,
    ModelProviderError,
    StructuredModelRequest,
)

AGENT_PROMPT_VERSION = "committee-agent-v1"
CHAIRPERSON_PROMPT_VERSION = "chairperson-v1"


class AgentGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vote: Vote
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=1_000)
    key_factors: tuple[str, ...] = Field(min_length=1, max_length=8)


class VerdictGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vote: Vote
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=2_000)
    deciding_factor: str = Field(min_length=1, max_length=500)
    minority_report: str | None = Field(default=None, max_length=1_000)


class RebuttalGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vote: Vote
    confidence: float = Field(ge=0, le=1)
    rebuttal: str = Field(min_length=1, max_length=1_500)
    evidence_that_would_change: str = Field(min_length=1, max_length=1_000)


class ModelBackedAgent:
    def __init__(
        self,
        *,
        name: AgentName,
        perspective: str,
        provider: ModelProvider,
        fallback: Agent,
        timeout_seconds: float = 15,
    ) -> None:
        self.name = name
        self._perspective = perspective
        self._provider = provider
        self._fallback = fallback
        self._timeout_seconds = timeout_seconds

    def evaluate(self, decision: Decision) -> AgentOpinion:
        request = StructuredModelRequest(
            prompt=_agent_prompt(decision, self.name),
            system_prompt=(
                f"You are {self.name.value} on a personal decision committee. "
                f"Your perspective is: {self._perspective}. Return only the requested structure."
            ),
            prompt_version=AGENT_PROMPT_VERSION,
            response_model=AgentGeneration,
            timeout_seconds=self._timeout_seconds,
        )
        try:
            generated = self._provider.generate(request).output
        except ModelProviderError:
            return self._fallback.evaluate(decision)
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=generated.vote,
            confidence=generated.confidence,
            summary=generated.summary,
            key_factors=generated.key_factors,
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        payload = {
            "decision": decision.model_dump(
                mode="json", include={"question", "category", "context"}
            ),
            "own_opinion": own_opinion.model_dump(mode="json"),
            "other_opinions": [item.model_dump(mode="json") for item in other_opinions],
        }
        request = StructuredModelRequest(
            prompt=f"Reconsider your vote after reviewing peers: {json.dumps(payload)}",
            system_prompt=(
                f"You are {self.name.value}. Rebut other arguments, preserve your distinct "
                "perspective, and state what evidence would change your conclusion."
            ),
            prompt_version=f"{AGENT_PROMPT_VERSION}-rebuttal",
            response_model=RebuttalGeneration,
            timeout_seconds=self._timeout_seconds,
        )
        try:
            generated = self._provider.generate(request).output
        except ModelProviderError:
            return self._fallback.rebut(decision, own_opinion, other_opinions)
        return RevisedOpinion(
            decision_id=decision.id,
            agent=self.name,
            original_vote=own_opinion.vote,
            **generated.model_dump(),
        )


class ModelBackedWalletAgent(ModelBackedAgent):
    def __init__(self, provider: ModelProvider, *, timeout_seconds: float = 15) -> None:
        super().__init__(
            name=AgentName.WALLET,
            perspective="affordability, alternatives, opportunity cost, and financial resilience",
            provider=provider,
            fallback=WalletAgent(),
            timeout_seconds=timeout_seconds,
        )


class ModelBackedFutureMeAgent(ModelBackedAgent):
    def __init__(self, provider: ModelProvider, *, timeout_seconds: float = 15) -> None:
        super().__init__(
            name=AgentName.FUTURE_ME,
            perspective="long-term alignment, consequences, compounding value, and likely regret",
            provider=provider,
            fallback=FutureMeAgent(),
            timeout_seconds=timeout_seconds,
        )


class ModelBackedChaosAgent(ModelBackedAgent):
    def __init__(self, provider: ModelProvider, *, timeout_seconds: float = 15) -> None:
        super().__init__(
            name=AgentName.CHAOS,
            perspective="exploration, spontaneity, emotional upside, safety, and reversibility",
            provider=provider,
            fallback=ChaosAgent(),
            timeout_seconds=timeout_seconds,
        )


class ModelBackedChairperson(Chairperson):
    def __init__(
        self,
        provider: ModelProvider,
        *,
        fallback: Chairperson | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self._provider = provider
        self._fallback = fallback or Chairperson()
        self._timeout_seconds = timeout_seconds

    def synthesize(
        self,
        decision: Decision,
        opinions: list[AgentOpinion],
        revised_opinions: list[RevisedOpinion] | None = None,
    ) -> Verdict:
        if not opinions:
            raise ValueError("At least one opinion is required")
        request = StructuredModelRequest(
            prompt=_chairperson_prompt(decision, opinions, revised_opinions or []),
            system_prompt=(
                "You are the Chairperson. Weigh evidence and disagreement, then return a "
                "grounded verdict with a minority report when dissent exists."
            ),
            prompt_version=CHAIRPERSON_PROMPT_VERSION,
            response_model=VerdictGeneration,
            timeout_seconds=self._timeout_seconds,
        )
        try:
            generated = self._provider.generate(request).output
        except ModelProviderError:
            return self._fallback.synthesize(decision, opinions, revised_opinions)
        return Verdict(decision_id=decision.id, **generated.model_dump())


def model_backed_agents(
    provider: ModelProvider, *, timeout_seconds: float = 15
) -> tuple[Agent, ...]:
    return (
        ModelBackedWalletAgent(provider, timeout_seconds=timeout_seconds),
        ModelBackedFutureMeAgent(provider, timeout_seconds=timeout_seconds),
        ModelBackedChaosAgent(provider, timeout_seconds=timeout_seconds),
    )


def _agent_prompt(decision: Decision, agent: AgentName) -> str:
    payload = decision.model_dump(mode="json", include={"question", "category", "context"})
    return f"Evaluate this decision independently as {agent.value}: {json.dumps(payload)}"


def _chairperson_prompt(
    decision: Decision,
    opinions: list[AgentOpinion],
    revised_opinions: list[RevisedOpinion],
) -> str:
    payload = {
        "decision": decision.model_dump(
            mode="json", include={"question", "category", "context"}
        ),
        "opinions": [opinion.model_dump(mode="json") for opinion in opinions],
        "revised_opinions": [item.model_dump(mode="json") for item in revised_opinions],
    }
    return f"Synthesize this committee record: {json.dumps(payload)}"
