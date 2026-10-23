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
10. Commit `uv.lock`. Do not loosen the FastAPI pin without an ADR in `docs/adr/`.
11. The OpenAI SDK 3.x uses `httpx2`: pass a float timeout, never an `httpx` object. Send only
    `tool_choice="auto"`. Validate structured replies with Pydantic; `strict` is not a guarantee.
12. Set `finished_at` and similar values in Python. The models have no `relationship()`; if you add
    one, make it `lazy="raise"` and load with `selectinload`. Assign a new dict to a JSONB column;
    in-place edits are not saved.

## How to work

This repo follows Matt Pocock's skill flow. `REFERENCE.md` is the beginner's guide: what to type when.

- New work: `/mattpocock-skills:grill-with-docs` → `/mattpocock-skills:to-spec` (a GitHub issue) →
  `/mattpocock-skills:to-tickets` (ticket issues with blocking links) → `/mattpocock-skills:implement`
  per ticket (drives `/tdd`, ends with `/code-review`) → PR → `/mattpocock-skills:retro`.
  Issues filed by others go through `/mattpocock-skills:triage`; hard bugs through `/diagnosing-bugs`.
- Read `GLOSSARY.md` and the ADRs in `docs/adr/` for the area you touch, and use the glossary's terms in
  code, issues and tests. `SPEC.md` is the original build spec (frozen v1): read its requirements (`R*`)
  and decisions (`D*`) for context, but new work is tracked in GitHub Issues, not in `SPEC.md`.
- A decision that is hard to reverse, surprising and a real trade-off gets an ADR in `docs/adr/` in the
  same change. Smaller decisions and assumptions go in the spec or ticket issue.
- Do not add an option, wrapper, dependency or file that the spec or ticket does not ask for.
- A shortcut with a known limit gets a comment: `# shortcut: <the limit>, <when to upgrade>`.
- One branch and one pull request per ticket (or per spec with `/implement-spec`), named after it. On
  that branch: commit, push, open the PR and squash-merge with no question when ruff and pytest are
  green (`.claude/hooks/pr_gate.sh` checks it at the merge). Never push to `main` directly. Commits use
  the noreply address.
- Tickets with no blocking edge between them can be built at the same time, each in its own worktree
  (`.claude/worktrees/<branch>`) with its own test database (`TEST_DATABASE_URL`), then merged one by one.
- Several libraries changed in the last weeks (SQLAlchemy 2.1, FastAPI native OpenTelemetry, OpenAI
  SDK 3.x). Check the current docs before you use an API from memory.

## Subagents

- `spec-auditor`: compares the repository with the requirements in `SPEC.md`. Run it after a change
  that touches a requirement, and before a release.
- `architecture-reviewer`: checks that the architectures differ in structure and stay comparable.
  Run it after a change in `app/agents/`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for SiddharthMuramkar/search (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the root. See `docs/agents/domain.md`.
