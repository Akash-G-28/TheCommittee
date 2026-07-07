# The Committee Architecture Decision Log

This document records meaningful architectural and product decisions made during development.

Use it for decisions that affect system structure, boundaries, behaviour, protocols, persistence, security, evaluation, or long-term maintainability.

Do not record ordinary implementation details or trivial code changes.

---

## Decision Record Template

### ADR-XXX: Decision Title

**Status:** Proposed | Accepted | Superseded | Rejected

**Date:**

**Milestone:**

### Context

Describe the problem, constraint, or architectural question.

### Decision

Describe the chosen approach.

### Alternatives Considered

Describe meaningful alternatives that were considered.

### Rationale

Explain why the selected option was chosen.

### Consequences

Describe positive and negative consequences.

### Follow-up

List future work, risks, or revisit conditions.

---

# Accepted Decisions

## ADR-015: Preserve Three Voting Seats While Making the Roster Selectable

**Status:** Accepted

**Date:** 2026-07-08

**Milestone:** Post-plan product refinement

### Context

The original plan names three voting perspectives plus a Chairperson. Presenting only the voters
made the Chair look absent and left no way to choose a better perspective for a particular choice.

### Decision

Keep exactly three peer voting seats, make their roster part of the persisted Decision contract,
and offer five deterministic implementations: Wallet, Future Me, Chaos, Skeptic, and Heart. Keep
the original trio as the default. The Chairperson remains a non-voting evidence synthesizer.

### Alternatives Considered

* Make the Chairperson a fourth voter
* Run all five agents on every decision
* Treat roster selection as transient frontend state

### Rationale

Three seats preserve clear majority semantics and the compact deliberation experience. Selection
adds meaningful variety without increasing every run's latency. Persisting the roster keeps retry,
history, scoring, and audit behavior deterministic.

### Consequences

Decision persistence gains a roster field and migration. Performance views can show agents with no
resolved samples. New agents need deterministic tests and can later gain model-backed variants.

### Follow-up

Evaluate whether outcome data supports recommended rosters by decision category, without silently
changing the user's selected committee.

## ADR-014: Extract Only Wallet Through the Official A2A 1.0 SDK

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M9

### Context

Wallet must become independently deployable without forcing networking and task lifecycle onto
the two committee members that remain internal. The released A2A specification is 1.0 and the
official Python SDK 1.1 implements its REST, JSON-RPC, and gRPC bindings.

### Decision

Use the official SDK's A2A 1.0 HTTP+JSON/REST binding for discovery, message submission, task
status, and typed artifacts. Preserve the existing `Agent` contract through `RemoteWalletAgent`;
select local or remote Wallet at composition time and fall back locally after timeout or failure.

### Alternatives Considered

* Hand-roll an A2A-shaped HTTP API
* Extract all committee members simultaneously
* Replace the internal `Agent` contract with protocol types

### Rationale

The SDK provides real interoperability and protocol lifecycle validation. Adapting at the existing
boundary isolates transport mechanics and keeps the orchestrator, persistence, and Chairperson
unchanged.

### Consequences

The remote path adds protobuf/SDK dependencies, latency, discovery, and network failure modes.
Deterministic fallback preserves availability but must be observable in a production exporter.

### Follow-up

Add peer authentication, HTTPS, persistent remote task storage, and signed Agent Card verification
before internet deployment.

## ADR-013: Trace Operational Metadata Through a Privacy Allowlist

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M8

### Context

Agent, provider, debate, and MCP operations need useful traces, but their inputs contain sensitive
personal decisions and history.

### Decision

Use replaceable tracing primitives with hierarchical run spans and a hard allowlist of operational
attributes. Record identifiers, phase, agent, timing, provider/model, usage counts, result counts,
status, and exception type; never record raw personal or generated content.

### Alternatives Considered

* Log full prompts and MCP payloads for easier debugging
* Avoid traces entirely
* Depend directly on one hosted observability vendor

### Rationale

The allowlist makes privacy the default while retaining enough metadata to diagnose latency,
failure location, retries, and token usage. A sink boundary keeps deployment export replaceable.

### Consequences

Content-level debugging requires explicit local reproduction rather than production traces. New
attributes must pass a deliberate privacy review.

### Follow-up

Add an authenticated OpenTelemetry exporter and retention controls when a production deployment
exists.

## ADR-012: Keep the Deliberation Experience API-Backed and Stage-Oriented

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M7

### Context

The frontend needs personality and cinematic pacing without turning canonical committee state
into client-only animation state or a chat transcript.

