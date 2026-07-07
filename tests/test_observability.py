from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from the_committee.agents import deterministic_agents
from the_committee.chairperson import Chairperson
from the_committee.model_provider import (
    MockModelProvider,
    ObservedModelProvider,
    StructuredModelRequest,
)
from the_committee.observability import InMemorySpanSink, SpanStatus, Tracer
from the_committee.orchestration import CommitteeService
from the_committee.persistence import Base, SqlAlchemyDecisionRepository, create_database


class ExampleOutput(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)


def test_deliberation_emits_nested_privacy_safe_spans(tmp_path: Path) -> None:
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'traces.db'}")
    Base.metadata.create_all(engine)
    sink = InMemorySpanSink()
    service = CommitteeService(
        SqlAlchemyDecisionRepository(sessions),
        deterministic_agents(),
        Chairperson(),
        Tracer(sink),
    )
    decision = service.create_decision(
        question="Should I share a private concern?",
        category="general",
        context="SECRET-CONTEXT",
    )

    service.deliberate(decision.id)

    spans = sink.snapshot()
    assert [span.name for span in spans].count("debate.round") == 2
    assert [span.name for span in spans].count("agent.execute") == 7
    assert [span.name for span in spans].count("decision.run") == 1
    assert len({span.trace_id for span in spans}) == 1
    serialized = " ".join(span.model_dump_json() for span in spans)
    assert "SECRET-CONTEXT" not in serialized
    assert all(span.status == SpanStatus.OK for span in spans)


def test_provider_trace_records_metadata_but_not_prompt() -> None:
    sink = InMemorySpanSink()
    provider = ObservedModelProvider(
        MockModelProvider([{"answer": "yes", "confidence": 0.8}]), Tracer(sink)
    )

    provider.generate(
        StructuredModelRequest(
            prompt="Return a structured answer",
            response_model=ExampleOutput,
            timeout_seconds=2,
        )
    )

    span = sink.snapshot()[0]
    assert span.name == "provider.generate"
    assert span.attributes["input_tokens"] is not None
    assert "Return a structured answer" not in span.model_dump_json()


def test_trace_rejects_unapproved_attributes() -> None:
    with pytest.raises(ValueError, match="Unsafe trace attribute"), Tracer().span(
        "test"
    ) as span:
        span.set_attribute("raw_prompt", "secret")
