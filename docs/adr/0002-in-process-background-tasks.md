# Research jobs run in-process with FastAPI BackgroundTasks, not a queue

The brief allows any worker pattern, so research and comparison jobs run as FastAPI `BackgroundTasks` inside the single API process, which keeps the service to the API plus PostgreSQL with no broker or worker. A run therefore does not survive a restart: at startup, `jobs.fail_stale_runs` sets runs in `queued`, `planning` or `running`, and comparisons in `queued` or `running`, to `failed`.

## Consequences

- Only one API process may run. A second process would sweep the first one's live runs at startup and split jobs across processes with no coordination.
- The job receives `run.id` and opens its own database sessions. The run row is committed before `add_task`.
- On SIGTERM uvicorn waits for the running job: up to 300 s for a research run, and up to about three times that plus the judge calls for a comparison. Only a forced exit leaves runs for the sweep.
- The upgrade path is a queue with a separate worker.

Source: SPEC.md D1 (§11), §12