### Decision

Use a single responsive React application whose intake, review, deliberation, verdict, archive,
performance, and follow-up stages render typed API records. Client state controls presentation;
the backend remains authoritative for decisions, opinions, rebuttals, verdicts, and outcomes.

### Alternatives Considered

* A generic message-thread interface
* Separate frontend routes with duplicated workflow state
* Client-generated committee output

### Rationale

Stage-oriented presentation supports the product metaphor while typed API state preserves retry
safety, refreshability, and evaluation integrity.

### Consequences

The frontend needs explicit loading/error transitions and a configured CORS allowlist. It can
change visual treatment without changing decision contracts.

### Follow-up

Add browser-level regression coverage if the frontend workflow grows beyond the current compact
state machine.

## ADR-011: Treat Committee Accuracy as Outcome-Conditioned Calibration

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M6

### Context

Personal choices rarely have objectively correct labels. A raw vote-versus-action match would
reward agents for agreeing with choices that users later report as harmful or regrettable.

### Decision

Score final post-rebuttal votes against both the user's actual choice and reported outcome quality.
High-satisfaction, low-regret outcomes reward matching votes; poor outcomes reward opposition;
mixed outcomes remain neutral. `MAYBE` receives partial credit, unresolved outcomes are excluded,
and calibration reports retain sample counts.

### Alternatives Considered

* Treat the user's action as ground truth regardless of outcome
* Score only the Chairperson verdict
* Omit accuracy because personal decisions are subjective

### Rationale

Outcome-conditioned scores preserve the feedback loop without pretending subjective hindsight is
objective truth. Using final votes measures whether debate improved each member's position.

### Consequences

Scores depend on self-reporting and can be sparse or biased. They are suitable for reflection and
calibration, not autonomous ranking or consequential decision authority.

### Follow-up

Future evaluation should test alternate thresholds and display uncertainty when category samples
are small.

---

## ADR-010: Expose Personal Memory Through Bounded MCP Tools on Stable SDK v1

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M5

### Context

As of this milestone, the official Python SDK v2 is still an alpha release while v1 is the current
stable protocol implementation. Personal history is sensitive and does not require arbitrary query
or filesystem capabilities.

### Decision

Pin `mcp>=1.27,<2` and expose six typed, bounded tools over local stdio. Committee members receive
no repository or database session. The context planner calls the MCP tool contract, reads are
bounded, and `record_outcome` is the only write tool.

### Alternatives Considered

* Adopt the v2 alpha immediately
* Give committee agents repository access
* Expose a general-purpose SQL MCP tool

### Rationale

The stable SDK reduces protocol churn, and purpose-built tools constrain data exposure and mutation
far more effectively than arbitrary database access.

### Consequences

The application must deliberately migrate when MCP v2 stabilizes. Local stdio inherits user
permissions; any remote transport will require authentication and authorization.

### Follow-up

Review the v2 migration after its stable release. M8 must include this boundary in the threat model
and ensure traces never record raw personal tool payloads.

---

## ADR-009: Fall Back at the Agent Boundary After Provider Policy Is Exhausted

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M3

### Context

The provider boundary owns retries, but a personal decision workflow should remain available when
a provider is down, times out, or returns schema-invalid data.

### Decision

Model-backed agents and the Chairperson request strict, versioned structured outputs. After the
provider returns a classified error, each model-backed implementation delegates to its matching
deterministic implementation. Provider retries therefore happen before fallback, and persistence
receives only a valid canonical domain object.

### Alternatives Considered

* Fail the whole deliberation when any model call fails
* Parse unstructured prose after schema validation fails
* Put fallback behavior in API handlers

### Rationale

The agent boundary has enough context to choose the correct deterministic substitute while keeping
orchestration and HTTP layers provider-agnostic. Refusing to parse invalid prose preserves contract
integrity.

### Consequences

Fallback output is reliable but less context-sensitive. Future observability must expose fallback
use without recording sensitive prompt content.

### Follow-up

M8 should trace provider errors and fallback selection. Evaluation should compare model-backed and
deterministic behavior rather than treating fallback as equivalent model success.

---

## ADR-008: Retry Only Explicitly Transient Model Provider Failures

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M2

### Context

Provider calls can fail because of temporary capacity or timeouts, malformed model output, invalid
requests, or permanent configuration errors. Blind retries can amplify costs and conceal contract
violations.

### Decision

Define a provider-neutral error taxonomy. Only `TransientModelProviderError` and its timeout subtype
are retryable. Schema violations and general provider errors fail immediately. Retry count and
exponential backoff are configuration values, and tests inject a no-op sleeper.

