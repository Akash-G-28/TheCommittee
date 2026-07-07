"""Replaceable structured model provider boundary."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from the_committee.observability import Tracer


class ModelProviderError(RuntimeError):
    """Base error for failures at the model provider boundary."""


class TransientModelProviderError(ModelProviderError):
    """A safe-to-retry temporary provider failure."""


class ModelTimeoutError(TransientModelProviderError):
    """The provider did not complete within the request timeout."""


class MalformedModelResponseError(ModelProviderError):
    """The provider returned data that violates the requested schema."""


class ProviderMode(StrEnum):
    DETERMINISTIC = "deterministic"
    MOCK = "mock"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: ProviderMode = ProviderMode.DETERMINISTIC
    provider_name: str = Field(default="mock", min_length=1)
    model_name: str = Field(default="committee-mock-v1", min_length=1)
    timeout_seconds: float = Field(default=15, gt=0, le=300)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_delay_seconds: float = Field(default=0.1, ge=0, le=30)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> ProviderConfig:
        values = environ if environ is not None else os.environ
        return cls(
            mode=ProviderMode(
                values.get("COMMITTEE_PROVIDER_MODE", ProviderMode.DETERMINISTIC)
            ),
            provider_name=values.get("COMMITTEE_PROVIDER_NAME", "mock"),
            model_name=values.get("COMMITTEE_MODEL_NAME", "committee-mock-v1"),
            timeout_seconds=float(values.get("COMMITTEE_MODEL_TIMEOUT_SECONDS", "15")),
            max_attempts=int(values.get("COMMITTEE_MODEL_MAX_ATTEMPTS", "3")),
            retry_base_delay_seconds=float(
                values.get("COMMITTEE_MODEL_RETRY_BASE_DELAY_SECONDS", "0.1")
            ),
        )


@dataclass(frozen=True, slots=True)
class StructuredModelRequest[ResponseT: BaseModel]:
    prompt: str
    response_model: type[ResponseT]
    timeout_seconds: float
    system_prompt: str | None = None
    prompt_version: str = "unversioned"

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class ModelMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    latency_ms: float = Field(ge=0)


class UsageMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class StructuredModelResponse[ResponseT: BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True)

    output: ResponseT
    model: ModelMetadata
    usage: UsageMetadata | None = None


class ModelProvider(Protocol):
    def generate[ResponseT: BaseModel](
        self, request: StructuredModelRequest[ResponseT]
    ) -> StructuredModelResponse[ResponseT]: ...


class ObservedModelProvider:
    """Records provider performance without retaining prompts or generated content."""

    def __init__(self, provider: ModelProvider, tracer: Tracer) -> None:
        self._provider = provider
        self._tracer = tracer

    def generate[ResponseT: BaseModel](
        self, request: StructuredModelRequest[ResponseT]
    ) -> StructuredModelResponse[ResponseT]:
        with self._tracer.span("provider.generate") as span:
            response = self._provider.generate(request)
            span.set_attribute("provider", response.model.provider)
            span.set_attribute("model", response.model.model)
            span.set_attribute("latency_ms", response.model.latency_ms)
            if response.usage is not None:
                span.set_attribute("input_tokens", response.usage.input_tokens)
                span.set_attribute("output_tokens", response.usage.output_tokens)
            return response


MockOutput = BaseModel | Mapping[str, object] | ModelProviderError


class MockModelProvider:
    """Deterministic queued provider used by tests and local development."""

    def __init__(
        self,
        outputs: Iterable[MockOutput],
        *,
        provider_name: str = "mock",
        model_name: str = "committee-mock-v1",
    ) -> None:
        self._outputs = iter(outputs)
        self._provider_name = provider_name
        self._model_name = model_name
        self.calls: list[object] = []

    def generate[ResponseT: BaseModel](
        self, request: StructuredModelRequest[ResponseT]
    ) -> StructuredModelResponse[ResponseT]:
        self.calls.append(request)
        started = time.perf_counter()
        try:
            item = next(self._outputs)
        except StopIteration as exc:
            raise ModelProviderError("Mock provider has no queued response") from exc
        if isinstance(item, ModelProviderError):
            raise item

        payload: object = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
        try:
            output = request.response_model.model_validate(payload)
        except ValidationError as exc:
            raise MalformedModelResponseError("Response failed schema validation") from exc

        latency_ms = (time.perf_counter() - started) * 1_000
        return StructuredModelResponse[ResponseT](
            output=output,
            model=ModelMetadata(
                provider=self._provider_name,
                model=self._model_name,
                latency_ms=latency_ms,
            ),
            usage=UsageMetadata(
                input_tokens=len(request.prompt.split()),
                output_tokens=len(output.model_dump_json().split()),
            ),
        )


class RetryingModelProvider:
    """Retries only failures explicitly classified as transient."""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        max_attempts: int,
        base_delay_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must not be negative")
        self._provider = provider
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._sleep = sleep

    def generate[ResponseT: BaseModel](
        self, request: StructuredModelRequest[ResponseT]
    ) -> StructuredModelResponse[ResponseT]:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._provider.generate(request)
            except TransientModelProviderError:
                if attempt == self._max_attempts:
                    raise
                self._sleep(self._base_delay_seconds * (2 ** (attempt - 1)))
        raise AssertionError("Retry loop must return or raise")


def build_model_provider(
    config: ProviderConfig, outputs: Iterable[MockOutput] = ()
) -> ModelProvider | None:
    if config.mode == ProviderMode.DETERMINISTIC:
        return None
    mock = MockModelProvider(
        outputs, provider_name=config.provider_name, model_name=config.model_name
    )
    return RetryingModelProvider(
        mock,
        max_attempts=config.max_attempts,
        base_delay_seconds=config.retry_base_delay_seconds,
    )
