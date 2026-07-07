# Wallet A2A Boundary

Wallet is the first independently deployable committee member. It uses the official A2A Python
SDK and the A2A 1.0 HTTP+JSON/REST binding.

Run the Wallet server separately:

```powershell
.\.venv\Scripts\uvicorn.exe the_committee.a2a_wallet:app --host 127.0.0.1 --port 8001
```

Set `COMMITTEE_WALLET_A2A_URL=http://127.0.0.1:8001` before starting the main API. Optional
`COMMITTEE_WALLET_A2A_TIMEOUT_SECONDS` defaults to five seconds. Without the URL, the orchestrator
uses local `WalletAgent`. Remote failures and timeouts fall back to that same deterministic
implementation so one unavailable peer does not strand a personal decision.

The server publishes `/.well-known/agent-card.json`. Its card declares Wallet's identity, A2A 1.0
REST interface, JSON input/output modes, and `wallet-deliberation` skill. Each evaluate or rebut
message creates a server-generated task, publishes submitted/working/completed state, and returns
one typed opinion artifact. The client validates the artifact back into the canonical Committee
domain model.

The in-process ASGI tests still pass through the official SDK's card resolver, client transport,
REST routes, request handler, task store, event queue, and artifact model. They cover local/remote
contract parity, discovery, task state, artifacts, timeout, failure fallback, and full
deliberation.

Production deployment must use HTTPS, authenticate both peers, authorize task access, cap message
sizes, and restrict Agent Card discovery as appropriate. Agent Card text and remote artifacts are
untrusted input; only declared interfaces and schema-valid artifacts are accepted.

