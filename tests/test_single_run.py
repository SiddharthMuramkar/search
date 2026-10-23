"""The three single-run tests of milestone M2 (SPEC.md sections 8, 12 and 13).

Each test wraps the fake model that the `client` fixture has set, to make one case happen.
"""

import re

import pytest

from app import db, llm, search, tracing

pytestmark = pytest.mark.anyio

USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0}


async def submit(client) -> str:
    response = await client.post("/research/query", json={"query": "What is A?"})
    assert response.status_code == 202, response.text
    return response.json()["id"]


@pytest.mark.parametrize(("bad_replies", "status"), [(1, "done"), (2, "failed")])
async def test_json_that_does_not_match_the_schema_is_retried_once(
    client, monkeypatch, bad_replies, status
):
    fake = llm.call_openrouter
    left = bad_replies

    async def bad_plan(messages, *, tools=None, schema=None, model=None):
        nonlocal left
        reply = await fake(messages, tools=tools, schema=schema, model=model)
        if schema is llm.Plan and left:
            left -= 1
            reply.data = {"sub_questions": "not a list"}
        return reply

    monkeypatch.setattr(llm, "call_openrouter", bad_plan)
    run_id = await submit(client)
    run = (await client.get(f"/research/{run_id}/status")).json()
    steps = (await client.get(f"/research/{run_id}/trace")).json()["steps"]
    plans = [step for step in steps if step["type"] == "plan"]
    assert run["status"] == status
    assert len(plans) == 2 and "sub_questions" in plans[0]["error"]  # one retry, not two
    if status == "done":
        assert plans[1]["error"] is None
    else:
        assert "validation error for Plan" in run["error"] and len(steps) == 2


async def test_a_reply_that_is_not_json_is_retried_and_its_tokens_count(client, monkeypatch):
    fake = llm.call_openrouter
    left = 1

    async def truncated_plan(messages, *, tools=None, schema=None, model=None):
        nonlocal left
        reply = await fake(messages, tools=tools, schema=schema, model=model)
        if schema is llm.Plan and left:
            left -= 1
            reply.data, reply.text = None, '{"sub_questions": ["cut'
        return reply

    monkeypatch.setattr(llm, "call_openrouter", truncated_plan)
    run_id = await submit(client)
    result = (await client.get(f"/research/{run_id}/result")).json()
    steps = (await client.get(f"/research/{run_id}/trace")).json()["steps"]
    plans = [step for step in steps if step["type"] == "plan"]
    assert len(plans) == 2 and plans[0]["error"] and plans[1]["error"] is None
    model_steps = [step for step in steps if step["type"] != "search"]
    assert result["metrics"]["prompt_tokens"] == USAGE["prompt_tokens"] * len(model_steps)


@pytest.mark.parametrize(
    ("cap", "metric", "value"), [("MAX_SEARCHES", "searches", 2), ("MAX_LLM_CALLS", "llm_calls", 4)]
)
async def test_a_cap_stops_the_loop_and_the_report_is_still_written(
    client, monkeypatch, cap, metric, value
):
    fake = llm.call_openrouter

    async def never_stops(messages, *, tools=None, schema=None, model=None):
        if tools:  # always one more search
            call = {
                "id": f"call_{len(messages)}",
                "name": "web_search",
                "arguments": {"query": "q"},
            }
            return llm.Reply(text="", tool_calls=[call], data=None, usage=USAGE, model="fake")
        return await fake(messages, tools=tools, schema=schema, model=model)

    monkeypatch.setattr(tracing, cap, value)
    monkeypatch.setattr(llm, "call_openrouter", never_stops)
    run_id = await submit(client)
    result = (await client.get(f"/research/{run_id}/result")).json()
    steps = (await client.get(f"/research/{run_id}/trace")).json()["steps"]
    metrics = result["metrics"]
    assert metrics["hit_cap"] is True and metrics[metric] == value
    assert steps[-1]["type"] == "synthesis" and "[1]" in result["report"]
    assert metrics["searches"] == sum(step["type"] == "search" for step in steps)
    assert metrics["llm_calls"] == sum(step["type"] != "search" for step in steps)


async def test_a_marker_without_a_source_is_counted_then_removed(client, monkeypatch):
    fake = llm.call_openrouter

    async def cites_a_missing_source(messages, *, tools=None, schema=None, model=None):
        reply = await fake(messages, tools=tools, schema=schema, model=model)
        if tools is None and schema is None:  # the report
            reply.text = "# Report\n\nFact A [1]. Fact C [7].\n"
        return reply

    monkeypatch.setattr(llm, "call_openrouter", cites_a_missing_source)
    result = (await client.get(f"/research/{await submit(client)}/result")).json()
    # [7] is gone with its space; the service adds the list of the cited sources
    assert result["report"] == (
        "# Report\n\nFact A [1]. Fact C.\n\n## Sources\n\n- [1] [A](https://example.com/a)\n"
    )
    metrics = result["metrics"]
    assert metrics["citation_validity"] == 0.5 and metrics["hit_cap"] is False
    assert metrics["sources_found"] == 2 and metrics["sources_cited"] == 1
    assert {source["n"]: source["cited"] for source in result["sources"]} == {1: True, 2: False}


async def test_a_source_title_with_brackets_is_not_a_citation_marker(client, monkeypatch):
    fake = search.call_tavily

    async def titled(query, *, max_results=5):
        return [{**r, "title": "Report [7]"} for r in await fake(query, max_results=max_results)]

    monkeypatch.setattr(search, "call_tavily", titled)
    result = (await client.get(f"/research/{await submit(client)}/result")).json()
    assert {int(n) for n in re.findall(r"\[(\d+)\]", result["report"])} <= {1, 2}
    assert "Report \\[7\\]" in result["report"]


async def test_the_status_moves_through_planning_and_running_during_the_job(client, monkeypatch):
    fake = llm.call_openrouter
    seen = []

    async def watching(messages, *, tools=None, schema=None, model=None):
        async with db.SessionLocal() as session:
            run = await session.get(db.Run, tracing.current.get().id)
        seen.append(("plan" if schema is llm.Plan else "act" if tools else "report", run.status))
        return await fake(messages, tools=tools, schema=schema, model=model)

    monkeypatch.setattr(llm, "call_openrouter", watching)
    await submit(client)
    assert seen[0] == ("plan", "planning")
    assert ("act", "running") in seen and ("report", "running") in seen


async def test_every_step_without_an_error_has_an_output(client):
    steps = (await client.get(f"/research/{await submit(client)}/trace")).json()["steps"]
    assert steps and all(step["output"] for step in steps if not step["error"])


async def test_the_app_sweeps_stale_runs_when_it_starts(client, seed_run):
    from app.main import app

    run_id = await seed_run("running")
    async with app.router.lifespan_context(app):  # the lifespan is what calls the sweep
        pass
    assert (await client.get(f"/research/{run_id}/status")).json()["status"] == "failed"
