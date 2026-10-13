# Deep Research API: working specification

This file is the source of truth for the build. The original brief is the take-home test
"Agentic Deep Research Platform" (backend engineering). Each requirement below has an id (`R1`...),
so that code, tests and reviews can refer to it.

## 1. Goal

A FastAPI service with a PostgreSQL database that exposes a deep research agent as an API.
A caller sends one query. The service stores it, returns a run id immediately, and does the research
in the background: plan, search the web, write a report with citations. The research can be done by
three structurally different agent architectures. A compare endpoint runs all of them on the same
query and stores an evaluation. Every run is stored and traced. There is no UI.

## 2. Grading rubric (from the brief)

| Criterion | Weight | What the reviewer looks for |
|---|---|---|
| System design and API contract | 20% | Clean FastAPI structure, sensible schemas, genuinely async background execution |
| Agent architecture design | 25% | Structurally distinct architectures with clear, defensible design rationale |
| Research quality and evaluation | 20% | Depth and grounding of the output, plus a real comparison method |
| Observability | 15% | Traces that show planning, search and synthesis as connected spans, not just logs |
| Code quality and persistence | 10% | PostgreSQL schema design, migrations, error handling, code organization |
| Documentation and judgment | 10% | README clarity, tradeoff reasoning, clarifying questions asked |

## 3. Requirements

| Id | Requirement | Rubric line | Milestone |
|---|---|---|---|
| R1 | `POST /research/query` accepts a query (architecture is optional), validates it, stores the run and returns 202 with the run id. It does not wait for the research. | System design | M2 |
| R2 | The research runs in a background task. A run moves through `queued -> planning -> running -> done` or `failed`. | System design | M2 |
| R3 | `GET /research/{id}/status` returns the status and timestamps. Unknown id gives 404. | System design | M2 |
| R4 | `GET /research/{id}/result` returns the report, its sources, the architecture and the model. A run that is not `done` gives 409. | System design | M2 |
| R5 | `GET /research/{id}/trace` returns the plan and the ordered steps (plan, search, model calls, synthesis) with their input and output, and the trace id. | Observability | M2 |
| R6 | `GET /research/architectures` lists the implemented architectures. | Architecture | M4 |
| R7 | The caller can select the architecture in the request. An unknown name gives 422. | Architecture | M2 |
| R8 | There are three architectures that differ in structure (section 7). They use the same model, search tool, caps and report template. | Architecture | M2, M4, M6 |
| R9 | Each architecture writes a plan first, uses web search, and writes a report whose citations refer only to sources that the run retrieved. | Research quality | M2, M3 |
| R10 | `POST /research/compare` runs the same query on all architectures in the background. `GET /research/compare/{id}` returns the stored comparison. | Evaluation | M5 |
| R11 | The comparison stores counted metrics and a judge score for each run, with the judge model and rubric version, and a winner chosen by a written rule. | Evaluation | M5 |
| R12 | PostgreSQL stores each run: query, architecture, status, timestamps, plan, every step, sources, report. The schema is created by Alembic migrations. | Persistence | M1 |
| R13 | Planning, search and synthesis are OpenTelemetry spans in one connected trace for each run. Spans carry what was planned, what was searched, what came back and which sources the report used. The trace id is stored on the run. | Observability | M2, M3 |
| R14 | Failures are recorded, not lost: a model error or a time limit gives `failed` with the reason; a failed search is an error step and the run continues; runs left unfinished by a restart are set to `failed` at startup. | Code quality | M2, M3 |
| R15 | API keys come only from environment variables. `.env.example` lists the names. No secret is in the repository. | Constraints | M1 |
| R16 | Deliverables: migrations, a README (setup, environment, how to run, how to view traces, architectures and evaluation, questions and assumptions) and a curl script that calls every route. | Documentation | M7 |

## 4. API contract

Seven routes: six from the brief, plus one GET for the stored comparison.

