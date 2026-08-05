# AGENTS.md

Notes for AI agents working in this repo.

## Repo layout

- `rogers/` - backend (FastAPI + LangGraph agent). Packages `app/` (FastAPI app, config, database, routers) and `src/` (agents, fitme services/models, knowledge_base) live at its root, so backend commands run from `rogers/` with `.` on `sys.path`.
- `frontend/` - Vite + React frontend.
- `langgraph.json` - registers `dev_graph` (`rogers/src/agents/agent_graph.py:dev_graph`) for `langgraph dev`.
- Root `.env` / `.env.example` - config loaded by `rogers/app/config.py`.

## Backend

- Run / lint from the repo root, with `rogers/` importable:
  - Lint: `python -m ruff check rogers` (no ruff config committed; default `E,F` rules). `python -m pip install ruff` if missing. Local env uses anaconda `agentenv`: `E:\wangtong\apps\anaconda\envs\agentenv\python.exe`.
  - Type-check: `mypy rogers` is not configured and has many pre-existing findings; install with `python -m pip install mypy` if needed.
  - Compile-check a file: `python -m py_compile rogers/src/.../file.py`.
  - Import-check (compiles the agent graph, validates middleware `state_schema`): from `rogers/` run `python -c "import src.agents.agent_graph as g; print(type(g.graph).__name__)"` with `PYTHONPATH=.`.
- Start dev server: `uvicorn app.main:app --reload` from `rogers/` (or `langgraph dev` for the Studio graph).
- Entry points: production chat via `app/routers/chat.py` -> `get_agent()` (`agent_graph.py`); `create_agent_with_middleware` (per-user middleware with MemoryUpdate/ConversationPersistence) is NOT used by chat.py.
- Memory subsystem (`src/agents/harness/runtime/memory/`) uses its own `MemoryBase`, separate from the app `Base`, and is NOT under Alembic - tables/indexes are created via `MemoryStore.init_db()` (`create_all`). Schema changes need manual SQL or folding into Alembic.
- Build frontend into backend: `python build_web.py` (runs `npm run build` in `frontend/`, copies `dist/` to `rogers/static/`).

## Agent prompt & skills architecture

- **L0 静态层唯一入口**：`rogers/src/agents/harness/orchestration/prompts/agent.md` 是基础系统提示词的唯一来源；`system.py` 启动时加载它作为 `BASE_SYSTEM_PROMPT`。**修改静态提示词改 `agent.md`，不要改 `system.py`**。`system.py` 仅负责加载 + INTENT injection 逻辑（`INTENT_PROMPTS` / `INTENT_KEYWORDS` / `build_system_prompt()`）。
- 外层仓库根目录**不新增 `agent.md`**（提示词 BASE 层只保留在 `prompts/agent.md`）。
- **Skills 子系统**（渐进式披露，仿 Deep Agents）：
  - L1 元数据：`harness/skills/<name>/SKILL.md` 的 YAML frontmatter（`name`/`description`）由 `skills_loader.get_catalog_prompt()` 在 `agent_factory` 构建时烘焙进 system_prompt（<500 token）。
  - L2 指令：AI 调 `skill_load_tool(skill_name)` 懒加载 `SKILL.md` 正文。
  - L3 资源：`skill_load_tool(skill_name, resource_path)` 读 `references/`。
  - 新增技能：在 `harness/skills/<name>/` 下放 `SKILL.md`（frontmatter + markdown 正文），无需改代码即被 catalog 自动扫描。
  - `SkillsMiddleware` 是纯占位（catalog 已静态烘焙，`before_model` 返回 None）。

## HITL（Human-in-the-Loop）审批

- 由 LangChain `HumanInTheLoopMiddleware` 实现，在 `_get_default_middleware(include_hitl=...)` 中**仅当 checkpointer 存在时启用**（`agent_factory.create_fitcream_agent` 传 `include_hitl=checkpointer is not None`）。
- 中断工具：`create_plan_tool` / `create_diet_plan_tool` / `adjust_plan_tool`，`allowed_decisions=["approve","reject"]`。
- `dev_graph` / `graph`（无 checkpointer）**不启用 HITL**，副作用工具自动放行。
- 流程：`/chat/message` 流末检测 `agent.aget_state().tasks[*].interrupts` -> 发 `approval_needed` SSE -> 前端 Confirmation 卡片 -> `POST /chat/resume`（`Command(resume={"decisions":[...]})`）续流。
- 「修改」语义：前端 reject + `reason`=修订稿 -> 后端映射为 `RejectDecision.message` 注入 -> agent 重新 `present_plan_tool` + `create_plan_tool` -> 新 `approval_needed`。
- `present_plan_tool` 是**纯展示工具**（不落库、不中断），驱动前端 Plan 卡片；`create_plan_tool` 才触发审批中断。

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
