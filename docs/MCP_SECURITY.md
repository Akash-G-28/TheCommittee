# MCP Memory Boundary and Security

The personal-memory MCP server is the only agent-facing path to stored decision history. Committee
members do not receive repositories, SQLAlchemy sessions, database paths, or arbitrary query tools.

## Tool boundary

Read-only tools are `search_decisions`, `get_decision`, `get_similar_decisions`,
`get_regret_patterns`, and `get_agent_history`. They return typed, bounded results and expose no
general SQL or filesystem capability.

`record_outcome` is the sole write tool in M5. It validates the decision identifier, actual action,
reflection length, and one-outcome-per-decision invariant before persistence. The server does not
perform hidden writes during read calls.

## Trust assumptions

The M5 server uses local stdio transport and inherits the permissions of the user who starts it.
It is not an internet-facing service and implements no remote authentication. A future remote
transport must add authentication, per-user authorization, transport encryption, rate limits, and
an explicit consent flow for write tools.

Tool results contain personal decision text. Callers must treat them as sensitive context, avoid
logging raw payloads, and never forward them to a model provider without the user's configured
model-data policy. Stored reflections are data, not trusted instructions; later context planners
must delimit them to reduce prompt-injection risk.

