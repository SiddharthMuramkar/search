# Deep Research API

## What it is

A FastAPI service with a PostgreSQL database. It runs a deep research agent in the background. You
send one query and get a run id at once. The service plans, searches the web and writes a report
with numbered citations. Every run, step, source and report is stored. Every run is one
OpenTelemetry trace. There is no UI and no authentication.

Two agent architectures do the research: `react` and `orchestrator`. `POST /research/compare` runs
both on the same query, has a second model judge the reports, and stores the metrics, the scores and
a winner. The build spec is `SPEC.md` (ids like `R1` and `D1` refer to it).

Where the code is:

- `app/main.py`: the 7 routes. `app/jobs.py`: the background jobs. `app/agents/`: one file per
  architecture.
- `app/llm.py` and `app/search.py`: the only doors to the model and to web search.
- `app/tracing.py`: the caps and `step()`, which writes one span and one `steps` row together.
- `app/evaluate.py`: the metrics, the judge and the winner rule. `app/db.py`: the tables.
- `tests/`: contract tests with a fake model and a fake search. `scripts/e2e.sh`: a curl walk
  through all 7 routes.

## Quick start

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker, curl and jq.

```bash
uv sync                                   # install
docker compose up -d                      # PostgreSQL 18 and Jaeger
cp .env.example .env                      # then put your keys in .env
uv run alembic upgrade head               # create the tables
uv run --env-file .env fastapi dev app/main.py --no-reload
uv run pytest -q                          # in a second terminal; needs Docker, no keys
```

The API listens on `http://localhost:8000`; the interactive docs are at `/docs`. Without
`--no-reload`, a file change reloads the app and kills a running job.

## Environment

Keys come only from environment variables. `.env` is in `.gitignore`. `.env.example` uses
`<your-key>` as the placeholder.

