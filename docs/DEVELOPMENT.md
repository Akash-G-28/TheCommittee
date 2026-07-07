# Local Development

## Backend

Requires Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe the_committee.api:create_app --factory --reload
```

Run `pytest`, `ruff check .`, `mypy .`, and `alembic upgrade head` before a backend checkpoint.
Deterministic mode is the default and needs no credentials.

## Frontend

Requires Node.js 22 or newer.

```powershell
cd frontend
npm install
npm run dev
```

Run `npm run lint`, `npm run type-check`, `npm run test`, and `npm run build`. The default API URL
is `http://localhost:8000`; override it with `VITE_API_URL`. Configure API origins with
`COMMITTEE_CORS_ORIGINS`.

## Evaluation and MCP

Run the regression report with `.\.venv\Scripts\python.exe -m the_committee.evaluation`. Start the
local memory server with `.\.venv\Scripts\python.exe -m the_committee.memory_mcp`; it communicates
over stdio and uses `COMMITTEE_DATABASE_URL` when configured.

