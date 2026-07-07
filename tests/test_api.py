from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/decisions",
        headers={
            "Origin": "http://localhost:4173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4173"


def test_decision_workflow(client: TestClient) -> None:
    create_response = client.post(
        "/decisions",
        json={
            "question": "Should I spend 28,000 on an ergonomic chair?",
            "category": "purchase",
            "context": "I sit for eight hours a day.",
        },
    )
    assert create_response.status_code == 201
    decision_id = create_response.json()["id"]

    deliberate_response = client.post(f"/decisions/{decision_id}/deliberate")
    assert deliberate_response.status_code == 200
    payload = deliberate_response.json()
    assert payload["decision"]["status"] == "VERDICT_READY"
    assert len(payload["opinions"]) == 3
    assert payload["verdict"] is not None

    get_response = client.get(f"/decisions/{decision_id}")
    assert get_response.status_code == 200
    assert get_response.json() == payload


def test_decision_can_select_alternative_committee_members(client: TestClient) -> None:
    create_response = client.post(
        "/decisions",
        json={
            "question": "Should I plan a meaningful family trip?",
            "category": "travel",
            "agent_roster": ["future_me", "skeptic", "heart"],
        },
    )

    assert create_response.status_code == 201
    decision = create_response.json()
    assert decision["agent_roster"] == ["future_me", "skeptic", "heart"]

    response = client.post(f"/decisions/{decision['id']}/deliberate")
    assert response.status_code == 200
    assert {item["agent"] for item in response.json()["opinions"]} == {
        "future_me",
        "skeptic",
        "heart",
    }


def test_missing_decision_returns_404(client: TestClient) -> None:
    response = client.get("/decisions/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_invalid_create_payload_returns_422(client: TestClient) -> None:
    response = client.post("/decisions", json={"question": "x"})

    assert response.status_code == 422
