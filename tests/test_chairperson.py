from the_committee.chairperson import Chairperson
from the_committee.domain import AgentName, AgentOpinion, Decision, Vote


def opinion(decision: Decision, agent: AgentName, vote: Vote, confidence: float) -> AgentOpinion:
    return AgentOpinion(
        decision_id=decision.id,
        agent=agent,
        vote=vote,
        confidence=confidence,
        summary=f"{agent} says {vote}",
        key_factors=(f"{agent} factor",),
    )


def test_chairperson_uses_majority_and_preserves_minority() -> None:
    decision = Decision(question="Should I buy the chair?")
    opinions = [
        opinion(decision, AgentName.WALLET, Vote.NO, 0.9),
        opinion(decision, AgentName.FUTURE_ME, Vote.YES, 0.8),
        opinion(decision, AgentName.CHAOS, Vote.YES, 0.7),
    ]

    verdict = Chairperson().synthesize(decision, opinions)

    assert verdict.vote == Vote.YES
    assert verdict.minority_report is not None
    assert "wallet" in verdict.minority_report


def test_chairperson_rejects_empty_committee() -> None:
    decision = Decision(question="Should I decide?")

    try:
        Chairperson().synthesize(decision, [])
    except ValueError as exc:
        assert "opinion" in str(exc)
    else:
        raise AssertionError("Expected empty committee to be rejected")