### Alternatives Considered

* Retry every provider exception
* Put retry logic inside each model-backed agent
* Depend on a vendor SDK's retry defaults

### Rationale

Central policy gives every future provider consistent behavior and keeps agents unaware of vendor
mechanics. Explicit classification avoids retrying malformed structured output.

### Consequences

Provider adapters must classify errors carefully. Timeouts may still consume provider work, but
generation requests do not mutate Committee state until a valid structured result is returned.

### Follow-up

Real provider adapters added after M2 must translate vendor exceptions into this taxonomy and
populate usage metadata when available.

---

## ADR-007: Persist Retry Checkpoints Behind a Typed Repository Boundary

**Status:** Accepted

**Date:** 2026-07-07

**Milestone:** M1

### Context

Deliberation must be safe to retry without duplicating opinions or recomputing a completed
verdict. Later milestones will add multi-round work and provider failures, making partial progress
an expected application state.

### Decision

Use immutable Pydantic domain models, separate SQLAlchemy persistence records, and a typed
repository protocol. Persist each lifecycle transition and completed agent opinion as a durable
checkpoint. Enforce one opinion per decision and agent, and one verdict per decision, with database
constraints in addition to orchestration checks.

### Alternatives Considered

* Keep an entire deliberation in one database transaction
* Put SQLAlchemy records directly in the domain and API contracts
* Rely only on application-level duplicate checks

### Rationale

Durable checkpoints make retries observable and resumable. Separating models keeps lifecycle and
agent logic testable without SQLAlchemy while database constraints protect invariants during
concurrent or repeated requests.

### Consequences

Positive:

* deterministic retry behaviour
* persistence concerns remain outside the domain
* later debate rounds can extend the checkpoint pattern

Negative:

* a run is not atomic as a whole
* transient intermediate states must be handled explicitly

### Follow-up

M4 should reuse this pattern for rounds and rebuttals and add stronger concurrency handling if the
application moves beyond a single-process SQLite deployment.

---

## ADR-001: Build the Product in Milestones Instead of as a Single Large Implementation

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** Global

### Context

The Committee is intended to demonstrate multiple advanced capabilities including multi-agent orchestration, MCP, structured outputs, memory, evaluations, tracing, feedback loops, and later A2A interoperability.

Attempting to implement all of these simultaneously would increase coupling, reduce testability, and make failures difficult to isolate.

### Decision

The project will be implemented through explicit milestones defined in `docs/BUILD_PLAN.md`.

Each milestone must:

* have a narrow goal
* define deliverables
* define validation requirements
* pass mandatory validation before the next milestone begins

The milestone runner may continue automatically through milestones, but it must preserve the architectural and validation boundaries between them.

### Alternatives Considered

* Build the complete application from one large prompt
* Build features opportunistically without milestone boundaries
* Build frontend and backend simultaneously from the beginning

### Rationale

Milestones preserve engineering discipline while still allowing autonomous execution.

They also provide clean checkpoints for:

* regression isolation
* portfolio storytelling
* architecture evolution
* test coverage
* resumability

### Consequences

Positive:

* failures are easier to isolate
* architecture can evolve intentionally
* validation is explicit
* work is resumable
* individual milestones can be reviewed independently

Negative:

* some later milestones may require refactoring earlier abstractions
* the repository will contain more planning and status documentation

### Follow-up

The milestone plan may evolve, but meaningful changes to milestone scope should be recorded in this document.

---

## ADR-002: Keep the Application Fully Testable Without a Live LLM

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** M1 and M2

### Context

Live model dependencies introduce:

* cost
* latency
* nondeterminism
* rate limits
* provider outages
* test instability

The core domain and orchestration should not depend on a model being available.

### Decision

The system will support deterministic and mock execution paths.

Agents will sit behind typed interfaces so that deterministic implementations, mock provider implementations, and real model-backed implementations can share the same contracts.

### Alternatives Considered

* Require a live model for all agent behaviour
* Mock only at the HTTP layer
* Skip deterministic agents and begin directly with prompts

### Rationale

The architecture should prove that the product is a software system with AI components, not a prompt wrapper.

### Consequences

Positive:

* reliable automated tests
* offline local development
* provider portability
* simpler CI
* safer refactoring

Negative:

* more abstraction work early in the project
* deterministic agents must be maintained during development

### Follow-up

Real model-backed implementations will be added in M3 without removing deterministic test support.

