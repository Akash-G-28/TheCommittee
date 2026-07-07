"""A2A 1.0 server and replaceable remote boundary for Wallet."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any, Protocol

import httpx
from a2a.client import ClientConfig, create_client
from a2a.helpers.proto_helpers import (
    get_data_parts,
    new_data_message,
    new_data_part,
    new_task_from_user_message,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.fastapi_routes import add_a2a_routes_to_fastapi
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    TaskState,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from a2a.utils.errors import A2AError
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, model_validator

from the_committee.agents import Agent, WalletAgent
from the_committee.domain import AgentName, AgentOpinion, Decision, RevisedOpinion


class WalletOperation(StrEnum):
    EVALUATE = "evaluate"
    REBUT = "rebut"


class WalletTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: WalletOperation
    decision: Decision
    own_opinion: AgentOpinion | None = None
    other_opinions: tuple[AgentOpinion, ...] = ()

    @model_validator(mode="after")
    def validate_rebuttal_input(self) -> WalletTaskRequest:
        if self.operation == WalletOperation.REBUT and self.own_opinion is None:
            raise ValueError("rebut requires own_opinion")
        return self


class WalletTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    state: str
    artifact: dict[str, object]


class RemoteWalletError(RuntimeError):
    pass


class WalletGateway(Protocol):
    async def execute(self, request: WalletTaskRequest) -> WalletTaskResult: ...


class WalletA2AExecutor(AgentExecutor):
    def __init__(self, wallet: Agent | None = None) -> None:
        self._wallet = wallet or WalletAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.task_id is None or context.context_id is None or context.message is None:
            raise ValueError("A2A request is missing task context")
        data_parts = get_data_parts(context.message.parts)
        if len(data_parts) != 1:
            raise ValueError("Wallet expects one structured data part")
        request = WalletTaskRequest.model_validate(data_parts[0])
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await event_queue.enqueue_event(new_task_from_user_message(context.message))
        await updater.start_work()

        if request.operation == WalletOperation.EVALUATE:
            result: AgentOpinion | RevisedOpinion = self._wallet.evaluate(request.decision)
        else:
            if request.own_opinion is None:
                raise ValueError("rebut requires own_opinion")
            result = self._wallet.rebut(
                request.decision, request.own_opinion, request.other_opinions
            )

        await updater.add_artifact(
            [new_data_part(result.model_dump(mode="json"), media_type="application/json")],
            name="wallet-opinion",
            last_chunk=True,
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.task_id is None or context.context_id is None:
            raise ValueError("A2A cancellation is missing task context")
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def wallet_agent_card(base_url: str) -> AgentCard:
    return AgentCard(
        name="The Committee Wallet",
        description="Independent affordability and opportunity-cost committee member.",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=base_url.rstrip("/"),
                protocol_binding=TransportProtocol.HTTP_JSON.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="wallet-deliberation",
                name="Wallet deliberation",
                description="Evaluate a decision or rebut other committee opinions.",
                tags=["affordability", "opportunity-cost", "rebuttal"],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
    )


def create_wallet_a2a_app(
    base_url: str = "http://localhost:8001", wallet: Agent | None = None
) -> FastAPI:
    card = wallet_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=WalletA2AExecutor(wallet),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = FastAPI(title="The Committee Wallet A2A Agent", version="1.0.0")
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        rest_routes=create_rest_routes(handler),
    )
    return app


AsyncClientFactory = Callable[[], httpx.AsyncClient]


class SdkWalletGateway:
    """Official A2A SDK client using the HTTP+JSON/REST binding."""

    def __init__(
        self,
        base_url: str,
        *,
        client_factory: AsyncClientFactory | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_factory = client_factory or (lambda: httpx.AsyncClient())

    async def execute(self, request: WalletTaskRequest) -> WalletTaskResult:
        async with self._client_factory() as http_client:
            client = await create_client(
                self._base_url,
                ClientConfig(
                    streaming=False,
                    httpx_client=http_client,
                    supported_protocol_bindings=[TransportProtocol.HTTP_JSON.value],
                ),
            )
            try:
                message = new_data_message(
                    request.model_dump(mode="json"),
                    media_type="application/json",
                    role=Role.ROLE_USER,
                )
                task = None
                async for event in client.send_message(
                    SendMessageRequest(
                        message=message,
                        configuration=SendMessageConfiguration(return_immediately=False),
                    )
                ):
                    if event.HasField("task"):
                        task = event.task
                if task is None:
                    raise RemoteWalletError("Wallet returned no task")
                if task.status.state != TaskState.TASK_STATE_COMPLETED:
                    raise RemoteWalletError(
                        f"Wallet task ended in {TaskState.Name(task.status.state)}"
                    )
                artifacts = [
                    item
                    for artifact in task.artifacts
                    for item in get_data_parts(artifact.parts)
                ]
                if len(artifacts) != 1 or not isinstance(artifacts[0], dict):
                    raise RemoteWalletError("Wallet returned no structured artifact")
                return WalletTaskResult(
                    task_id=task.id,
                    state=TaskState.Name(task.status.state),
                    artifact=artifacts[0],
                )
            finally:
                await client.close()


class RemoteWalletAgent:
    name = AgentName.WALLET

    def __init__(
        self,
        gateway: WalletGateway,
        *,
        timeout_seconds: float = 5,
        fallback: Agent | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._gateway = gateway
        self._timeout_seconds = timeout_seconds
        self._fallback = fallback
        self.last_task: WalletTaskResult | None = None

    def evaluate(self, decision: Decision) -> AgentOpinion:
        request = WalletTaskRequest(operation=WalletOperation.EVALUATE, decision=decision)
        try:
            result = self._execute(request)
            return AgentOpinion.model_validate(result.artifact)
        except (TimeoutError, RemoteWalletError, A2AError, httpx.HTTPError) as exc:
            if self._fallback is not None:
                return self._fallback.evaluate(decision)
            raise RemoteWalletError("Remote Wallet evaluation failed") from exc

    def rebut(
        self,
        decision: Decision,
        own_opinion: AgentOpinion,
        other_opinions: tuple[AgentOpinion, ...],
    ) -> RevisedOpinion:
        request = WalletTaskRequest(
            operation=WalletOperation.REBUT,
            decision=decision,
            own_opinion=own_opinion,
            other_opinions=other_opinions,
        )
        try:
            result = self._execute(request)
            return RevisedOpinion.model_validate(result.artifact)
        except (TimeoutError, RemoteWalletError, A2AError, httpx.HTTPError) as exc:
            if self._fallback is not None:
                return self._fallback.rebut(decision, own_opinion, other_opinions)
            raise RemoteWalletError("Remote Wallet rebuttal failed") from exc

    def _execute(self, request: WalletTaskRequest) -> WalletTaskResult:
        operation: Coroutine[Any, Any, WalletTaskResult] = self._gateway.execute(request)
        try:
            result = asyncio.run(asyncio.wait_for(operation, self._timeout_seconds))
        except TimeoutError as exc:
            raise TimeoutError("Remote Wallet timed out") from exc
        self.last_task = result
        return result


def build_wallet_agent(
    *,
    remote_url: str | None = None,
    gateway: WalletGateway | None = None,
    timeout_seconds: float = 5,
    fallback: bool = True,
) -> Agent:
    if remote_url is None and gateway is None:
        return WalletAgent()
    remote_gateway = gateway or SdkWalletGateway(remote_url or "")
    return RemoteWalletAgent(
        remote_gateway,
        timeout_seconds=timeout_seconds,
        fallback=WalletAgent() if fallback else None,
    )


app = create_wallet_a2a_app()