| Method | Route | Success | Errors |
|---|---|---|---|
| POST | `/research/query` | 202 `{id, status, architecture}` | 422 empty or whitespace-only query, or unknown architecture |
| GET | `/research/{id}/status` | 200 `{id, status, architecture, created_at, started_at, finished_at, error}` | 404 |
| GET | `/research/{id}/result` | 200 `{id, query, architecture, model, report, sources[], metrics}` | 404; 409 `{status, error}` if not `done` |
| GET | `/research/{id}/trace` | 200 `{id, trace_id, trace_url, plan, steps[]}` | 404 |
| GET | `/research/architectures` | 200 `[{name, description}]` | |
| POST | `/research/compare` | 202 `{comparison_id, run_ids, result_url}` | 422 |
| GET | `/research/compare/{id}` | 200 `{id, query, status, runs[], evaluations[], winner, method}` | 404 |

- Request body of `POST /research/query`: `{"query": "...", "architecture": "react"}`.
  `architecture` is optional; the default is `react`.
  Request body of `POST /research/compare`: `{"query": "..."}`.
- `POST /research/compare` returns 202 and not the comparison itself. Three research jobs take minutes,
  and the brief says research must not block the request. The body gives the GET route to poll.
- `GET /research/compare/{id}` shows each run's status. If one run fails, the comparison completes
  over the runs that finished. A comparison is `failed` only when no run finished.
- `run_ids` is a map `{architecture: run id}`. `result_url` is `/research/compare/{comparison_id}`.
  `winner` is a run id, or null.
- The 409 body is exactly `{status, error}` at the top level (no `detail` wrapper).
- `sources[]` item: `{n, url, title, snippet, cited}`. `steps[]` item:
  `{seq, type, name, input, output, error, span_id, parent_span_id, started_at, ended_at}`.
- `runs[]` item of a comparison: `{id, architecture, status, error, metrics}`. `evaluations[]` item:
  `{run_id, scores, reasons, judge_model, rubric_version}`; `scores` has exactly the keys
  `coverage`, `grounding`, `depth`, `clarity`.

## 5. Data model

Five tables. UUID primary keys. Status columns are `String`, not PostgreSQL enums. Timestamps are
`timestamptz`. JSONB holds values whose shape belongs to the agent, not to the schema.

| Table | Columns |
|---|---|
| `runs` | id, query, architecture, status, model, plan (JSONB), report, error, metrics (JSONB), trace_id, comparison_id (FK, null), created_at, started_at, finished_at |
| `steps` | id, run_id (FK), seq, type, name, input (JSONB), output (JSONB), error, span_id, parent_span_id, started_at, ended_at |
| `sources` | id, run_id (FK), step_id (FK), n, url, domain, title, snippet, cited |
| `comparisons` | id, query, status, winner_run_id (FK, null), method, created_at, finished_at |
| `evaluations` | id, run_id (FK), comparison_id (FK), scores (JSONB), reasons (JSONB), raw (JSONB), judge_model, rubric_version, created_at |

- `steps.type` is `search` for a search call, else the label of the model call:
  `plan`, `act`, `worker`, `critique`, `synthesis`, `judge`. The draft and the revision of
  `reflection` are both `synthesis` steps; `steps.name` says `draft` or `revise`.
- `runs.status` is `queued`, `planning`, `running`, `done` or `failed`. `comparisons.status` is
  `queued`, `running`, `done` or `failed`.
- `runs.model` is the configured `LLM_MODEL`. The model that really answered a call is stored in the
  output of its step.
- `sources.n` is the citation number of the source inside its run. `(run_id, url)` is unique.
- `evaluations` is its own table: a judgment has its own model and rubric version, and a run can be
  judged again with a new rubric without losing the old result.
- A foreign key that is not marked "null" above is `NOT NULL`. A step row therefore exists before
  its sources. `steps.span_id` is `NOT NULL`: the database refuses a step with no span.
- `runs.comparison_id` and `comparisons.winner_run_id` make a cycle. Both keys have a name, and the
  second one is added after both tables exist (`use_alter`).
- Defaults are set in Python (ids, `created_at`, `sources.cited`). There is no server default.

## 6. Code layout

