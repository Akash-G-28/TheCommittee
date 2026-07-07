import pytest

from the_committee.agents import (
    ChaosAgent,
    FutureMeAgent,
    HeartAgent,
    SkepticAgent,
    WalletAgent,
)
from the_committee.domain import AgentName, Decision, Vote


@pytest.mark.parametrize(
    ("agent", "question", "expected_name", "expected_vote"),
    [
        (WalletAgent(), "Should I spend 28,000 on a chair?", AgentName.WALLET, Vote.NO),
        (
            FutureMeAgent(),
            "Should I take this career course?",
            AgentName.FUTURE_ME,
            Vote.YES,
        ),
        (ChaosAgent(), "Should I try a spontaneous trip?", AgentName.CHAOS, Vote.YES),
        (
            SkepticAgent(),
            "Should I run a small pilot and compare the results?",
            AgentName.SKEPTIC,
            Vote.YES,
        ),
        (
            HeartAgent(),
            "Should I make time for a meaningful family trip?",
            AgentName.HEART,
            Vote.YES,
        ),
    ],
)
def test_deterministic_agent_returns_structured_opinion(
    agent: WalletAgent | FutureMeAgent | ChaosAgent | SkepticAgent | HeartAgent,
    question: str,
    expected_name: AgentName,
    expected_vote: Vote,
) -> None:
    decision = Decision(question=question)

    result = agent.evaluate(decision)

    assert result.decision_id == decision.id
    assert result.agent == expected_name
    assert result.vote == expected_vote
    assert 0 <= result.confidence <= 1
    assert result.key_factors


def test_wallet_ignores_punctuation_when_no_amount_is_present() -> None:
    decision = Decision(question="I want joy and connection, but the timing is unclear.")

    result = WalletAgent().evaluate(decision)

    assert result.vote == Vote.MAYBE
