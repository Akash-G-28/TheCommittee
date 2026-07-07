import pytest

from the_committee.agents import WalletAgent
from the_committee.chairperson import Chairperson
from the_committee.domain import AgentName, AgentOpinion, Decision, Vote
from the_committee.model_agents import (
    AGENT_PROMPT_VERSION,
    CHAIRPERSON_PROMPT_VERSION,
    ModelBackedChairperson,
    ModelBackedWalletAgent,
)
from the_committee.model_provider import (
    MalformedModelResponseError,
    MockModelProvider,
    ModelTimeoutError,
    StructuredModelRequest,
)


def test_model_backed_agent_returns_schema_valid_opinion() -> None:
    provider = MockModelProvider(
        [
            {
                "vote": "YES",
                "confidence": 0.77,
                "summary": "The durable benefit justifies the bounded cost.",
                "key_factors": ["daily use", "health"],
            }
        ]
    )
    agent = ModelBackedWalletAgent(provider)
    decision = Decision(question="Should I buy a better desk chair?")

    opinion = agent.evaluate(decision)

    assert opinion.agent == AgentName.WALLET
    assert opinion.vote == Vote.YES
    call = provider.calls[0]
    assert isinstance(call, StructuredModelRequest)
    assert call.prompt_version == AGENT_PROMPT_VERSION


@pytest.mark.parametrize(
    "failure",
    [
        ModelTimeoutError("timed out"),
        MalformedModelResponseError("bad output"),
    ],
)
def test_model_backed_agent_falls_back_deterministically(failure: Exception) -> None:
    provider = MockModelProvider([failure])  # type: ignore[list-item]
    decision = Decision(question="Should I spend 28,000 on a chair?")

    result = ModelBackedWalletAgent(provider).evaluate(decision)
    expected = WalletAgent().evaluate(decision)

    assert result.vote == expected.vote
    assert result.summary == expected.summary


def test_model_backed_chairperson_synthesizes_structured_verdict() -> None:
    provider = MockModelProvider(
        [
            {
                "vote": "MAYBE",
                "confidence": 0.7,
                "summary": "Gather the missing budget evidence first.",
                "deciding_factor": "uncertain affordability",
                "minority_report": "Chaos favors trying a reversible version.",
            }
        ]
    )
    decision = Decision(question="Should I buy the chair?")
    opinions = [
        AgentOpinion(
            decision_id=decision.id,
            agent=AgentName.WALLET,
            vote=Vote.MAYBE,
            confidence=0.6,
            summary="Budget unknown.",
            key_factors=("budget",),
        )
    ]

    verdict = ModelBackedChairperson(provider).synthesize(decision, opinions)

    assert verdict.vote == Vote.MAYBE
    call = provider.calls[0]
    assert isinstance(call, StructuredModelRequest)
    assert call.prompt_version == CHAIRPERSON_PROMPT_VERSION


def test_model_backed_chairperson_falls_back_on_provider_failure() -> None:
    provider = MockModelProvider([ModelTimeoutError("slow")])
    decision = Decision(question="Should I buy the chair?")
    opinion = AgentOpinion(
        decision_id=decision.id,
        agent=AgentName.WALLET,
        vote=Vote.NO,
        confidence=0.9,
        summary="Too expensive.",
        key_factors=("cost",),
    )

    result = ModelBackedChairperson(provider).synthesize(decision, [opinion])
    expected = Chairperson().synthesize(decision, [opinion])

    assert result.vote == expected.vote
    assert result.summary == expected.summary