```
app/
  __init__.py      empty: `fastapi dev app/main.py` needs `app` as a package
  main.py          FastAPI app, lifespan (calls fail_stale_runs), the 7 routes
  db.py            Base, engine, SessionLocal, Run, Step, Source, Comparison, Evaluation
  schemas.py       Pydantic request and response models
  llm.py           complete() -> call_openrouter()
  search.py        search() -> call_tavily()
  tracing.py       tracer provider, run context and caps, step() helper
  jobs.py          run_research(run_id), run_comparison(comparison_id), fail_stale_runs()
  evaluate.py      metrics(run, report, sources, latency_s) from M2; judge(run_id, comparison_id)
                   and pick_winner(rows) from M5
  agents/
    __init__.py    ARCHITECTURES: name -> (description, run function)
    react.py  orchestrator.py  reflection.py
migrations/        Alembic (async template); `alembic.ini` is next to it. The URL and the
                   metadata come from `app/db.py`
tests/             contract tests, fake model and fake search
scripts/e2e.sh     curl walk through every route
docker-compose.yml PostgreSQL 18 + Jaeger
```

Fixed interfaces (tests depend on them):

- `llm.complete(messages, *, step, name=None, tools=None, schema=None, model=None) -> Reply`: the
  only way to call the model. `step` becomes `steps.type` and `name` becomes `steps.name`.
  It checks the call cap, records the step and the span, then calls
  `llm.call_openrouter(messages, *, tools=None, schema=None, model=None) -> Reply` (network only).
  `model=None` means `LLM_MODEL`; the judge passes `JUDGE_MODEL`.
  `Reply` has `text`, `tool_calls`, `data` (parsed JSON when `schema` is given), `usage`, `model`.
  `usage` has the keys `prompt_tokens`, `completion_tokens`, `cost`.
- `search.search(query, *, max_results=5) -> list[dict]`: the only way to search. It checks the search
  cap, records the step, the span and the sources, then calls
  `search.call_tavily(query, *, max_results) -> list[dict]` (network only).
  Each result has `url`, `title`, `snippet`, `content`. `search` skips a URL that the run already
  has and gives out the citation number `n` under one lock, so parallel workers cannot collide on
  `(run_id, url)`.
- Structured replies use these Pydantic models as `schema`. `call_openrouter` returns the parsed
  JSON; `complete` validates it and retries one time:
  - `Plan`: `sub_questions: list[str]`
  - `Findings`: `summary: str`, `source_numbers: list[int]` (the reply of one worker)
  - `Critique`: `sufficient: bool`, `gaps: list[str]`, `follow_up_queries: list[str]`
  - `Judgment`: `coverage`, `grounding`, `depth`, `clarity`, each `{score: 1-5, reason: str}`
- A tool call in `Reply.tool_calls` is `{id, name, arguments}`; `arguments` is a parsed dict. The
  one tool is `web_search(query)`.
- `messages` are OpenAI-style dicts (`role`, `content`). A tool result goes back to the model as a
  `role: "tool"` message.
- Each architecture is `async def run(query: str) -> str` and returns the report body.
- `RUN_TIMEOUT_S` is a constant in `app/jobs.py`. `MAX_LLM_CALLS` and `MAX_SEARCHES` are constants
  in `app/tracing.py`, next to the run context, so `llm` and `search` do not import `jobs`. Code
  reads a cap through its module at call time (tests change `jobs.RUN_TIMEOUT_S`).
- `SessionLocal` is an `async_sessionmaker` with `expire_on_commit=False`.
- Code imports the modules (`from app import llm, search`) and calls through them. Tests replace only
  `call_openrouter` and `call_tavily`, so caps, steps and spans also run under test.
- The current run (id, counters) is held in a `contextvars.ContextVar` in `app/tracing.py`, set by
  the job.

## 7. Agent architectures

All three share: one model (`LLM_MODEL`), one search tool, the same caps, the same report template.
Only the control structure differs. This makes the comparison a comparison of architectures.

