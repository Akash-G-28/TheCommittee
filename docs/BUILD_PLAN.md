# The Committee Build Plan

## Global Definition of Done

The project is complete when:

* the complete user decision workflow functions end to end
* deterministic test mode works without an LLM
* real model-backed committee members use structured outputs
* committee members perform independent argument and rebuttal phases
* a Chairperson produces a final verdict and minority report
* personal decision memory is accessed through an MCP server
* decisions support delayed outcome feedback
* committee member accuracy can be calculated from resolved decisions
* the responsive web UI presents a deliberation-room experience rather than a generic chatbot
* important AI operations are traceable
* evaluation datasets and graders exist
* documentation explains architecture, trade-offs, security, MCP boundaries, and the A2A roadmap
* all required test, lint, type-check, and build validation passes

---

## M1: Deterministic Backend Foundation

### Goal

Create the domain, persistence, API, deterministic committee members, and orchestration foundation without using an LLM.

### Deliverables

* FastAPI application
* Pydantic v2 schemas
* SQLAlchemy 2.x persistence
* SQLite development database
* Alembic migrations
* typed repository interfaces
* typed Agent interface
* WalletAgent deterministic implementation
* FutureMeAgent deterministic implementation
* ChaosAgent deterministic implementation
* deterministic Chairperson service
* validated decision state machine

### Initial Decision Statuses

* RECEIVED
* CONTEXT_READY
* DELIBERATING
* VERDICT_READY
* COMPLETED
* FAILED

### API

* POST `/decisions`
* POST `/decisions/{decision_id}/deliberate`
* GET `/decisions/{decision_id}`
* GET `/health`

### Required Tests

* unit test for each agent
* Chairperson tests
* state transition tests
* orchestration tests
* API integration tests
* retry-safe deliberation test
* duplicate opinion prevention test

### Validation

* pytest
* ruff check .
* mypy .

---

## M2: Model Provider Abstraction

### Goal

Make AI generation replaceable without coupling the domain or agents to one model provider.

### Deliverables

Create a typed model provider abstraction supporting:

* structured request
* structured response model
* timeout
* provider errors
* model metadata
* usage metadata where available

Implement:

* MockModelProvider
* provider configuration
* retry policy for safe transient failures
* provider contract tests

The application must continue to run fully in deterministic or mock mode.

### Validation

* provider contract tests
* full pytest suite
* Ruff
* mypy

---

## M3: Model-Backed Committee Members

### Goal

Replace rule-only reasoning with optional model-backed implementations while preserving deterministic testing.

### Deliverables

* Wallet model-backed implementation
* Future Me model-backed implementation
* Chaos model-backed implementation
* Chairperson model-backed synthesis
* strict structured outputs
* prompt versioning
* malformed-output handling
* model timeout handling
* deterministic fallback behaviour

Create a small evaluation dataset covering at least:

* purchase decisions
* travel decisions
* career decisions
* fitness decisions
* ambiguous decisions

### Validation

* schema-valid output tests
* provider failure tests
* fallback tests
* evaluation runner
* full validation suite

---

## M4: Debate and Rebuttal

### Goal

Move from parallel opinions to genuine multi-stage deliberation.

### Workflow

Round 1:
Committee members produce independent opinions without seeing other members' answers.

Round 2:
Each member receives the other opinions and may:

* maintain its vote
* change its vote
* produce a rebuttal
* identify evidence that would change its conclusion

Final:
The Chairperson evaluates:

* argument quality
* evidence
* unresolved disagreement
* vote changes
* confidence
* minority opinion

### Deliverables

* persisted debate rounds
* rebuttal model
* revised opinion model
* orchestration state
* retry-safe round execution
* Chairperson final synthesis

### Validation

* order-independent orchestration tests
* retry tests
* partial-failure recovery tests
* full validation suite

---

## M5: Personal Memory MCP Server

### Goal

Build the first custom MCP server used by The Committee.

### Initial Tools

* `search_decisions`
* `get_decision`
* `get_similar_decisions`
* `record_outcome`
* `get_regret_patterns`
* `get_agent_history`

### Requirements

* explicit typed tool contracts
* no hidden direct database access from committee agents
* safe read/write separation
* write validation
* deterministic local test fixture
* MCP contract tests
* clear security documentation

### Validation

* MCP tool contract tests
* integration tests from context planner to MCP
* retry and failure tests
* full validation suite

---

## M6: Outcome Feedback and Committee Accuracy

### Goal

Create the feedback loop that makes The Committee improve as a personal decision system.

### Flow

Decision
? Committee verdict
? User records actual choice
? Follow-up outcome
? Satisfaction/regret score
? Agent vote comparison
? Committee accuracy update

### Deliverables

* actual user action field
* outcome status
* follow-up date
* satisfaction score
* regret score
* free-text outcome reflection
* agent scoring methodology
* category-level performance statistics
* confidence calibration analysis

### Validation

* scoring tests
* unresolved decision handling
* vote-change scoring rules
* category aggregation tests
* full validation suite

---

## M7: Deliberation Room Frontend

### Goal

Build a memorable responsive product experience.

The UI must not look like a generic AI chatbot or corporate SaaS dashboard.

### Screens

1. Decision intake
2. Context review
3. Deliberation room
4. Debate/rebuttal view
5. Verdict card
6. Minority report
7. Decision history
8. Committee performance
9. Outcome follow-up

### Experience Requirements

Committee members should feel visually distinct.

The deliberation screen should communicate:

* who is thinking
* who has voted
* disagreement
* rebuttal
* vote changes
* Chairperson synthesis

The verdict screen must prominently display:

* verdict
* confidence
* vote breakdown
* deciding factor
* minority report

### Validation

* lint
* type-check
* frontend tests
* production build
* API integration smoke test

---

## M8: Observability, Evaluation, Security and Documentation

### Goal

Turn the working application into a portfolio-quality engineering reference implementation.

### Deliverables

Observability:

* decision run trace
* context retrieval spans
* agent execution spans
* debate round spans
* provider latency
* token/usage metadata where available
* errors without sensitive personal content

Evaluation:

* curated decision dataset
* structured-output grader
* consistency grader
* Chairperson evidence-grounding grader
* regression report

Security:

* threat model
* secret handling documentation
* MCP trust boundary documentation
* prompt injection considerations
* personal data handling policy

Documentation:

* architecture
* decision lifecycle
* agent contracts
* MCP design
* evaluation strategy
* security model
* local development guide
* roadmap

### Validation

Run every repository validation command.

No milestone may remain incomplete.

---

## M9: First A2A Committee Member

### Goal

Demonstrate true independent-agent interoperability without restructuring the entire system unnecessarily.

### Scope

Extract Wallet as the first independently deployed agent.

Expose:

* agent identity
* Agent Card
* supported skill declaration
* task submission
* task status
* result artifact

The Committee orchestrator must be able to use:

* the local Wallet implementation
* the remote A2A Wallet implementation

through a replaceable boundary.

### Validation

* local and remote contract parity
* A2A interoperability tests
* timeout tests
* remote-agent failure handling
* complete end-to-end deliberation test
* full repository validation suite
