# One helper writes each step to both PostgreSQL and the trace, and a run is its own trace

`GET /research/{id}/trace` must answer from the API, and the Jaeger viewer must show the same steps. So `tracing.step()` opens the OpenTelemetry span and writes the `steps` row together (a short session per write), and no step exists in only one place. The tracer provider is a module object, not the global provider, and `research.run` starts with an empty context. Each run is a trace of its own, and FastAPI's native request spans stay off because no global provider is set.

## Consequences

- Every step is written twice. `/trace` reads the database, which keeps the steps after Jaeger's in-memory store is gone.
- The HTTP request that started a run is not a span in the run's trace.

Source: SPEC.md D6, D14 (§11), §9
