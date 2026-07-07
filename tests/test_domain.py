import pytest
from pydantic import ValidationError

from the_committee.domain import AgentName, Decision, DecisionStatus, InvalidStateTransition


def test_valid_decision_state_sequence() -> None:
    decision = Decision(question="Should I learn pottery?")

    decision = decision.transition_to(DecisionStatus.CONTEXT_READY)
    decision = decision.transition_to(DecisionStatus.DELIBERATING)
    decision = decision.transition_to(DecisionStatus.VERDICT_READY)
    decision = decision.transition_to(DecisionStatus.COMPLETED)

    assert decision.status == DecisionStatus.COMPLETED


def test_invalid_decision_transition_is_rejected() -> None:
    decision = Decision(question="Should I learn pottery?")

    with pytest.raises(InvalidStateTransition):
        decision.transition_to(DecisionStatus.VERDICT_READY)


def test_failed_deliberation_can_be_retried() -> None:
    decision = Decision(question="Should I learn pottery?")
    decision = decision.transition_to(DecisionStatus.FAILED)

    retried = decision.transition_to(DecisionStatus.DELIBERATING)

    assert retried.status == DecisionStatus.DELIBERATING


def test_decision_requires_three_distinct_voting_agents() -> None:
    with pytest.raises(ValidationError, match="three distinct agents"):
        Decision(
            question="Should I do this?",
            agent_roster=(AgentName.WALLET, AgentName.WALLET, AgentName.HEART),
        )
