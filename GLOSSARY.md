# Glossary

The terms needed to explain the service. Use these words in code, issues and tests.

## Research

**Run**: One attempt by one Architecture to answer one query. It ends with a stored report, or fails with an error.

**Step**: One recorded unit of work in a Run: a model call or a search. Each Step is one row in `steps` and one Span.

**Plan**: The first Step of every Run. The model splits the query into 2 to 4 sub-questions.

**Act**: In react, one model call that either asks for a search or stops the loop.

**Worker**: In orchestrator, one sub-question handled on its own: one search, then one model call that returns a short summary with source numbers.

**Synthesis**: The model call that writes the report from what the Run gathered.

**Source**: One web page a search returned. It gets a number `n` that is unique within the Run.

**Citation**: A marker `[n]` in the report that points to the Source with that number.

**Cap**: The most model calls (10) or searches (6) one Run may make. A Run at a Cap still writes its report and is marked `hit_cap`.

## Architectures

**Architecture**: One control structure for a Run. Both share the model, the search tool, the Caps and the report template.

**react**: One agent in a loop. The model decides at each turn whether to search again or stop. Its spans form a chain.

**orchestrator**: The Plan splits the query, one Worker per sub-question runs at the same time, and one Synthesis writes the report. Its spans fan out and fan in.

## Comparison

**Comparison**: One query run by both Architectures, one after the other, then judged.

**Judge**: A model from another family that scores each report from 1 to 5 on coverage, grounding, depth and clarity. It does not know which Architecture wrote it.

**Evaluation**: The stored scores and reasons of one Judge call for one Run.

**Winner rule**: `judge_mean_v1`. Highest mean score wins; a tie goes to higher citation validity, then lower latency.

## Observability

**Trace**: All the Spans of one Run, under one Root span. The judge call is a separate one-span trace.

**Span**: One timed operation in a Trace, with a name, a start, an end and Attributes.

**Root span**: The span with no parent. Here it is `research.run`, one per Run.

**Parent span / child span**: A child span is opened while its parent is the current span. Every Step span is a child of `research.run`.

**Trace id**: The id shared by all Spans of one Trace. It is stored on the Run.

**Span id**: The id of one Span. It is stored on the matching `steps` row, so the database and Jaeger line up.

**Attribute**: A key and value on a Span, such as `gen_ai.request.model` or the search query.

**Jaeger**: The trace viewer in the compose stack, at http://localhost:16686.

**OTLP exporter**: The part of the OpenTelemetry SDK that sends Spans to Jaeger over HTTP (`OTEL_EXPORTER_OTLP_ENDPOINT`).
