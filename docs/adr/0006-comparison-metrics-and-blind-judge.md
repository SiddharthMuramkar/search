# Comparisons score runs with counted metrics and one blind pointwise judge, with a fixed winner rule

A comparison runs `react`, `orchestrator` and `reflection` on the same query one after the other, so latency does not include waiting for the other runs and the provider rate limit is respected. Every finished run gets metrics counted in code. Each report also gets one judge call from `JUDGE_MODEL`, a different model family than `LLM_MODEL`. The judge does not see the architecture name and scores `coverage`, `grounding`, `depth` and `clarity` from 1 to 5. The winner (`method = "judge_mean_v1"`) is the highest mean judge score, then higher `citation_validity`, then lower `latency_s`. Cost and latency are shown but not scored.

## Considered Options

- **Pairwise judging in both orders.** More stable than pointwise scores, but it needs more calls per comparison. It is the recorded next step, together with a claim-by-claim citation check.
- **Running the three runs in parallel.** Faster, but latencies would include contention and the free-tier rate limit would be exceeded.

## Consequences

The judge has no reference answers and is not calibrated against humans. If a judge call fails, the winner is chosen over the judged runs, or null if there are none.

Source: SPEC.md D7, D8 (§11), §8
