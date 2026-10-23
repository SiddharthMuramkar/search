# The judge step is stored on the judged run but kept out of its trace and metrics

A run's metrics are frozen when the run ends, before the judge runs, and a judge call is not research work. The judge step (`type = "judge"`) is stored on the judged run with `seq` continuing, so `/trace` lists it. Its span is a one-span trace of its own (`parent_span_id` null, not in `runs.trace_id`), and it is not counted in `llm_calls`, tokens or `cost_usd`. This keeps the architectures comparable.

## Consequences

This is a deliberate exception to ADR-0003 and ADR-0008. `/trace` shows the judge step, but Jaeger does not show it in the run's trace, and `llm_calls` equals the model steps in `/trace` except `judge`.

Source: SPEC.md D18 (§11)
