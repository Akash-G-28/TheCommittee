# Architecture

## System boundaries

The Committee is a FastAPI application with a React presentation layer. The API composes typed
domain services; route handlers do not orchestrate agents. Immutable Pydantic domain records are
mapped to separate SQLAlchemy 2.x persistence records through `DecisionRepository`.

Committee members implement the `Agent` protocol (`evaluate` and `rebut`). Deterministic and
model-backed implementations share that contract. Model generation sits behind `ModelProvider`,
which owns structured output, timeout, error, retry, model, and usage metadata. The Chairperson
synthesizes canonical opinions and revisions into a typed verdict.

Each decision persists exactly three voting seats selected from the available roster. The default
remains Wallet, Future Me, and Chaos; Skeptic and Heart are deterministic alternative perspectives.
The Chairperson is deliberately outside that roster because it synthesizes evidence rather than
casting a peer vote. Persisting the roster makes retries and historical decisions reproducible.

Personal memory is a separate MCP boundary. The context planner can call bounded MCP tools but
cannot access the repository. A local stdio server is the development transport. See
[`MCP_SECURITY.md`](MCP_SECURITY.md) for its trust model.

## Decision lifecycle

1. `RECEIVED`: the API validates and stores a decision.
2. `CONTEXT_READY`: required context preparation has completed.
3. `DELIBERATING`: round one opinions and round two rebuttals are checkpointed independently.
4. `VERDICT_READY`: the Chairperson verdict is persisted.
5. `COMPLETED`: the user has supplied the applicable outcome feedback.
6. `FAILED`: a retryable workflow failure is recorded without losing completed checkpoints.

Every opinion, revised opinion, debate round, and verdict has a database uniqueness constraint.
Retrying deliberation resumes from existing checkpoints rather than duplicating work.

## Agent and provider contracts

`AgentOpinion`, `RevisedOpinion`, and `Verdict` are the canonical structured outputs. Product
personality affects their wording but not vote, confidence, evidence, or persistence semantics.
Model-backed implementations use versioned prompts and strict Pydantic schemas, then fall back to
their deterministic counterpart after the provider retry policy is exhausted.

## Observability

`Tracer` records a `decision.run` root, two `debate.round` spans, individual `agent.execute`
children, MCP `context.retrieve`, and `provider.generate`. The allowlisted attribute vocabulary
contains operational metadata only. Questions, context, prompts, MCP payloads, model output, and
reflections are never trace attributes. The in-memory sink is intentionally replaceable with an
OpenTelemetry exporter at deployment time.

## A2A Wallet

Wallet may be selected locally or through `RemoteWalletAgent` without changing orchestration. The
remote adapter uses the official A2A 1.0 SDK to discover an Agent Card, submit structured messages,
observe task completion, and validate the result artifact into the canonical domain contract.
Future Me and Chaos remain in process. See [`A2A.md`](A2A.md).

## Outcome loop

Outcome records preserve actual action, optional choice, follow-up state/date, satisfaction,
regret, and reflection. Accuracy is outcome-conditioned rather than treating the user's action as
objective truth. See [`SCORING.md`](SCORING.md).
