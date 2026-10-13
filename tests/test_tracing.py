"""R13 (SPEC.md section 9): one run is one connected trace, and its spans carry the content.

An in-memory exporter is attached to the real tracer provider, so the spans come from the real
`tracing.step()`, `llm.complete()` and `search.search()`; only the two network functions are fake.
"""

import json

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode, format_span_id, format_trace_id

from app import llm, search, tracing

pytestmark = pytest.mark.anyio


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    tracing.provider.add_span_processor(processor)
    yield exporter.get_finished_spans
    # the SDK has no way to remove a processor: shutdown stops it from storing any more spans
    processor.shutdown()


async def run_react(client) -> dict:
    response = await client.post("/research/query", json={"query": "What is A?"})
    assert response.status_code == 202, response.text
    trace = await client.get(f"/research/{response.json()['id']}/trace")
    return trace.json()


async def test_a_run_is_one_trace_and_every_step_hangs_under_the_run_span(client, spans):
    trace = await run_react(client)
    finished = spans()
    root = next(span for span in finished if span.name == "research.run")
    steps = [span for span in finished if span is not root]
    assert root.parent is None  # the request is not the parent
    assert {span.context.trace_id for span in finished} == {root.context.trace_id}  # one trace id
    assert format_trace_id(root.context.trace_id) == trace["trace_id"]
    assert all(span.parent.span_id == root.context.span_id for span in steps)
    # a span for every stored step, and the same ids in the /trace payload
    assert [format_span_id(span.context.span_id) for span in steps] == [
        step["span_id"] for step in trace["steps"]
    ]
    assert {step["parent_span_id"] for step in trace["steps"]} == {
        format_span_id(root.context.span_id)
    }


async def test_spans_carry_the_plan_the_search_and_the_sources_of_the_report(client, spans):
    await run_react(client)
    by_name = {span.name: span.attributes for span in spans()}
    assert "What is A?" in by_name["plan"]["output"]  # the planned sub-questions
    arguments = json.loads(by_name["execute_tool web_search"]["gen_ai.tool.call.arguments"])
    assert arguments["query"] == "fake query"  # what was searched
    returned = json.loads(by_name["execute_tool web_search"]["gen_ai.tool.call.result"])
    assert [(r["url"], r["title"]) for r in returned] == [
        ("https://example.com/a", "A"),
        ("https://example.org/b", "B"),
    ]  # what came back
    assert tuple(by_name["synthesis"]["citations"]) == (1, 2)  # the source numbers of the report
    assert by_name["synthesis"]["gen_ai.request.model"] == llm.configured_model()


async def test_a_failed_search_puts_its_error_on_its_span_and_the_run_goes_on(
    client, spans, monkeypatch
):
    async def broken(query, *, max_results=5):
        raise RuntimeError("search is down")

    monkeypatch.setattr(search, "call_tavily", broken)
    trace = await run_react(client)
    failed = next(span for span in spans() if span.name == "execute_tool web_search")
    assert failed.status.status_code == StatusCode.ERROR
    assert "search is down" in failed.status.description
    assert [event.name for event in failed.events] == ["exception"]
    stored = next(step for step in trace["steps"] if step["type"] == "search")
    assert stored["error"] == "search is down" and stored["span_id"]
    assert trace["steps"][-1]["type"] == "synthesis"  # the run went on to the report
