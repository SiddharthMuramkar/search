# Deep Research API

FastAPI + PostgreSQL service that runs a deep research agent in the background, with three agent
architectures, a stored comparison and OpenTelemetry traces. A take-home test with a short deadline.

The specification is `SPEC.md`. Read the section you work on before you write code. Requirement ids
(`R1`...), decisions (`D1`...) and milestones (`M1`...) are defined there.

## Commands

```bash
uv sync                                   # install
docker compose up -d                      # PostgreSQL 18 + Jaeger (UI: http://localhost:16686)
uv run alembic upgrade head               # apply migrations
uv run --env-file .env fastapi dev app/main.py   # add --no-reload while a research job runs
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run alembic revision --autogenerate -m "message"   # then read the new file before you apply it
bash scripts/e2e.sh                       # curl walk through every route (needs the running stack)
```

## Stack

Python 3.12+, uv, FastAPI (`fastapi[standard]==0.143.*`), SQLAlchemy 2.1 async + asyncpg, Alembic,
PostgreSQL 18, OpenAI SDK pointed at OpenRouter, Tavily through httpx, OpenTelemetry SDK + Jaeger,
pytest with the AnyIO plugin. No agent framework, no queue, no extra service.

## Hard rules

1. The background job opens its own database session. Pass `run.id` to it, never a session or an ORM
   object. Commit the run row before `background_tasks.add_task`.
2. One short session for each step write. Never share a session between tasks in `asyncio.gather`.
3. The database URL is always `postgresql+asyncpg://`. Install `"sqlalchemy[asyncio]"` (quote extras:
   the shell is zsh).
4. No blocking calls in async code (`requests`, `time.sleep`, sync file or network IO).
5. Every model call goes through `llm.complete`, every search through `search.search`. Import the
   modules (`from app import llm, search`) and call through them; tests replace `call_openrouter`
   and `call_tavily`.
6. Every agent step is recorded with `tracing.step()` (span + `steps` row). No step without both.
7. All architectures use the same model, search tool, caps and report template. Model ids come from
   `LLM_MODEL` and `JUDGE_MODEL`. Never hardcode a model id in an architecture.
8. Never print, log or commit a key. Keys exist only in `.env`; load it only with `--env-file`.
   Use `<your-key>` as a placeholder in examples.
9. Status columns are `String`. Never edit a committed migration: add a new revision.
10. Commit `uv.lock`. Do not loosen the FastAPI pin without a reason in `SPEC.md`.
11. The OpenAI SDK 3.x uses `httpx2`: pass a float timeout, never an `httpx` object. Send only
    `tool_choice="auto"`. Validate structured replies with Pydantic; `strict` is not a guarantee.
12. Set `finished_at` and similar values in Python. Relationships are `lazy="raise"`; load with
    `selectinload`. Assign a new dict to a JSONB column; in-place edits are not saved.

## How to work

- Build from `SPEC.md` in the order of section 13. The rows of the milestone are the brief of the
  agent that builds it. Build the smallest version that meets the milestone.
- Do not add an option, wrapper, dependency or file that `SPEC.md` does not ask for.
- A new assumption or a changed decision goes in `SPEC.md` (sections 10 and 11) in the same change.
- A shortcut with a known limit gets a comment: `# shortcut: <the limit>, <when to upgrade>`.
- One branch `step-N` and one pull request for each milestone. On a step branch: commit, push, open
  the PR and squash-merge with no question when ruff and pytest are green (`.claude/hooks/pr_gate.sh`
  checks it at the merge). Never push to `main` directly. Commits use the noreply address.
- Milestones that do not depend on each other are built at the same time, each in its own worktree
  (`.claude/worktrees/step-N`) with its own test database (`TEST_DATABASE_URL`), then merged one by one.
- Several libraries changed in the last weeks (SQLAlchemy 2.1, FastAPI native OpenTelemetry, OpenAI
  SDK 3.x). Check the current docs before you use an API from memory.

## Subagents

- `spec-auditor`: compares the repository with the requirements in `SPEC.md`. Run it after a milestone.
- `architecture-reviewer`: checks that the architectures differ in structure and stay comparable.
  Run it after a change in `app/agents/`.