**Caps for each run:** 10 model calls, 6 searches, 300 seconds (D20). One comparison is at most about
33 model calls (3 runs + 3 judge calls).

**Plan first:** each architecture starts with a `plan` step. The run status is `planning` during this
step. The plan is stored in `runs.plan`.

**Report template:** title, summary, findings with numbered citations `[n]`, limits and open questions.
The service adds the source list itself from the `sources` rows, so a URL cannot be invented.
Target length: 600 to 1,000 words.

| | `react` | `orchestrator` | `reflection` |
|---|---|---|---|
| Idea | One agent in a loop | Planner + parallel workers | Draft, critic, revise |
| Control flow | plan -> loop: the model calls the search tool or stops -> report | plan (up to 4 sub-questions) -> one worker for each sub-question at the same time -> one synthesis call | plan -> one search pass -> draft -> critic -> new searches for the gaps -> revise |
| Who decides the next step | The model, at each turn | The planner decides the split; code does the fan-out and fan-in | The critic decides stop or continue, and what to search |
| Context | One growing message list | Each worker has its own context; the writer sees only short findings | Draft + evidence pool + the critique |
| Stop rule | The model stops calling the tool, or a cap | All workers returned | The critic says "sufficient", or 2 rounds |
| Call graph | Chain | Fan-out, fan-in | Cycle |
| Expected cost | Low to medium | Highest (most tokens) | Medium |
| Expected latency | Sequential, medium | Lowest wall-clock for its work (parallel) | Highest (sequential rounds) |
| Expected strength | Adapts each step to what it found | Breadth on queries that split into parts | Fewer gaps and unsupported claims |
| Fails when | The query has many sub-topics; context grows; stops early | The split is vague: duplicate work, gaps; hand-off loses detail | The critic shares the writer's blind spots |

- `reflection` has its own gather code and does not call the `react` loop. The critic must return
  follow-up queries, and the revision uses the new sources. A critique that cannot cause new searches
  would only polish the text.
- `orchestrator` workers return short findings with source numbers, not raw pages. The report is
  written in one call (parallel section writing gives disjoint reports).
- The expected values above are a hypothesis. The README reports the measured values.

## 8. Comparison and evaluation

- The runs of one comparison execute one after the other. Latency then does not include waiting for
  the other runs, and the provider rate limit is respected.
- **Metrics** (counted in code for every finished run, stored in `runs.metrics`; a failed run stores none): `latency_s`, `llm_calls`,
  `searches`, `prompt_tokens`, `completion_tokens`, `cost_usd` (sum of OpenRouter `usage.cost`),
  `sources_found`, `sources_cited`, `domains_cited`, `citation_validity` (share of `[n]` markers that
  refer to a stored source), `words`, `hit_cap`.
- A `[n]` marker that does not refer to a stored source is counted (`citation_validity` is the share
  before removal) and then removed from the stored report. A stored report therefore cites only
  retrieved sources.
- **Judge** (stored in `evaluations`): one model call for each report, with `JUDGE_MODEL` from a
  different model family than `LLM_MODEL`. The judge does not see the architecture name. It sees the
  query, the report and the snippets of the cited sources. It gives a 1 to 5 score with a one-line
  reason for `coverage`, `grounding`, `depth`, `clarity`. It is told not to reward length.
- **Winner rule** (`method = "judge_mean_v1"`): highest mean judge score; tie -> higher
  `citation_validity`; tie -> lower `latency_s`. Cost and latency are shown, not scored.
- If a judge call fails, the metrics are stored, that evaluation is missing, and the winner is chosen
  over the judged runs (null if none).
- **Known limits:** no reference answers, a small query set, one judge that is not calibrated against
  humans, pointwise scores are less stable than pairwise ones. A pairwise judge in both orders and a
  claim-by-claim citation check are the next steps.

## 9. Observability

- One root span for each run, named `research.run`, started with no parent, so a run is one trace.
  The trace id (32 hex characters) is stored in `runs.trace_id`.
- Child spans: one for each step. Model calls use the OpenTelemetry GenAI attribute names
  (`gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`). A search is an `execute_tool web_search` span.
