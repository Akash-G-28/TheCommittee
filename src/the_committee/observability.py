"""Privacy-safe tracing primitives for committee operations."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

SafeAttribute = str | int | float | bool | None
SAFE_ATTRIBUTE_KEYS = {
    "agent",
    "error_type",
    "fallback",
    "input_tokens",
    "latency_ms",
    "model",
    "output_tokens",
    "phase",
    "provider",
    "result_count",
    "round",
    "status",
}


class SpanStatus(StrEnum):
    OK = "OK"
    ERROR = "ERROR"


class TraceSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    trace_id: UUID
    parent_id: UUID | None = None
    name: str = Field(min_length=1)
    decision_id: UUID | None = None
    started_at: datetime
    duration_ms: float = Field(ge=0)
    status: SpanStatus
    attributes: dict[str, SafeAttribute] = Field(default_factory=dict)


class SpanSink(Protocol):
    def record(self, span: TraceSpan) -> None: ...


class InMemorySpanSink:
    """Thread-safe local sink suitable for tests and development inspection."""

    def __init__(self) -> None:
        self._spans: list[TraceSpan] = []
        self._lock = Lock()

    def record(self, span: TraceSpan) -> None:
        with self._lock:
            self._spans.append(span)

    def snapshot(self) -> tuple[TraceSpan, ...]:
        with self._lock:
            return tuple(self._spans)


class NullSpanSink:
    def record(self, span: TraceSpan) -> None:
        pass


class ActiveSpan:
    def __init__(
        self,
        sink: SpanSink,
        name: str,
        *,
        decision_id: UUID | None,
        trace_id: UUID | None,
        parent_id: UUID | None,
        attributes: Mapping[str, SafeAttribute] | None,
    ) -> None:
        self.id = uuid4()
        self.trace_id = trace_id or uuid4()
        self.parent_id = parent_id
        self._sink = sink
        self._name = name
        self._decision_id = decision_id
        self._started_at = datetime.now(UTC)
        self._started = time.perf_counter()
        self._attributes: dict[str, SafeAttribute] = {}
        for key, value in (attributes or {}).items():
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value: SafeAttribute) -> None:
        if key not in SAFE_ATTRIBUTE_KEYS:
            raise ValueError(f"Unsafe trace attribute: {key}")
        self._attributes[key] = value

    def finish(self, error: BaseException | None = None) -> None:
        if error is not None:
            self._attributes["error_type"] = type(error).__name__
        self._sink.record(
            TraceSpan(
                id=self.id,
                trace_id=self.trace_id,
                parent_id=self.parent_id,
                name=self._name,
                decision_id=self._decision_id,
                started_at=self._started_at,
                duration_ms=(time.perf_counter() - self._started) * 1_000,
                status=SpanStatus.ERROR if error else SpanStatus.OK,
                attributes=self._attributes,
            )
        )


class Tracer:
    def __init__(self, sink: SpanSink | None = None) -> None:
        self.sink = sink or NullSpanSink()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        decision_id: UUID | None = None,
        trace_id: UUID | None = None,
        parent_id: UUID | None = None,
        attributes: Mapping[str, SafeAttribute] | None = None,
    ) -> Iterator[ActiveSpan]:
        active = ActiveSpan(
            self.sink,
            name,
            decision_id=decision_id,
            trace_id=trace_id,
            parent_id=parent_id,
            attributes=attributes,
        )
        try:
            yield active
        except BaseException as exc:
            active.finish(exc)
            raise
        else:
            active.finish()
