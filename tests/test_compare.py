"""The tests of milestone M5: the compare routes, the judge and the winner rule (SPEC.md section 8).

Each test wraps the fake model that the `client` fixture has set, to make one case happen.
"""

import asyncio
import itertools
import json
import uuid
from datetime import datetime

import pytest

from app import db, evaluate, jobs, llm
from app.agents import ARCHITECTURES

pytestmark = pytest.mark.anyio


async def compare(client, query="What is A?") -> dict:
    """POST a comparison and GET the stored result (the test client ran the job before it returned)."""
    response = await client.post("/research/compare", json={"query": query})
    assert response.status_code == 202, response.text
    return (await client.get(response.json()["result_url"])).json()


def wrap_model(monkeypatch, before):
    """Replace the fake model by one that first calls `before(schema)`, which may raise."""
    fake = llm.call_openrouter

    async def wrapped(messages, *, tools=None, schema=None, model=None):
        await before(schema, messages, model)
        return await fake(messages, tools=tools, schema=schema, model=model)

    monkeypatch.setattr(llm, "call_openrouter", wrapped)


# --- the winner rule on fixed scores ------------------------------------------------------------


def row(run_id, scores, citation_validity=1.0, latency_s=10.0):
    return {
        "id": run_id,
        "scores": dict(zip(("coverage", "grounding", "depth", "clarity"), scores, strict=True)),
        "citation_validity": citation_validity,
        "latency_s": latency_s,
    }


@pytest.mark.parametrize(
    ("rows", "winner"),
    [
        # the highest mean wins, whatever the citation validity and the latency are
        ([row("a", (5, 5, 5, 4), 0.5, 99.0), row("b", (4, 4, 4, 4), 1.0, 1.0)], "a"),
        # same mean (4.0 and 4.0): the higher citation_validity wins, although it is slower
        ([row("a", (5, 3, 4, 4), 1.0, 50.0), row("b", (4, 4, 4, 4), 0.5, 5.0)], "a"),
        # same mean and same citation_validity: the lower latency_s wins
        ([row("a", (4, 4, 4, 4), 0.8, 20.0), row("b", (4, 4, 4, 4), 0.8, 12.5)], "b"),
        # only the judged runs are rows: the best of them wins, whatever the other runs did
        ([row("a", (2, 2, 2, 2)), row("c", (3, 3, 3, 3), 0.0, 90.0)], "c"),
        ([row("a", (1, 1, 1, 1))], "a"),
        ([], None),  # no run was judged
    ],
)
def test_winner_rule_on_fixed_scores(rows, winner):
    assert evaluate.pick_winner(rows) == winner


# --- the judge ----------------------------------------------------------------------------------


async def test_the_judge_never_sees_an_architecture_name(client, monkeypatch):
    seen = []

    async def spy(schema, messages, model):
        if schema is evaluate.Judgment:
            seen.append((json.dumps(messages).lower(), model))

    wrap_model(monkeypatch, spy)
    body = await compare(client)
    assert len(seen) == len(ARCHITECTURES) == len(body["evaluations"])
    for text, model in seen:
        assert not [name for name in ARCHITECTURES if name in text]
        assert "What is A?".lower() in text and "fact a" in text  # the query and a cited snippet
        assert model == "fake/judge"  # JUDGE_MODEL, not LLM_MODEL


@pytest.mark.parametrize("failing", [1, 99])  # one judge call fails, then all of them
async def test_a_failed_judge_call_keeps_the_metrics_and_loses_the_evaluation(
    client, monkeypatch, failing
):
    calls = 0

    async def judge_down(schema, messages, model):
        nonlocal calls
        if schema is evaluate.Judgment:
            calls += 1
            if calls <= failing:
                raise RuntimeError("judge down")

    wrap_model(monkeypatch, judge_down)
    body = await compare(client)
    judged = {e["run_id"] for e in body["evaluations"]}
    assert body["status"] == "done"
    assert len(judged) == max(len(ARCHITECTURES) - failing, 0)
    assert body["winner"] in judged if judged else body["winner"] is None
    for run in body["runs"]:
        assert run["status"] == "done" and run["metrics"]["words"] > 0
        steps = (await client.get(f"/research/{run['id']}/trace")).json()["steps"]
        # the judge step is on the judged run, last, with the next seq; a failed one keeps its error
        assert steps[-1]["type"] == "judge" and steps[-1]["seq"] == len(steps)
        # D18: the judge span is a trace of its own, not a child of research.run
        assert steps[-1]["parent_span_id"] is None
        assert (steps[-1]["error"] is None) == (run["id"] in judged)
        # D15: the judge is not counted in llm_calls
        assert run["metrics"]["llm_calls"] == sum(
            s["type"] not in ("search", "judge") for s in steps
        )


# --- the runs ----------------------------------------------------------------------------------


@pytest.mark.parametrize("failing", [1, 99])  # the first run fails, then all of them
async def test_a_failed_run_does_not_fail_the_comparison(client, monkeypatch, failing):
    plans = 0

    async def model_down(schema, messages, model):
        nonlocal plans
        if schema is llm.Plan:  # every run starts with its plan
            plans += 1
            if plans <= failing:
                raise RuntimeError("model down")

    wrap_model(monkeypatch, model_down)
    body = await compare(client)
    done = {r["id"] for r in body["runs"] if r["status"] == "done"}
    failed = [r for r in body["runs"] if r["status"] == "failed"]
    assert len(failed) == min(failing, len(ARCHITECTURES))
    assert all(r["error"] == "model down" and r["metrics"] is None for r in failed)
    assert {e["run_id"] for e in body["evaluations"]} == done  # only finished runs are judged
    if done:
        assert body["status"] == "done" and body["winner"] in done
    else:  # a comparison is failed only when no run finished
        assert body["status"] == "failed" and body["winner"] is None


async def test_the_runs_execute_one_after_the_other(client, monkeypatch):
    async def slow(schema, messages, model):
        await asyncio.sleep(0.01)  # a run that started in parallel would overlap the others

    wrap_model(monkeypatch, slow)
    body = await compare(client)
    stamps = []
    for run in body["runs"]:
        status = (await client.get(f"/research/{run['id']}/status")).json()
        stamps.append((datetime.fromisoformat(status["started_at"]), status["finished_at"]))
    stamps.sort()
    assert len(stamps) == len(ARCHITECTURES) >= 2
    for (_, finished_at), (started_at, _) in itertools.pairwise(stamps):
        assert started_at >= datetime.fromisoformat(finished_at)


# --- the routes ---------------------------------------------------------------------------------


async def test_post_returns_202_with_three_keys_and_an_unknown_id_is_404(client):
    response = await client.post("/research/compare", json={"query": "What is A?"})
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"comparison_id", "run_ids", "result_url"}
    assert set(body["run_ids"]) == set(ARCHITECTURES)
    assert body["result_url"] == f"/research/compare/{body['comparison_id']}"
    assert (await client.get(f"/research/compare/{uuid.uuid4()}")).status_code == 404


@pytest.mark.parametrize("body", [{}, {"query": "   "}])
async def test_an_empty_compare_query_is_422(client, body):
    assert (await client.post("/research/compare", json=body)).status_code == 422


async def test_a_comparison_left_running_by_a_restart_is_failed_at_startup(client):
    async with db.SessionLocal() as session:
        comparison = db.Comparison(query="seeded", status="running")
        session.add(comparison)
        await session.commit()
    await jobs.fail_stale_runs()
    body = (await client.get(f"/research/compare/{comparison.id}")).json()
    assert body["status"] == "failed"
