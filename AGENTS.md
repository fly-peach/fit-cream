# AGENTS.md

Notes for AI agents working in this repo.

## Repo layout

- `rogers/` — backend (FastAPI + LangGraph agent). Packages `app/` (FastAPI app, config, database, routers) and `src/` (agents, fitme services/models, knowledge_base) live at its root, so backend commands run from `rogers/` with `.` on `sys.path`.
- `frontend/` — Vite + React frontend.
- `langgraph.json` — registers `dev_graph` (`rogers/src/agents/agent_graph.py:dev_graph`) for `langgraph dev`.
- Root `.env` / `.env.example` — config loaded by `rogers/app/config.py`.

## Backend

- Run / lint from the repo root, with `rogers/` importable:
  - Lint: `python -m ruff check rogers` (no ruff config committed; default `E,F` rules). `python -m pip install ruff` if missing.
  - Type-check: `mypy rogers` is not configured and has many pre-existing findings; install with `python -m pip install mypy` if needed.
  - Compile-check a file: `python -m py_compile rogers/src/.../file.py`.
  - Import-check (compiles the agent graph, validates middleware `state_schema`): from `rogers/` run `python -c "import src.agents.agent_graph as g; print(type(g.graph).__name__)"` with `PYTHONPATH=.`.
- Start dev server: `uvicorn app.main:app --reload` from `rogers/` (or `langgraph dev` for the Studio graph).
- Entry points: production chat via `app/routers/chat.py` -> `get_agent()` (`agent_graph.py`); `create_agent_with_middleware` (per-user middleware with MemoryUpdate/ConversationPersistence) is NOT used by chat.py.
- Memory subsystem (`src/agents/harness/memory/`) uses its own `MemoryBase`, separate from the app `Base`, and is NOT under Alembic — tables/indexes are created via `MemoryStore.init_db()` (`create_all`). Schema changes need manual SQL or folding into Alembic.
- Build frontend into backend: `python build_web.py` (runs `npm run build` in `frontend/`, copies `dist/` to `rogers/static/`).

## Frontend

- From `frontend/`:
  - Dev: `npm run dev`
  - Build: `npm run build`
  - Lint: `npm run lint`
  - Type-check: `npm run typecheck`
  - Format: `npm run format`

## Conventions

- Do not add comments unless requested.
- Only commit when explicitly asked.
