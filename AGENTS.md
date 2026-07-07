# The Committee: Repository Engineering Instructions

## Product

The Committee is a playful but technically serious personal decision application.

Users submit decisions such as:

“Should I spend ?28,000 on an ergonomic chair?”

A committee of agents evaluates the decision:

* Wallet: affordability, cost, alternatives, and opportunity cost
* Future Me: long-term alignment, consequences, and likely regret
* Chaos: exploration value, spontaneity, emotional upside, and the cost of over-analysis
* Chairperson: evidence synthesis, disagreement resolution, final verdict, confidence, and minority report

The project is intended to demonstrate serious engineering beneath a playful consumer product, including:

* multi-agent orchestration
* structured LLM outputs
* MCP-based context access
* persistent decision memory
* delayed feedback loops
* agent performance evaluation
* observability and tracing
* human approval for consequential write actions
* later A2A interoperability

## Development Protocol

The source of truth for project execution is:

`docs/BUILD_PLAN.md`

The execution state is:

`docs/BUILD_STATUS.md`

Architectural decisions and meaningful deviations must be recorded in:

`docs/DECISIONS.md`

When instructed to execute the build plan:

1. Read this file.
2. Read `docs/BUILD_PLAN.md`.
3. Read `docs/BUILD_STATUS.md`.
4. Find the first milestone that is not COMPLETE.
5. Work only within the scope and acceptance criteria of that milestone.
6. Implement the smallest coherent architecture that satisfies the milestone.
7. Run all milestone validation commands.
8. If validation fails, diagnose and repair the current milestone.
9. Do not advance while mandatory validation is failing.
10. When validation passes:

* update `docs/BUILD_STATUS.md`
* record meaningful architectural decisions
* create a clean milestone checkpoint commit when repository permissions allow
* continue automatically to the next incomplete milestone

11. Continue until all milestones are COMPLETE or a HARD BLOCKER is reached.

## Recovery Rules

A failing test, lint error, type error, migration problem, or ordinary implementation defect is not a blocker.

Diagnose it, repair it, and rerun validation.

A HARD BLOCKER is limited to situations such as:

* missing credentials that cannot be replaced by a mock
* unavailable external account or service
* security-sensitive action requiring explicit human approval
* a genuinely ambiguous product choice that materially changes the architecture
* an environment constraint that cannot be worked around locally

When a hard blocker occurs:

1. Stop modifying unrelated code.
2. Update `docs/BUILD_STATUS.md`.
3. Record:

   * milestone
   * blocker
   * investigations performed
   * attempted solutions
   * exact human input required
4. Stop execution.

Do not classify ordinary coding difficulty as a hard blocker.

## Engineering Rules

* Python backend code must be typed.
* Use Python 3.12.
* Use Pydantic v2 conventions.
* Use SQLAlchemy 2.x style.
* Keep domain models separate from persistence models.
* Keep orchestration outside API route handlers.
* External providers must sit behind typed interfaces.
* The application must remain testable without a live LLM.
* Every external integration must have a deterministic fake or mock implementation.
* Do not introduce MCP until the MCP milestone.
* Do not introduce A2A until the A2A milestone.
* Do not introduce infrastructure merely for portfolio appearance.
* Prefer simple architecture that can evolve cleanly.
* Never commit credentials, tokens, private personal data, or production secrets.

## Validation

Backend milestones must normally pass:

`pytest`

`ruff check .`

`mypy .`

Frontend milestones must normally pass the repository's configured:

* lint command
* type-check command
* test command
* production build command

Run focused tests while repairing failures, followed by the full required validation suite before marking a milestone complete.

## Architecture Changes

When the existing design must change to support a later milestone:

* make the smallest coherent change
* maintain backward compatibility where practical
* update tests
* update architecture documentation
* record the reasoning in `docs/DECISIONS.md`

Do not preserve a poor earlier abstraction merely to avoid refactoring.

## Execution Style

Work autonomously.

Make conservative engineering assumptions when they are reversible.

Record assumptions that materially affect behaviour or architecture.

Do not ask for approval between normal milestones.

Do not skip validation gates.

Do not start multiple write-heavy implementation agents against overlapping files.

Parallel agents may be used for independent read-heavy tasks such as:

* repository exploration
* test analysis
* security review
* documentation review
* failure triage

The primary agent remains responsible for integration and final validation.
