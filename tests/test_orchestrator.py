"""Tests of the `orchestrator` architecture (M4, SPEC.md section 7).

Each test wraps the fake model and the fake search that the `client` fixture has set.
"""

import asyncio
from datetime import datetime

import pytest

from app import llm, search, tracing

pytestmark = pytest.mark.anyio


async def run_orchestrator(client) -> tuple[dict, list[dict]]:
    response = await client.post(
        "/research/query", json={"query": "What is A?", "architecture": "orchestrator"}
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    status = (await client.get(f"/research/{run_id}/status")).json()
    steps = (await client.get(f"/research/{run_id}/trace")).json()["steps"]
    return status, steps


async def test_metrics_equal_the_stored_steps_and_no_seq_repeats(client):
    status, steps = await run_orchestrator(client)
    run_id = status["id"]
    metrics = (await client.get(f"/research/{run_id}/result")).json()["metrics"]
    assert metrics["searches"] == sum(step["type"] == "search" for step in steps) == 2
    assert metrics["llm_calls"] == sum(step["type"] != "search" for step in steps) == 4
    seqs = [step["seq"] for step in steps]
    assert len(set(seqs)) == len(seqs)
    types = [step["type"] for step in steps]
    assert types[0] == "plan" and types[-1] == "synthesis"
    assert types.count("plan") == types.count("synthesis") == 1 and types.count("worker") == 2


async def test_the_workers_run_at_the_same_time(client, monkeypatch):
    fake = search.call_tavily

    async def slow(query, *, max_results=5):
        await asyncio.sleep(0.2)
        return await fake(query, max_results=max_results)

    monkeypatch.setattr(search, "call_tavily", slow)
    _, steps = await run_orchestrator(client)
    spans = sorted(
        (datetime.fromisoformat(s["started_at"]), datetime.fromisoformat(s["ended_at"]))
        for s in steps
        if s["type"] == "search"
    )
    # the second search starts before the first one ends; run one after the other it could not
    assert spans[1][0] < spans[0][1]


async def test_every_step_is_a_child_of_the_run_span(client):
    _, steps = await run_orchestrator(client)
    assert {"worker", "search"} <= {step["type"] for step in steps}
    parents = {step["parent_span_id"] for step in steps}
    assert len(parents) == 1 and None not in parents  # the one parent is the research.run span


@pytest.mark.parametrize(
    ("cap", "metric", "value"), [("MAX_SEARCHES", "searches", 1), ("MAX_LLM_CALLS", "llm_calls", 3)]
)
async def test_a_cap_still_gives_a_report(client, monkeypatch, cap, metric, value):
    monkeypatch.setattr(tracing, cap, value)
    status, steps = await run_orchestrator(client)
    metrics = (await client.get(f"/research/{status['id']}/result")).json()["metrics"]
    assert status["status"] == "done" and metrics["hit_cap"] is True
    assert metrics[metric] == value and steps[-1]["type"] == "synthesis"
    assert metrics["llm_calls"] == sum(step["type"] != "search" for step in steps)


async def test_a_failed_search_gives_empty_findings_and_the_run_continues(client, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("search down")

    monkeypatch.setattr(search, "call_tavily", broken)
    status, steps = await run_orchestrator(client)
    types = [step["type"] for step in steps]
    assert status["status"] == "done" and "worker" not in types and types[-1] == "synthesis"


async def test_a_worker_that_fails_fails_the_run_with_the_reason(client, monkeypatch):
    fake = llm.call_openrouter

    async def worker_down(messages, *, tools=None, schema=None, model=None):
        if schema is not None and schema.__name__ == "Findings":
            raise RuntimeError("worker down")
        return await fake(messages, tools=tools, schema=schema, model=model)

    monkeypatch.setattr(llm, "call_openrouter", worker_down)
    status, steps = await run_orchestrator(client)
    assert status["status"] == "failed" and "worker down" in status["error"]
    assert "synthesis" not in [step["type"] for step in steps]
