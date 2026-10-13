"""Contract tests for the 7 routes. Each test names the requirement of SPEC.md that it proves.

The test client completes the background job before the POST returns, so tests do POST then GET with
no polling. States that a finished job never shows (`queued`, 409) use rows inserted by `seed_run`.
Tests are skipped until the code of their milestone exists, then they fail loudly.
"""

import asyncio
import re
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
APP_EXISTS = (ROOT / "app" / "main.py").exists()

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not APP_EXISTS, reason="the app is built in M2"),
]


# the 12 metric names of SPEC.md section 8
METRICS = {
    "latency_s",
    "llm_calls",
    "searches",
    "prompt_tokens",
    "completion_tokens",
    "cost_usd",
    "sources_found",
    "sources_cited",
    "domains_cited",
    "citation_validity",
    "words",
    "hit_cap",
}


def needs(path: str, milestone: str):
    return pytest.mark.skipif(not (ROOT / path).exists(), reason=f"built in {milestone}")


async def submit(client, query="What is A?", **body) -> str:
    response = await client.post("/research/query", json={"query": query, **body})
    assert response.status_code == 202, response.text
    return response.json()["id"]


# --- R1, R7: submit ---------------------------------------------------------------------------


async def test_r1_submit_returns_202_and_run_id(client):
    response = await client.post("/research/query", json={"query": "What is A?"})
    assert response.status_code == 202
    body = response.json()
    uuid.UUID(body["id"])
    assert body["architecture"] == "react"  # the default
    assert body["status"] in {"queued", "planning", "running", "done"}


@pytest.mark.parametrize("body", [{}, {"query": ""}, {"query": "   "}])
async def test_r1_empty_query_is_422(client, body):
    assert (await client.post("/research/query", json=body)).status_code == 422


async def test_r7_unknown_architecture_is_422(client):
    response = await client.post("/research/query", json={"query": "q", "architecture": "nope"})
    assert response.status_code == 422


# --- R2, R3: background job and status ----------------------------------------------------------


async def test_r2_run_is_done_after_the_background_job(client):
    run_id = await submit(client)
    body = (await client.get(f"/research/{run_id}/status")).json()
    assert body["status"] == "done"
    assert body["started_at"] and body["finished_at"] and body["error"] is None


@pytest.mark.parametrize("status", ["queued", "planning", "running"])
async def test_r3_status_shows_the_stored_state(client, seed_run, status):
    run_id = await seed_run(status)
    assert (await client.get(f"/research/{run_id}/status")).json()["status"] == status


@pytest.mark.parametrize("route", ["status", "result", "trace"])
async def test_r3_unknown_run_is_404(client, route):
    assert (await client.get(f"/research/{uuid.uuid4()}/{route}")).status_code == 404


# --- R4: result ---------------------------------------------------------------------------------


async def test_r4_result_has_report_sources_architecture_model(client):
    run_id = await submit(client)
    body = (await client.get(f"/research/{run_id}/result")).json()
    assert body["architecture"] == "react" and body["model"]
    assert "[1]" in body["report"]
    assert set(body["metrics"]) == METRICS
    assert {s["url"] for s in body["sources"]} == {"https://example.com/a", "https://example.org/b"}
    assert all({"n", "url", "title", "snippet", "cited"} <= set(s) for s in body["sources"])


async def test_r4_result_before_done_is_409(client, seed_run):
    response = await client.get(f"/research/{await seed_run('running')}/result")
    assert response.status_code == 409
    assert response.json() == {"status": "running", "error": None}


async def test_r4_result_of_a_failed_run_is_409_with_the_error(client, seed_run):
    response = await client.get(f"/research/{await seed_run('failed', error='boom')}/result")
    assert response.status_code == 409
    assert response.json() == {"status": "failed", "error": "boom"}


# --- R5, R13: trace -----------------------------------------------------------------------------


async def test_r5_trace_has_plan_search_and_synthesis_steps_in_order(client):
    run_id = await submit(client)
    body = (await client.get(f"/research/{run_id}/trace")).json()
    types = [step["type"] for step in body["steps"]]
    assert types[0] == "plan" and "search" in types and types[-1] == "synthesis"
    assert [step["seq"] for step in body["steps"]] == sorted(step["seq"] for step in body["steps"])
    assert body["plan"]


