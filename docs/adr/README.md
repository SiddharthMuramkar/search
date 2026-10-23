# Architecture Decision Records

| ADR | Decision |
|---|---|
| [0001](0001-plain-python-agents.md) | Agent architectures are plain Python, with no agent framework |
| [0002](0002-in-process-background-tasks.md) | Jobs run in-process with BackgroundTasks; a restart fails unfinished runs; one API process |
| [0003](0003-one-helper-writes-step-row-and-span.md) | `tracing.step()` writes the steps row and the span together; a run is its own trace |
| [0004](0004-caps-checked-in-step-helper.md) | The call and search caps are checked only in `tracing.step()`; the last model call is kept for the report |
| [0005](0005-service-writes-source-list.md) | The service writes the report's source list; only retrieved URLs can be cited |
| [0006](0006-comparison-metrics-and-blind-judge.md) | Sequential comparison runs, counted metrics, one blind pointwise judge, the `judge_mean_v1` winner rule |
| [0007](0007-compare-is-async.md) | `POST /research/compare` returns 202 and is polled; failed only if no run finished |
| [0008](0008-each-retry-is-a-step.md) | Each model-call retry is its own step and counts against the cap |
| [0009](0009-judge-step-outside-run-metrics.md) | The judge step is stored on the run but kept out of its trace and metrics |
| [0010](0010-two-architectures.md) | Two architectures, `react` and `orchestrator`; `reflection` is removed |

## When to add an ADR

Add one only when a decision passes all three tests: it is **hard to reverse**, it would be **surprising without context**, and it is the result of a **real trade-off**.
Number it after the highest existing file (`NNNN-slug.md`) and end it with its source.
New decisions go here, not in `SPEC.md` §11. `SPEC.md` is the frozen original build spec.
