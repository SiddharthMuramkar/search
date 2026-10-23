# Agent architectures are plain Python, with no agent framework

The architectures (`react` and `orchestrator`, ADR-0010) exist to be compared, so their control structure must be visible. Each one is a single short file in `app/agents/` built only on `llm.complete` and `search.search`, which record every step through `tracing.step()`, plus `tracing.CapReached` and `tracing.update_run`, with no LangGraph, CrewAI or similar framework underneath.

## Considered Options

- **An agent framework (LangGraph and the like).** Rejected: the chain and the fan-out would live in the framework's graph runtime instead of in code a reader can follow line by line, and the framework's own calls would sit between the architectures and the shared caps and step recording.

## Consequences

There are no built-in checkpoints, resumable graphs or graph tooling. A run cannot resume after a crash (see ADR-0002).

Source: SPEC.md D2 (§11)