async def test_r13_run_has_one_trace_and_every_step_has_a_span(client):
    run_id = await submit(client)
    body = (await client.get(f"/research/{run_id}/trace")).json()
    assert re.fullmatch(r"[0-9a-f]{32}", body["trace_id"]) and set(body["trace_id"]) != {"0"}
    assert body["trace_id"] in body["trace_url"]
    assert all(re.fullmatch(r"[0-9a-f]{16}", step["span_id"]) for step in body["steps"])


# --- R6, R8, R9: architectures ------------------------------------------------------------------


@needs("app/agents/orchestrator.py", "M4")
async def test_r6_architectures_route_matches_the_registry(client):
    from app.agents import ARCHITECTURES

    body = (await client.get("/research/architectures")).json()
    assert {a["name"] for a in body} == set(ARCHITECTURES)
    assert all(a["description"] for a in body)


@pytest.mark.parametrize("name", ["react", "orchestrator", "reflection"])
async def test_r9_architecture_plans_searches_and_cites_only_its_sources(client, name):
    from app.agents import ARCHITECTURES

    if name not in ARCHITECTURES:
        pytest.skip(f"{name} is not built yet")
    run_id = await submit(client, architecture=name)
    result = (await client.get(f"/research/{run_id}/result")).json()
    trace = (await client.get(f"/research/{run_id}/trace")).json()
    assert result["architecture"] == name
    numbers = {int(n) for n in re.findall(r"\[(\d+)\]", result["report"])}
    assert numbers and numbers <= {s["n"] for s in result["sources"]}
    assert trace["plan"] and trace["steps"][0]["type"] == "plan"
    assert any(step["type"] == "search" for step in trace["steps"])


@needs("app/agents/reflection.py", "M6")
async def test_r8_reflection_searches_again_after_the_critique(client):
    run_id = await submit(client, architecture="reflection")
    types = [s["type"] for s in (await client.get(f"/research/{run_id}/trace")).json()["steps"]]
    assert "critique" in types and "search" in types[types.index("critique") :]


# --- R14: failures ------------------------------------------------------------------------------


async def test_r14_model_error_gives_failed_with_the_reason(client, monkeypatch):
    from app import llm

    async def broken(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm, "call_openrouter", broken)
    body = (await client.get(f"/research/{await submit(client)}/status")).json()
    assert body["status"] == "failed" and "provider down" in body["error"]


async def test_r14_time_limit_gives_failed(client, monkeypatch):
    from app import jobs, llm

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(jobs, "RUN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(llm, "call_openrouter", slow)
    body = (await client.get(f"/research/{await submit(client)}/status")).json()
    assert body["status"] == "failed" and "time limit" in body["error"]


async def test_r14_failed_search_is_an_error_step_and_the_run_continues(client, monkeypatch):
    from app import search

    async def broken(*args, **kwargs):
        raise RuntimeError("search down")

    monkeypatch.setattr(search, "call_tavily", broken)
    run_id = await submit(client)
    assert (await client.get(f"/research/{run_id}/status")).json()["status"] == "done"
    steps = (await client.get(f"/research/{run_id}/trace")).json()["steps"]
    assert any(s["type"] == "search" and "search down" in (s["error"] or "") for s in steps)


async def test_r14_stale_runs_are_failed_at_startup(client, seed_run):
    from app import jobs

    run_id = await seed_run("running")
    await jobs.fail_stale_runs()
    body = (await client.get(f"/research/{run_id}/status")).json()
    assert body["status"] == "failed" and body["error"]


# --- R10, R11: comparison -----------------------------------------------------------------------


async def test_r10_r11_compare_stores_metrics_judgment_and_winner(client):
    from app import jobs
    from app.agents import ARCHITECTURES

    # app/evaluate.py exists from M2 (metrics), so the gate is the comparison job itself
    if not hasattr(jobs, "run_comparison"):
        pytest.skip("compare is built in M5")

    response = await client.post("/research/compare", json={"query": "What is A?"})
    assert response.status_code == 202
    started = response.json()
    assert set(started["run_ids"]) == set(ARCHITECTURES)
    assert started["result_url"] == f"/research/compare/{started['comparison_id']}"

    body = (await client.get(started["result_url"])).json()
    assert body["status"] == "done" and body["method"] == "judge_mean_v1"
    assert body["winner"] in started["run_ids"].values()
    assert len(body["runs"]) == len(body["evaluations"]) == len(ARCHITECTURES)
    for run in body["runs"]:
        assert run["status"] == "done"
        assert set(run["metrics"]) == METRICS
    for evaluation in body["evaluations"]:
        assert set(evaluation["scores"]) == {"coverage", "grounding", "depth", "clarity"}
        assert evaluation["judge_model"] and evaluation["rubric_version"]
