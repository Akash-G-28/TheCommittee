from collections.abc import Callable

import pytest
from pydantic import BaseModel, Field

from the_committee.model_provider import (
    MalformedModelResponseError,
    MockModelProvider,
    ModelProviderError,
    ModelTimeoutError,
    ProviderConfig,
    ProviderMode,
    RetryingModelProvider,
    StructuredModelRequest,
    TransientModelProviderError,
    build_model_provider,
)


class ExampleOutput(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)


def request() -> StructuredModelRequest[ExampleOutput]:
    return StructuredModelRequest(
        prompt="Return a structured answer",
        response_model=ExampleOutput,
        timeout_seconds=2,
    )


def assert_provider_contract(provider_factory: Callable[[], MockModelProvider]) -> None:
    provider = provider_factory()

    response = provider.generate(request())

    assert response.output == ExampleOutput(answer="yes", confidence=0.8)
    assert response.model.provider
    assert response.model.model
    assert response.model.latency_ms >= 0
    assert response.usage is not None
    assert response.usage.input_tokens is not None


def test_mock_provider_satisfies_provider_contract() -> None:
    assert_provider_contract(
        lambda: MockModelProvider([{"answer": "yes", "confidence": 0.8}])
    )


def test_mock_provider_rejects_malformed_structured_output() -> None:
    provider = MockModelProvider([{"answer": "yes", "confidence": 2}])

    with pytest.raises(MalformedModelResponseError):
        provider.generate(request())


def test_retry_provider_retries_transient_failures_with_backoff() -> None:
    provider = MockModelProvider(
        [
            TransientModelProviderError("busy"),
            ModelTimeoutError("slow"),
            {"answer": "yes", "confidence": 0.9},
        ]
    )
    delays: list[float] = []
    retrying = RetryingModelProvider(
        provider, max_attempts=3, base_delay_seconds=0.25, sleep=delays.append
    )

    response = retrying.generate(request())

    assert response.output.answer == "yes"
    assert delays == [0.25, 0.5]
    assert len(provider.calls) == 3


def test_retry_provider_does_not_retry_permanent_failure() -> None:
    provider = MockModelProvider(
        [ModelProviderError("invalid request"), {"answer": "yes", "confidence": 0.9}]
    )
    retrying = RetryingModelProvider(
        provider, max_attempts=3, base_delay_seconds=0, sleep=lambda _: None
    )

    with pytest.raises(ModelProviderError, match="invalid request"):
        retrying.generate(request())

    assert len(provider.calls) == 1


def test_provider_configuration_from_environment() -> None:
    config = ProviderConfig.from_environment(
        {
            "COMMITTEE_PROVIDER_MODE": "mock",
            "COMMITTEE_PROVIDER_NAME": "contract-test",
            "COMMITTEE_MODEL_NAME": "mock-v2",
            "COMMITTEE_MODEL_TIMEOUT_SECONDS": "5",
            "COMMITTEE_MODEL_MAX_ATTEMPTS": "2",
            "COMMITTEE_MODEL_RETRY_BASE_DELAY_SECONDS": "0",
        }
    )

    assert config.mode == ProviderMode.MOCK
    assert config.provider_name == "contract-test"
    assert config.model_name == "mock-v2"
    assert config.timeout_seconds == 5
    assert config.max_attempts == 2
    assert build_model_provider(config, [{"answer": "yes", "confidence": 1}]) is not None


def test_deterministic_mode_requires_no_provider() -> None:
    assert build_model_provider(ProviderConfig()) is None

