# Security Model

## Assets and trust boundaries

The primary sensitive assets are decision questions, supporting context, personal history,
outcome reflections, and provider credentials. Trust boundaries exist at the browser/API origin,
model provider, MCP server, database, traces, and (from M9) remote-agent transport.

## Threat model and controls

* **Unauthorized browser calls:** production sets `COMMITTEE_CORS_ORIGINS` to explicit trusted
  origins. CORS is not authentication; an internet deployment must add authenticated sessions and
  per-user authorization before storing multi-user data.
* **Prompt injection:** decision and MCP content are untrusted data, never instructions. Provider
  system prompts define the task, structured schemas constrain output, and agents receive no
  arbitrary filesystem, shell, network, or database tool. Retrieved memories must not be promoted
  into system instructions.
* **MCP overreach:** tools are purpose-built, typed, bounded, and read-only except validated
  `record_outcome`. Agents do not receive repository access. Detailed controls are in
  [`MCP_SECURITY.md`](MCP_SECURITY.md).
* **Sensitive telemetry:** trace attributes use a hard allowlist. Raw questions, context, prompts,
  responses, memory payloads, and reflections are excluded; errors record exception type only.
* **Data corruption/replay:** lifecycle validation, durable checkpoints, and database uniqueness
  constraints make deliberation retries idempotent.
* **Dependency or remote compromise:** dependencies are pinned to compatible major versions.
  The A2A Wallet path has a bounded timeout and strict artifact validation. Production requires
  HTTPS, peer authentication, task authorization, size limits, and Agent Card verification.

## Secrets

Credentials belong in environment variables or a deployment secret manager, never source,
fixtures, logs, traces, browser bundles, or committed `.env` files. Rotate exposed credentials,
restrict them to the smallest scope, and use separate development/production identities. The
deterministic default and fake integrations require no secrets.

## Personal data policy

Collect only data needed for the decision and feedback loop. Users should be able to inspect and
delete their records before multi-user release. Encrypt production transport and storage, apply
retention limits, restrict operator access, and avoid sending personal memory to a model unless
the user enabled that provider path. Backups inherit the same access and deletion policy.

The current local-first reference implementation is not a production multi-tenant service. Its
SQLite database inherits the operating-system user's permissions.
