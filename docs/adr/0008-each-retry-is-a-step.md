# Each retry of a model call is its own step and counts against the cap

A reply that fails schema validation is retried once, and the retry is recorded as a separate step that counts as a model call. Then `llm_calls` always equals the number of model steps in `/trace`, at the cost that a schema error uses one call of the cap. The one exception is the judge step (ADR-0009).

Source: SPEC.md D12 (§11), §12
