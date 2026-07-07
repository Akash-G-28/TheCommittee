"""Small deterministic evaluation runner for committee contract regression."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from the_committee.agents import Agent, deterministic_agents
from the_committee.chairperson import Chairperson
from the_committee.domain import AgentOpinion, Decision, Verdict

DEFAULT_DATASET = Path(__file__).parents[2] / "evals" / "decisions.json"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    question: str = Field(min_length=3)
    context: str | None = None


class GraderResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    grader: str
    passed: bool
    score: float = Field(ge=0, le=1)
    detail: str


class EvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    opinions: tuple[AgentOpinion, ...]
    verdict: Verdict
    grades: tuple[GraderResult, ...]


class EvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int
    categories: tuple[str, ...]
    results: tuple[EvaluationResult, ...]
    passed: bool
    grader_scores: dict[str, float]


def load_cases(path: Path = DEFAULT_DATASET) -> list[EvaluationCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return TypeAdapter(list[EvaluationCase]).validate_python(data)


def run_evaluation(
    cases: list[EvaluationCase], agents: tuple[Agent, ...] | None = None
) -> EvaluationReport:
    committee = agents or deterministic_agents()
    results: list[EvaluationResult] = []
    for case in cases:
        decision = Decision(
            question=case.question, category=case.category, context=case.context
        )
        opinions = tuple(agent.evaluate(decision) for agent in committee)
        repeated = tuple(agent.evaluate(decision) for agent in committee)
        verdict = Chairperson().synthesize(decision, list(opinions))
        grades = (
            grade_structured_outputs(opinions),
            grade_consistency(opinions, repeated),
            grade_chairperson_grounding(opinions, verdict),
        )
        results.append(
            EvaluationResult(
                case_id=case.id,
                category=case.category,
                opinions=opinions,
                verdict=verdict,
                grades=grades,
            )
        )
    grader_names = ("structured-output", "consistency", "chair-evidence-grounding")
    scores = {
        name: sum(
            grade.score
            for result in results
            for grade in result.grades
            if grade.grader == name
        )
        / len(results)
        if results
        else 0.0
        for name in grader_names
    }
    return EvaluationReport(
        case_count=len(cases),
        categories=tuple(sorted({case.category for case in cases})),
        results=tuple(results),
        passed=bool(results) and all(grade.passed for item in results for grade in item.grades),
        grader_scores=scores,
    )


def grade_structured_outputs(opinions: tuple[AgentOpinion, ...]) -> GraderResult:
    unique_agents = {opinion.agent for opinion in opinions}
    valid = len(opinions) == 3 and len(unique_agents) == 3
    return GraderResult(
        grader="structured-output",
        passed=valid,
        score=1.0 if valid else 0.0,
        detail="Three unique schema-valid committee opinions are required.",
    )


def grade_consistency(
    first: tuple[AgentOpinion, ...], second: tuple[AgentOpinion, ...]
) -> GraderResult:
    def canonical(opinion: AgentOpinion) -> tuple[object, ...]:
        return (
            opinion.agent,
            opinion.vote,
            opinion.confidence,
            opinion.summary,
            opinion.key_factors,
        )

    matches = sum(
        canonical(left) == canonical(right) for left, right in zip(first, second, strict=False)
    )
    denominator = max(len(first), len(second), 1)
    score = matches / denominator if len(first) == len(second) else 0.0
    return GraderResult(
        grader="consistency",
        passed=score == 1.0,
        score=score,
        detail="Repeated deterministic runs must preserve every decision-bearing field.",
    )


def grade_chairperson_grounding(
    opinions: tuple[AgentOpinion, ...], verdict: Verdict
) -> GraderResult:
    evidence = {factor for opinion in opinions for factor in opinion.key_factors}
    grounded = verdict.deciding_factor in evidence
    has_dissent = any(opinion.vote != verdict.vote for opinion in opinions)
    minority_is_consistent = (verdict.minority_report is not None) == has_dissent
    valid = grounded and minority_is_consistent
    return GraderResult(
        grader="chair-evidence-grounding",
        passed=valid,
        score=(float(grounded) + float(minority_is_consistent)) / 2,
        detail="The deciding factor and minority report must be grounded in committee evidence.",
    )


def main() -> None:
    print(run_evaluation(load_cases()).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