---

## ADR-003: Use MCP for Personal Context Access

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** M5

### Context

Committee members will eventually require access to personal decision history and other contextual sources.

Direct database access from agent implementations would tightly couple reasoning logic to persistence and make future context sources harder to add safely.

### Decision

Personal decision memory will be exposed through an MCP server.

Initial tools will include:

* `search_decisions`
* `get_decision`
* `get_similar_decisions`
* `record_outcome`
* `get_regret_patterns`
* `get_agent_history`

Committee agents will not receive hidden direct access to the underlying persistence layer.

### Alternatives Considered

* direct SQL access from agent implementations
* internal REST API only
* inject repositories directly into agents

### Rationale

MCP is a genuine fit because the problem is agent access to tools and structured context.

It also provides a clear portfolio example of designing and implementing an MCP server rather than merely consuming one.

### Consequences

Positive:

* explicit tool contracts
* clearer trust boundaries
* easier testing
* easier future integration of additional context sources

Negative:

* more integration complexity
* protocol boundary introduces additional failure modes

### Follow-up

Security and trust boundaries must be documented in M8.

---

## ADR-004: Do Not Use A2A for Internal Committee Members in the Initial Architecture

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** M1 through M8

### Context

The Committee contains multiple logical agents, but the initial committee members are internal parts of one application.

Using an agent-to-agent protocol prematurely would add networking, deployment, task lifecycle, and discovery complexity without a genuine interoperability requirement.

### Decision

Initial committee members will use native in-process orchestration.

A2A will be introduced only in M9 when Wallet becomes an independently deployed agent with a genuine remote interoperability boundary.

### Alternatives Considered

* deploy every committee member as a separate service from M1
* use A2A for all internal subagent communication
* never introduce A2A

### Rationale

Protocols should exist because the architecture needs them, not because they are fashionable.

This approach demonstrates both protocol knowledge and engineering restraint.

### Consequences

Positive:

* simpler early architecture
* easier tests
* faster iteration
* A2A milestone becomes a meaningful architectural evolution

Negative:

* later extraction of Wallet will require an adapter boundary
* some orchestration code may need refactoring

### Follow-up

The local and remote Wallet implementations must satisfy compatible contracts in M9.

---

## ADR-005: Separate Product Personality from Agent Decision Logic

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** M1 onward

### Context

Wallet, Future Me, Chaos, and Chairperson have distinct personalities.

There is a risk that humour and personality could become mixed with core voting logic, persistence, scoring, and evaluation.

### Decision

Agent personality presentation should remain separable from:

* vote semantics
* confidence
* key factors
* evidence
* rebuttals
* outcome scoring
* persistence

Structured decision outputs remain canonical.

Personality should influence wording and perspective, not corrupt the domain contract.

### Alternatives Considered

* store only unstructured conversational responses
* allow each agent to return arbitrary output
* parse verdict information from generated prose

### Rationale

The product can be playful while the architecture remains measurable and testable.

### Consequences

Positive:

* reliable scoring
* easier evaluation
* clearer persistence model
* UI can change tone without changing the decision model

Negative:

* structured outputs may constrain some creative responses
* rendering logic becomes a separate concern

### Follow-up

M3 prompt contracts and M7 presentation components should preserve this separation.

---

## ADR-006: Make Outcome Feedback a Core Product Loop

**Status:** Accepted

**Date:** Initial architecture

**Milestone:** M6

### Context

A multi-agent debate application could easily become a novelty experience with no way to determine whether the advice was useful.

### Decision

The application will track:

* committee recommendation
* actual user action
* later outcome
* satisfaction
* regret
* agent-level historical performance

The Committee Accuracy experience is a core product feature, not optional analytics.

### Alternatives Considered

* store verdict history only
* allow manual likes/dislikes on responses
* avoid performance scoring because personal decisions are subjective

### Rationale

Outcome tracking turns the project from a multi-agent demo into a longitudinal personal decision system.

It also creates meaningful engineering work around:

* delayed feedback
* unresolved outcomes
* calibration
* category-level accuracy
* memory retrieval

### Consequences

Positive:

* stronger product differentiation
* richer evaluation
* memorable UI opportunities
* longitudinal personalization

Negative:

* scoring methodology must be designed carefully
* many decisions will remain unresolved for long periods
* accuracy must not be presented as objective truth

### Follow-up

M6 must document the scoring methodology and limitations.

---

# Proposed Decisions

None yet.

---

# Superseded Decisions

None yet.

---

# Rejected Decisions

None yet.