| Variable | Meaning |
|---|---|
| `OPENROUTER_API_KEY` | Key for model calls (https://openrouter.ai/keys). |
| `LLM_MODEL` | OpenRouter model id for both architectures. Empty: the free default `nvidia/nemotron-3-super-120b-a12b:free`. |
| `JUDGE_MODEL` | Model id of the judge, from another family. Empty: the free default `dots-studio/dots-3-note-preview:free`. |
| `TAVILY_API_KEY` | Key for web search (https://app.tavily.com, free tier 1,000 searches a month). |
| `DATABASE_URL` | Must start with `postgresql+asyncpg://`. `.env.example` matches `docker-compose.yml`. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Where spans go. `http://localhost:4318` is the Jaeger container. Empty: no export. |
| `OTEL_SERVICE_NAME` | The service name Jaeger shows (`deep-research-api`). |

## The 7 routes

| Method | Route | Success | Errors |
|---|---|---|---|
| POST | `/research/query` | 202 `{id, status, architecture}` | 422 |
| GET | `/research/{id}/status` | 200 status and timestamps | 404 |
| GET | `/research/{id}/result` | 200 report, sources, metrics | 404; 409 if not `done` |
| GET | `/research/{id}/trace` | 200 plan, ordered steps, trace id and link | 404 |
| GET | `/research/architectures` | 200 `[{name, description}]` | |
| POST | `/research/compare` | 202 `{comparison_id, run_ids, result_url}` | 422 |
| GET | `/research/compare/{id}` | 200 runs, evaluations, winner, method | 404 |

```bash
BASE=http://localhost:8000

# 1. Start a run. "architecture" is optional: react (default) or orchestrator.
curl -s -X POST $BASE/research/query -H 'Content-Type: application/json' \
  -d '{"query": "How do HTTP/2 and HTTP/3 differ?", "architecture": "react"}'
RUN=<run-id>

# 2. Status: queued, planning, running, done or failed.
curl -s $BASE/research/$RUN/status
# 3. Result: report, sources, metrics. 409 until the run is done.
curl -s $BASE/research/$RUN/result
# 4. Trace: the plan, every step with input and output, the trace id and the Jaeger link.
curl -s $BASE/research/$RUN/trace
# 5. The architectures.
curl -s $BASE/research/architectures

# 6. Compare: both architectures, one after the other, then the judge. Takes minutes.
curl -s -X POST $BASE/research/compare -H 'Content-Type: application/json' \
  -d '{"query": "How do HTTP/2 and HTTP/3 differ?"}'
CMP=<comparison-id>
# 7. The stored comparison. Poll until "status" is done or failed.
curl -s $BASE/research/compare/$CMP
```

All 7 in one go: `BASE=http://localhost:8000 bash scripts/e2e.sh`.

## How a run flows

1. `POST /research/query` stores a run with status `queued` and returns 202.
2. A background job opens the root span `research.run`. It has no parent, so each run is its own
   trace. It carries the run id, the architecture and the query.
3. The architecture runs. Each model call goes through `llm.complete`, each search through
   `search.search`. Both call `tracing.step()`. It checks the caps, opens a span and writes a
   `steps` row with the same span id.
4. The job counts the metrics, adds the source list from the stored sources, and sets `done`.

`tracing.step()` opens and closes each span before the next one starts. A step span never
contains another step. So every step span is a direct child of `research.run`. "Chain" and
"fan-out" describe the timing on the Jaeger timeline, not deeper nesting.

react: the spans follow one another.

```
research.run
├─ plan
├─ act                        model asks for a search
├─ execute_tool web_search
├─ act                        model searches again or stops
├─ execute_tool web_search
├─ act                        no tool call: the loop ends
└─ synthesis                  the report
```

orchestrator: the workers run at the same time, so their spans overlap in time.

```
research.run
├─ plan                       up to 4 sub-questions
├─ execute_tool web_search    worker 1 search  ┐
├─ execute_tool web_search    worker 2 search  │ at the same time
├─ worker                     worker 1 summary │
├─ worker                     worker 2 summary ┘
└─ synthesis                  one call writes the report
```

In each worker, the search span ends before its `worker` model-call span starts. They are siblings,
not parent and child.

Every span is also a row in `steps`, with the same `span_id` and `parent_span_id`. So
`GET /research/{id}/trace` (from the database) and Jaeger show the same steps.

The judge step of a comparison is stored as a `steps` row on the judged run. Its span `judge`
starts after `research.run` has ended, so it is a one-span trace of its own.

## How to view traces

Open Jaeger at http://localhost:16686, choose the service `deep-research-api` and search. Or use
the `trace_url` from `GET /research/{id}/trace`, a direct link to the run's trace.

- Model-call spans (`plan`, `act`, `worker`, `synthesis`, `judge`) have the GenAI attributes
  `gen_ai.request.model`, `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`, the answer
  and the citation numbers used.
- Search spans (`execute_tool web_search`) have the query and the URLs and titles found.
- A failed step has its error on the span.

Span attributes are cut at 1,000 characters; the `steps` rows keep the full text. Jaeger keeps
traces in memory only; the database keeps the steps.

## Architectures and evaluation

Both architectures use the same model, the same search tool, the same caps and the same report
template. Only the control structure differs.

- Caps per run: 10 model calls, 6 searches, 300 seconds. A model call that is not `synthesis` stops
  one call early, so a run at the cap can still write its report.
- Both start with a `plan` step. The report has a title, a summary, findings with `[n]` citations,
  and limits (600 to 1,000 words). The service writes the source list itself, so a cited URL is
  always a retrieved URL.

| | `react` | `orchestrator` |
|---|---|---|
| Idea | One agent in a loop | Planner and parallel workers |
| Who decides the next step | The model, each turn | The planner splits; code fans out and in |
| Context | One growing message list | Each worker has its own; the writer sees short findings |
| Stop rule | The model stops calling the tool, or a cap | All workers returned |
| Trace shape | A chain | Fan-out, fan-in |
| Fails when | Many sub-topics; context grows; stops early | The split is vague; the hand-off loses detail |

**Comparison method.** `POST /research/compare` makes one run per architecture on the same query.
They run one after the other, so latency is fair. Then each finished report is judged.

- **Metrics**, counted in code: `latency_s`, `llm_calls`, `searches`, tokens, `cost_usd`,
  `sources_found`, `sources_cited`, `domains_cited`, `citation_validity` (share of `[n]` markers
  that point to a stored source), `words`, `hit_cap`. Judge calls are not counted.
- **Judge**: one call per report with `JUDGE_MODEL`. It does not see the architecture name. It sees
  the query, the report and the cited snippets. It scores `coverage`, `grounding`, `depth` and
  `clarity` from 1 to 5, with a reason each.
- **Winner rule** `judge_mean_v1`: highest mean score wins. A tie goes to higher
  `citation_validity`, then lower `latency_s`.
- If a judge call fails, that evaluation is missing and the winner is picked from the others.

**Limits of the method.** No reference answers and a small query set. One judge, not calibrated
against humans. The judge reads snippets, not full pages. Each architecture runs once per query, so
there is no estimate of run-to-run variation. `citation_validity` checks that a source exists, not
that it supports the claim.

## Questions and assumptions

Questions for the test owner (not sent; each has the default the build uses):

1. Must one comparison fit free tiers? **Default: yes.** Empty model lines use free models. A
   comparison is at most 22 model calls and 12 searches.
2. Is 202 plus a GET acceptable for compare? **Default: yes.**
3. Are there reference queries? **Default: no.** We use our own.

Assumptions:

- Quality decides the winner. Cost and latency are shown, not scored.
- A run does not survive an API restart. There is one API process.
- The `/trace` payload is our stored step list.
- No authentication, no deployment, no UI.
- A malformed id gives 422, an unknown id gives 404.

## Known limits

- **A restart loses a running job.** It lives in the API process (`BackgroundTasks`). At startup,
  every unfinished run and comparison is set to `failed`.
- **One API process only.** A queue with a worker is the upgrade.
- **No authentication or rate limiting.**
- **`trace_url` always points to `http://localhost:16686`.**
- **Free models** allow about 20 requests a minute and are retired often (`app/llm.py`).
- **The caps cut research short.** At the cap the report uses what the run has (`hit_cap`). At 300
  seconds the run fails with `time limit` and no report.
- **A failed worker fails the `orchestrator` run**, after the other workers finish.
- **Page text is cut at 4,000 characters** (`app/search.py`).
- **A list like `[1, 2]` is not parsed as citations** (`app/llm.py`).
- **The tests use a fake model and search.** They prove structure, caps, traces and the contract,
  not research quality.
