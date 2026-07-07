"""Typed agent contract and deterministic committee members."""

from __future__ import annotations

import re
from typing import Protocol

from the_committee.domain import AgentName, AgentOpinion, Decision, RevisedOpinion, Vote


class Agent(Protocol):
    name: AgentName

    def evaluate(self, decision: Decision) -> AgentOpinion: ...

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion: ...


def _text(decision: Decision) -> str:
    return f"{decision.question} {decision.context or ''}".lower()


class WalletAgent:
    name = AgentName.WALLET

    def evaluate(self, decision: Decision) -> AgentOpinion:
        text = _text(decision)
        amounts = [
            float(value.replace(",", ""))
            for value in re.findall(r"\d[\d,]*(?:\.\d+)?", text)
        ]
        amount = max(amounts, default=0)
        if any(word in text for word in ("debt", "loan", "cannot afford", "rent money")):
            vote, confidence = Vote.NO, 0.91
            summary = "Protect essential cash flow before taking on this commitment."
        elif amount >= 25_000:
            vote, confidence = Vote.NO, 0.82
            summary = "The price is substantial enough to require a stronger affordability case."
        elif 0 < amount <= 5_000:
            vote, confidence = Vote.YES, 0.72
            summary = (
                "The cost appears bounded, assuming essentials and savings are already covered."
            )
        else:
            vote, confidence = Vote.MAYBE, 0.58
            summary = "Affordability is unclear without a budget or price benchmark."
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=vote,
            confidence=confidence,
            summary=summary,
            key_factors=("upfront cost", "opportunity cost", "cash-flow safety"),
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        return _deterministic_rebuttal(decision, own_opinion, other_opinions)


class FutureMeAgent:
    name = AgentName.FUTURE_ME

    def evaluate(self, decision: Decision) -> AgentOpinion:
        text = _text(decision)
        positive = ("career", "learn", "health", "exercise", "ergonomic", "save time")
        negative = ("impulse", "temporary", "just because", "skip sleep")
        if any(word in text for word in positive):
            vote, confidence = Vote.YES, 0.8
            summary = "This choice is likely to compound into long-term value."
        elif any(word in text for word in negative):
            vote, confidence = Vote.NO, 0.78
            summary = "The short-term reward is unlikely to serve your longer-term priorities."
        else:
            vote, confidence = Vote.MAYBE, 0.62
            summary = "The long-term outcome depends on whether this supports a durable priority."
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=vote,
            confidence=confidence,
            summary=summary,
            key_factors=("long-term alignment", "future regret", "compounding effects"),
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        return _deterministic_rebuttal(decision, own_opinion, other_opinions)


class ChaosAgent:
    name = AgentName.CHAOS

    def evaluate(self, decision: Decision) -> AgentOpinion:
        text = _text(decision)
        unsafe = ("dangerous", "illegal", "debt", "gamble everything")
        exploratory = ("travel", "adventure", "try", "creative", "spontaneous")
        if any(word in text for word in unsafe):
            vote, confidence = Vote.NO, 0.88
            summary = "Novelty is not worth an irreversible or unsafe downside."
        elif any(word in text for word in exploratory):
            vote, confidence = Vote.YES, 0.84
            summary = "The experience has meaningful exploration value and emotional upside."
        else:
            vote, confidence = Vote.YES, 0.6
            summary = "A reversible experiment may be better than extended over-analysis."
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=vote,
            confidence=confidence,
            summary=summary,
            key_factors=("exploration value", "reversibility", "cost of over-analysis"),
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        return _deterministic_rebuttal(decision, own_opinion, other_opinions)


class SkepticAgent:
    """Tests assumptions, evidence quality, and hidden downside."""

    name = AgentName.SKEPTIC

    def evaluate(self, decision: Decision) -> AgentOpinion:
        text = _text(decision)
        unsupported = ("guaranteed", "everyone says", "probably", "too good to be true")
        testable = ("trial", "pilot", "compare", "evidence", "return policy")
        if any(phrase in text for phrase in unsupported):
            vote, confidence = Vote.NO, 0.81
            summary = "The case leans on an assumption that has not earned your trust yet."
        elif any(word in text for word in testable):
            vote, confidence = Vote.YES, 0.74
            summary = (
                "The claim can be tested cheaply enough to proceed without pretending certainty."
            )
        else:
            vote, confidence = Vote.MAYBE, 0.68
            summary = "The missing evidence matters more than the confidence of the sales pitch."
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=vote,
            confidence=confidence,
            summary=summary,
            key_factors=("quality of evidence", "hidden assumptions", "downside test"),
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        return _deterministic_rebuttal(decision, own_opinion, other_opinions)


class HeartAgent:
    """Represents values, relationships, energy, and emotional honesty."""

    name = AgentName.HEART

    def evaluate(self, decision: Decision) -> AgentOpinion:
        text = _text(decision)
        aligned = ("family", "friend", "joy", "meaningful", "love", "belong")
        draining = ("dread", "resent", "people pleasing", "obligation", "burnout")
        if any(word in text for word in aligned):
            vote, confidence = Vote.YES, 0.79
            summary = "This choice appears to serve a relationship or value worth making room for."
        elif any(word in text for word in draining):
            vote, confidence = Vote.NO, 0.8
            summary = "Your emotional resistance looks like information, not merely inconvenience."
        else:
            vote, confidence = Vote.MAYBE, 0.64
            summary = (
                "The practical case is incomplete until you name what this choice means to you."
            )
        return AgentOpinion(
            decision_id=decision.id,
            agent=self.name,
            vote=vote,
            confidence=confidence,
            summary=summary,
            key_factors=("values alignment", "relational impact", "emotional energy"),
        )

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        return _deterministic_rebuttal(decision, own_opinion, other_opinions)


def deterministic_agents() -> tuple[Agent, ...]:
    return (WalletAgent(), FutureMeAgent(), ChaosAgent())


def available_agents() -> tuple[Agent, ...]:
    return (*deterministic_agents(), SkepticAgent(), HeartAgent())


def _deterministic_rebuttal(
    decision: Decision,
    own_opinion: AgentOpinion,
    other_opinions: tuple[AgentOpinion, ...],
) -> RevisedOpinion:
    strongest_dissent = max(
        (item for item in other_opinions if item.vote != own_opinion.vote),
        key=lambda item: (item.confidence, item.agent.value),
        default=None,
    )
    revised_vote = own_opinion.vote
    confidence = own_opinion.confidence
    if strongest_dissent and strongest_dissent.confidence >= own_opinion.confidence + 0.2:
        revised_vote = Vote.MAYBE
        confidence = round((own_opinion.confidence + strongest_dissent.confidence) / 2, 2)
        rebuttal = (
            f"{own_opinion.agent.value} softens its position after considering "
            f"{strongest_dissent.agent.value}'s higher-confidence objection."
        )
    else:
        rebuttal = (
            f"{own_opinion.agent.value} maintains {own_opinion.vote} after reviewing the "
            "other committee perspectives."
        )
    return RevisedOpinion(
        decision_id=decision.id,
        agent=own_opinion.agent,
        original_vote=own_opinion.vote,
        vote=revised_vote,
        confidence=confidence,
        rebuttal=rebuttal,
        evidence_that_would_change=(
            f"Concrete evidence that changes the assessment of {own_opinion.key_factors[0]}."
        ),
    )
