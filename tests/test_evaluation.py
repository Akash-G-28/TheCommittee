from pathlib import Path

from the_committee.evaluation import load_cases, run_evaluation


def test_evaluation_dataset_covers_required_categories() -> None:
    path = Path(__file__).parents[1] / "evals" / "decisions.json"

    report = run_evaluation(load_cases(path))

    assert report.case_count >= 5
    assert set(report.categories) >= {"purchase", "travel", "career", "fitness", "ambiguous"}
    assert all(len(result.opinions) == 3 for result in report.results)
    assert report.passed
    assert report.grader_scores == {
        "structured-output": 1.0,
        "consistency": 1.0,
        "chair-evidence-grounding": 1.0,
    }
