from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from the_committee.domain import OutcomeStatus, Vote
from the_committee.orchestration import CommitteeService
from the_committee.outcomes import OutcomeService


def outcome_service(service: CommitteeService) -> OutcomeService:
    repository = service._repository  # noqa: SLF001 - white-box service integration test
    return OutcomeService(repository)


def test_resolved_outcome_scores_final_votes_by_category(service: CommitteeService) -> None:
    decision = service.create_decision(
        question="Should I take this career course?", category="career", context=None
    )
    result = service.deliberate(decision.id)
    outcomes = outcome_service(service)
    outcomes.record(
        decision.id,
        actual_action="Enrolled",
        actual_choice=Vote.YES,
        status=OutcomeStatus.RESOLVED,
        follow_up_date=date(2026, 8, 1),
        satisfaction_score=9,
        regret_score=1,
        reflection="The course was useful.",
    )

    scores = outcomes.score_decision(decision.id)
    report = outcomes.performance(category="career")

    final_votes = {item.agent: item.vote for item in result.revised_opinions}
    assert all(item.final_vote == final_votes[item.agent] for item in scores)
    assert report.resolved_decisions == 1
    assert len(report.agent_performance) == 3
    assert report.calibration


def test_unresolved_outcomes_are_excluded(service: CommitteeService) -> None:
    decision = service.create_decision(
        question="Should I try climbing?", category="fitness", context=None
    )
    service.deliberate(decision.id)
    outcomes = outcome_service(service)
    outcomes.record(
        decision.id,
        actual_action="Not decided yet",
        actual_choice=None,
        status=OutcomeStatus.FOLLOW_UP_DUE,
        follow_up_date=date(2026, 8, 1),
        satisfaction_score=None,
        regret_score=None,
        reflection="I will revisit this next month.",
    )

    assert outcomes.score_decision(decision.id) == []
    assert outcomes.performance().resolved_decisions == 0


def test_poor_outcome_rewards_agents_that_opposed_actual_choice(
    service: CommitteeService,
) -> None:
    decision = service.create_decision(
        question="Should I spend 28,000 impulsively?", category="purchase", context=None
    )
    service.deliberate(decision.id)
    outcomes = outcome_service(service)
    outcomes.record(
        decision.id,
        actual_action="Bought it",
        actual_choice=Vote.YES,
        status=OutcomeStatus.RESOLVED,
        follow_up_date=None,
        satisfaction_score=2,
        regret_score=9,
        reflection="I regret the purchase.",
    )

    scores = outcomes.score_decision(decision.id)

    assert all(
        item.score == (0.5 if item.final_vote == Vote.MAYBE else float(item.final_vote == Vote.NO))
        for item in scores
    )


def test_outcome_api_and_performance_endpoint(client: TestClient) -> None:
    created = client.post(
        "/decisions", json={"question": "Should I learn pottery?", "category": "career"}
    ).json()
    client.post(f"/decisions/{created['id']}/deliberate")

    response = client.post(
        f"/decisions/{created['id']}/outcome",
        json={
            "actual_action": "Joined the class",
            "actual_choice": "YES",
            "status": "RESOLVED",
            "satisfaction_score": 8,
            "regret_score": 1,
            "reflection": "I learned a useful skill.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
    performance = client.get("/committee/performance?category=career")
    assert performance.status_code == 200
    assert performance.json()["resolved_decisions"] == 1

