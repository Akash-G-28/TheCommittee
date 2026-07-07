from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from the_committee.a2a_wallet import (
    RemoteWalletAgent,
    RemoteWalletError,
    SdkWalletGateway,
    WalletTaskRequest,
    WalletTaskResult,
    build_wallet_agent,
    create_wallet_a2a_app,
)
from the_committee.agents import ChaosAgent, FutureMeAgent, WalletAgent, deterministic_agents
from the_committee.chairperson import Chairperson
from the_committee.domain import Decision, DecisionStatus
from the_committee.orchestration import CommitteeService
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


def asgi_client_factory(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://wallet"
    )


def canonical_opinion(opinion: object) -> dict[str, object]:
    payload = opinion.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        key: payload[key]
        for key in ("decision_id", "agent", "vote", "confidence", "summary", "key_factors")
    }


def test_wallet_agent_card_declares_identity_interface_and_skill() -> None:
    app = create_wallet_a2a_app("http://wallet")

    with TestClient(app) as client:
        response = client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "The Committee Wallet"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "HTTP+JSON"
    assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0"
    assert card["skills"][0]["id"] == "wallet-deliberation"


def test_local_and_remote_wallet_contracts_have_parity() -> None:
    app = create_wallet_a2a_app("http://wallet")
    remote = RemoteWalletAgent(
        SdkWalletGateway("http://wallet", client_factory=lambda: asgi_client_factory(app))
    )
    local = WalletAgent()
    decision = Decision(
        question="Should I spend 28,000 on a chair?",
        category="purchase",
        context="I work from home.",
    )

    local_opinion = local.evaluate(decision)
    remote_opinion = remote.evaluate(decision)
    others = tuple(
        agent.evaluate(decision)
        for agent in deterministic_agents()
        if agent.name != local.name
    )
    local_rebuttal = local.rebut(decision, local_opinion, others)
    remote_rebuttal = remote.rebut(decision, remote_opinion, others)

    assert canonical_opinion(remote_opinion) == canonical_opinion(local_opinion)
    assert remote_rebuttal.model_dump(
        exclude={"id", "created_at"}
    ) == local_rebuttal.model_dump(exclude={"id", "created_at"})
    assert remote.last_task is not None
    assert remote.last_task.state == "TASK_STATE_COMPLETED"
    assert remote.last_task.task_id
    assert remote.last_task.artifact


class SlowGateway:
    async def execute(self, request: WalletTaskRequest) -> WalletTaskResult:
        await asyncio.sleep(0.05)
        raise AssertionError("timeout should cancel this coroutine")


class FailingGateway:
    async def execute(self, request: WalletTaskRequest) -> WalletTaskResult:
        raise RemoteWalletError("remote unavailable")


def test_remote_wallet_timeout_falls_back_to_local() -> None:
    decision = Decision(question="Should I travel?", category="travel")
    remote = RemoteWalletAgent(SlowGateway(), timeout_seconds=0.001, fallback=WalletAgent())

    assert canonical_opinion(remote.evaluate(decision)) == canonical_opinion(
        WalletAgent().evaluate(decision)
    )


def test_remote_wallet_failure_falls_back_to_local() -> None:
    decision = Decision(question="Should I travel?", category="travel")
    remote = RemoteWalletAgent(FailingGateway(), fallback=WalletAgent())

    assert canonical_opinion(remote.evaluate(decision)) == canonical_opinion(
        WalletAgent().evaluate(decision)
    )


def test_remote_wallet_can_complete_end_to_end_deliberation(tmp_path: Path) -> None:
    app = create_wallet_a2a_app("http://wallet")
    wallet = build_wallet_agent(
        gateway=SdkWalletGateway(
            "http://wallet", client_factory=lambda: asgi_client_factory(app)
        ),
        fallback=False,
    )
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'a2a.db'}")
    Base.metadata.create_all(engine)
    service = CommitteeService(
        SqlAlchemyDecisionRepository(sessions),
        (wallet, FutureMeAgent(), ChaosAgent()),
        Chairperson(),
    )
    decision = service.create_decision(
        question="Should I buy an ergonomic chair for 28,000?",
        category="purchase",
        context="I work from home.",
    )

    result = service.deliberate(decision.id)

    assert result.decision.status == DecisionStatus.VERDICT_READY
    assert len(result.opinions) == 3
    assert result.verdict is not None