- Span content (truncated): the plan text on the plan span; the query and the returned URLs and titles
  on a search span; the source numbers used on the synthesis span; the error on a failed span.
- `tracing.step()` opens the span and writes the `steps` row together, with a short database session
  for each write. `/trace` and the trace viewer therefore show the same steps.
- The tracer provider is created at import. The OTLP exporter is added only when
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Tests run without an exporter and still get trace ids.
- Local viewer: Jaeger in `docker-compose.yml`, UI at `http://localhost:16686`.
  `trace_url` is `http://localhost:16686/trace/<trace_id>`.

## 10. Questions and assumptions

Questions for the test owner. They were not sent: the time was too short to wait for an answer.
Each one has the default that the build uses:

1. How will you run the submission: with your own keys, on free tiers only? Must one comparison fit in
   a free daily quota? Default: yes. Stored example outputs are in the repository.
2. `POST /research/compare` starts three research jobs that take minutes. Is 202 plus a GET for the
   stored comparison acceptable, or must the POST block? Default: 202 plus GET.
3. Do you have reference queries? Default: no. We use our own 3 to 5 queries and list them in the README.

Access to the private repository is arranged with the submission.

Assumptions (each one is answered by the brief, so it was not asked):

| Assumption | Brief section |
|---|---|
| Quality decides which research is better. Cost and latency are stored and shown next to it. | 5: the comparison method is our design; document the tradeoffs |
| A run is limited by the caps in section 7; the report is 600 to 1,000 words with numbered citations. | 3.2 and 10: the agent plans alone; make reasonable engineering decisions |
| A run does not survive an API restart. One API process. | 2: "BackgroundTasks, a task queue, or any worker pattern you choose" |
| One stored judgment for each compare call. No aggregate ranking endpoint. | 4 and 5: "the same query"; "for a given query" |
| The `/trace` payload is our stored step list. | 4 and 6: the payload shape is ours; the content is listed |
| A free or a paid model is our choice. `.env.example` names the paid pair of the measured runs. With both model lines empty the service uses the free defaults of `app/llm.py`. | 1 and 7 |
| No authentication, no deployment, no UI. | 1 and 8 |
| A malformed run id gives 422 (the path type is a UUID); an unknown id gives 404. There is no maximum query length. | 4: the error shapes are ours |
| The free defaults for an empty model line are `nvidia/nemotron-3-super-120b-a12b:free` (generator) and `dots-studio/dots-3-note-preview:free` (judge), chosen on 13 Oct 2026 from the free models that list `tools` and `structured_outputs`. They are for a reviewer with a free key; the measured runs use the paid pair of `.env.example`. | 1 and 7: the model is our choice |
| Metric rounding: `latency_s` and `citation_validity` to 2 decimals, `cost_usd` to 6. `citation_validity` is 0.0 for a report with no marker. Markers are counted for each occurrence; a list such as `[1, 2]` is not parsed (shortcut). | 5: the comparison method is our design |
| The stored report ends with `## Sources`, with the cited sources only. `words` counts the body before that list. Brackets in a source title are escaped, so a title cannot look like a marker. | 5: the report template is ours |

## 11. Decisions

