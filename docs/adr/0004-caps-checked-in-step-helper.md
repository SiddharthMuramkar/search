# The call and search caps are checked only in `tracing.step()`, and the last model call is kept for the report

All architectures share the caps (10 model calls, 6 searches, 300 s), so the call and search counts are checked in one place, `tracing.step()`, rather than in each architecture. The 300 s limit is enforced separately, by `jobs.py` around the whole run. A model call that is not `synthesis` is refused at `MAX_LLM_CALLS - 1`, so the last call is always left for the report. A refused step sets `hit_cap` and raises `tracing.CapReached`, and the architecture catches it and writes its report from what it has. A run that hits a cap is therefore `done` with `hit_cap = true`, not `failed`.

## Consequences

Every architecture must catch `CapReached` around its gather phase. A new architecture that does not will fail at the cap instead of writing a report.

Source: SPEC.md D11 (§11), §12
