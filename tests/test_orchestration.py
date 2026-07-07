from the_committee.domain import DecisionStatus
from the_committee.orchestration import CommitteeService


def test_orchestration_produces_three_opinions_and_verdict(
    service: CommitteeService,
) -> None:
    decision = service.create_decision(
        question="Should I buy an ergonomic chair for 28,000?",
        category="purchase",
        context="I work from home.",
    )

    result = service.deliberate(decision.id)

    assert result.decision.status == DecisionStatus.VERDICT_READY
    assert len(result.opinions) == 3
    assert result.verdict is not None


def test_deliberation_is_retry_safe_and_prevents_duplicate_opinions(
    service: CommitteeService,
) -> None:
    decision = service.create_decision(
        question="Should I try a pottery class?", category="creative", context=None
    )

    first = service.deliberate(decision.id)
    second = service.deliberate(decision.id)

    assert first.verdict == second.verdict
    assert len(second.opinions) == 3
    assert {item.id for item in first.opinions} == {item.id for item in second.opinions}