| Id | Decision | Reason | Tradeoff |
|---|---|---|---|
| D1 | FastAPI `BackgroundTasks`, in-process | The brief names it. No extra service. | A restart loses running jobs; one API process only. A queue with a worker is the upgrade. |
| D2 | Plain Python for the agents, no framework | Each architecture is one short file that can be read line by line; the structure is visible. | No built-in checkpoints or graph tooling. |
| D3 | OpenRouter through the OpenAI SDK; model ids in env vars | One key reaches many models; the default can be a free model. | Free models have low limits and change often. |
| D4 | Tavily for search, called with httpx | Free tier without a card; returns page text in the same call. | One provider. |
| D5 | OpenTelemetry + Jaeger | Named in the brief; no account for the reviewer; vendor-neutral. | Jaeger keeps traces in memory only; the database keeps the steps. |
| D6 | Steps in PostgreSQL and spans, written by one helper | `/trace` must answer from the API; the viewer must show the same. | Each step is written twice. |
| D7 | Metrics + one pointwise judge call for each report | Numbers can be checked; the judge covers quality. | See the limits in section 8. |
| D8 | Comparison runs one after the other | Fair latency; safe for 20 requests each minute. | A comparison takes longer. |
| D9 | `String` status, JSONB for agent-shaped data | Simple migrations. | Less checking by the database. |
| D10 | The service writes the source list of the report | A cited URL is always a retrieved URL. | The model cannot add a source it knows from training. |
| D11 | Caps are checked in one place, `tracing.step()`. A model call that is not the synthesis stops at `MAX_LLM_CALLS - 1`, so the last call is always kept for the report. A refused step sets `hit_cap` and raises `tracing.CapReached`. | One check for all architectures; a run at the cap still writes a report. | An architecture must catch `CapReached`. |
| D12 | Each retry of a model call is its own step and counts as a model call. | `llm_calls` equals the number of model steps in `/trace`. | A schema error costs one call of the cap. |
| D13 | The current run (id, counters, `seq`, citation numbers) is one mutable object in a `ContextVar`, changed under one lock. Code never calls `.set()` inside a worker. | `asyncio.gather` gives each task a copy of the context, so a `.set()` in a worker is lost. | Every writer takes the lock. |
| D14 | The tracer provider is a module object, not the global provider. `research.run` starts with an empty context. | A run is a trace of its own; FastAPI's native request spans stay off. | The HTTP request is not a span in the trace. |
| D15 | `call_openrouter` makes one `AsyncOpenAI` client for each call (float timeout 120 s, the SDK's default retries). A structured reply uses `response_format` json_schema with no `strict`, and the JSON is parsed here and validated by `complete()`. `usage.cost` is OpenRouter's extra field. | Simple, and a provider that ignores `strict` still works. | No connection reuse. |
| D16 | `call_tavily` asks for the page text in the same call: `snippet` is Tavily's summary, `content` is the page text cut at 4,000 characters. Any HTTP error is raised as `Tavily <status>: <body>`. | D4: one call gives both. The body names the reason (432 is the plan limit). | A long page loses its end. |
| D17 | The OTLP exporter is added to the tracer provider only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and not empty, with a 1 s batch delay. | Tests run with no exporter; a trace shows in Jaeger within seconds. | A crash can lose the last second of spans. |
| D18 | The judge step (`type = "judge"`) is stored on the judged run with `seq` continuing, after `research.run` ended. Its span is a one-span trace of its own (`parent_span_id` null, not in `runs.trace_id`). Judge steps are not counted in `llm_calls`, tokens or `cost_usd`. | The metrics are frozen when the run ends, before the judge runs; a judge call is not research work, so the architectures stay comparable. | An exception to D12 and section 9: `/trace` lists the judge step, Jaeger does not show it in the run's trace, and `llm_calls` equals the model steps in `/trace` except `judge`. |
| D19 | `reflection` splits the 6 searches: the first pass searches at most 3 sub-questions, and the critic's follow-up queries get at most 3 in all rounds. A critic that says `sufficient` ends the loop with no revision. A round with no follow-up budget left, or a critique with gaps but no query, also ends the loop: it could not cause a search and would only polish the text. | The first pass cannot use the cap that the critique needs; a revision with no new evidence would only polish the text. | Fewer searches in the first pass than `react` may use. |
| D20 | The time limit of a run is 300 seconds, not 180. | A dry run with the paid models (GLM-5.3, canned search) took 35 s for `orchestrator`, 89 s for `react` and 173 s for `reflection`. Live search adds time, and `reflection` is the slowest by design (SPEC.md section 7), so 180 s would cut off the architecture under test and make the comparison unfair. | A stuck run holds its place longer before it fails. |

## 12. Failure handling

| Event | Result |
|---|---|
| Run longer than 300 seconds | `failed`, `error = "time limit"` |
| Model call fails after the SDK retries (429, 5xx, network) | `failed` with the provider message |
| Model returns JSON that does not match the schema | one retry, then `failed` |
| Search call fails | the step is stored with its error; the run continues |
| Cap reached | the architecture writes the report with what it has; `hit_cap = true` |
| Orchestrator: the plan has no sub-questions | the query is the one sub-question, so the report always has at least one search |
| Orchestrator: a worker fails with a real error | the other workers finish, then the run fails with the first error. Known cost: they still spend calls until the slowest returns (at most the 300 second limit). A `TaskGroup` would cancel them but would hide the error text in an `ExceptionGroup`. |
| API restart during a run | at startup, runs in `queued`, `planning` or `running` are set to `failed`, and so are comparisons in `queued` or `running` |
| SIGTERM of the API during a run | uvicorn waits for the running job (up to the time limit). Only a forced exit (a second signal, SIGKILL, a crash) leaves the run to the startup sweep. |

## 13. Milestones

| Milestone | Content | Requirements | Done when |
|---|---|---|---|
| M1 | Runtime dependencies, `docker-compose.yml` (PostgreSQL with the databases `research` and `research_test`, Jaeger), models, Alembic async setup, first migration | R12, R15 | `alembic upgrade head` creates the 5 tables and `alembic check` finds no difference; `create_all`, `drop_all`, `create_all` work on `research_test` |
| M2 | The full single-run path with a fake model: single-run routes, background job, `tracing.py`, `llm.py` and `search.py` (the two network functions exist as stubs that raise; M3 writes them), `react`, the counted metrics of section 8, startup sweep. `app/jobs.py` has no `run_comparison` before M5 | R1-R5, R7-R9, R13, R14 | the single-run contract tests pass with the fake model and the fake search, with three more tests: the one retry on JSON that does not match the schema, `hit_cap`, and the removal of a citation marker that has no source |
| M3 | The real world: `call_openrouter`, `call_tavily`, the OTLP exporter and Jaeger, the default model ids, `scripts/e2e.sh` for the single-run routes | R9, R13, R14 | a real POST returns before the research ends (a poll shows `planning` or `running`); a real run shows one connected trace in Jaeger; a run that a restart killed is `failed` after startup; a test with an in-memory span exporter proves one trace id, the parent links and the span content; one full real report has been read and accepted for depth and grounding |
| M4 | `orchestrator`, `/research/architectures` | R6, R8 | the architecture review passes for 2 designs; a test proves that for an `orchestrator` run `llm_calls` and `searches` equal the stored steps and no `seq` repeats |
| M5 | Compare and the judge | R10, R11 | the compare tests pass, with a test of the winner rule on fixed scores |
| M6 | `reflection` | R8 | the architecture review passes for 3 designs |
| M7 | README with: setup, environment, how to run, how to view traces, the questions asked with their answers, a results table, and its own section "Architectures and evaluation" (for each architecture: design, rationale, and cost / latency / quality against the others with the measured numbers; then the judge method and its limits). Also: the other routes in `scripts/e2e.sh`, real runs on 3 to 5 queries, one run and one comparison on the free default models, `examples/` with stored outputs | R16 | `scripts/e2e.sh` calls all 7 routes and exits 0; the full audit passes |

Build order: M1 and M2 one after the other. M3 to M6 are built at the same time, each on its own
branch in its own worktree, with the fake model, and merge in the order M3, M4, M5, M6. A milestone
that is not green is not merged.

Cut line: after M5 the submission is complete against the brief with two architectures. M6 merges
last and is the first to stay out. M7 is never skipped.

Tests: pytest with the AnyIO plugin and `httpx.AsyncClient` on the ASGI app. The database is the
compose PostgreSQL, database `research_test`. Each test reads only the run it created. The test
client completes the background job before the POST returns, so tests do POST then GET with no
polling, and insert rows directly for the `queued` and 409 cases.

## 14. Out of scope

Authentication, rate limiting, deployment, a UI, a durable queue, more than one API process,
streaming, a Postman collection (the curl script covers every route; `/openapi.json` can be imported
into Postman).
