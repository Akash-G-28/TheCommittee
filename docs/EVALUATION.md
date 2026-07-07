# Evaluation Strategy

`evals/decisions.json` is a curated deterministic regression set spanning purchase, travel,
career, fitness, and ambiguous choices. Run it with:

```powershell
.\.venv\Scripts\python.exe -m the_committee.evaluation
```

The JSON regression report contains every opinion and verdict plus three per-case grades:

* **structured-output** requires three unique schema-valid committee opinions;
* **consistency** compares every decision-bearing field across repeated deterministic runs;
* **chair-evidence-grounding** requires the deciding factor to come from committee evidence and
  the minority report to agree with actual dissent.

The report fails its `passed` field if any case fails any grader and includes aggregate scores by
grader. Automated tests require all scores to remain `1.0`. This suite checks contracts and
regressions; it does not claim that subjective advice is objectively correct. Model quality
evaluation should add human-labelled rubrics, larger samples, and confidence intervals without
weakening the deterministic gate.

