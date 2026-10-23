# Two architectures: `react` and `orchestrator`; `reflection` is removed

The service keeps two architectures. `react` is one agent in a loop, so its trace is a chain of spans. `orchestrator` is a planner, parallel workers and one writer, so its trace fans out and fans in. `reflection` (draft, critic, revise) is deleted with its tests, its `critique` step type, the `name=` argument of `llm.complete` that only it used, and D19.

The brief asks for 2 to 3 architectures. Two that differ in who decides the next step (the model against the code) and in call graph (chain against fan-out) meet it. Each extra architecture is more code to keep comparable and more trace shapes to explain. SPEC.md already named `reflection` as the first thing to cut.

## Considered Options

- **Keep all three.** Rejected: `reflection` was the slowest (173 s in the dry run), the most code, and its cycle is the hardest trace to read.
- **Keep `reflection` instead of one of the others.** Rejected: dropping `react` loses the simplest baseline, and dropping `orchestrator` loses the only parallel trace.

## Consequences

No architecture has a critic, so no architecture checks its own report for gaps. A comparison runs 2 architectures and judges 2 reports. The schema is unchanged: `architecture` and `steps.type` are strings.

Source: YAGNI cut, October 2026; SPEC.md cut line (§13)
