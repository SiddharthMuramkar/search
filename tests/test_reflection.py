"""The `reflection` architecture (SPEC.md section 7): the critic causes new searches, and the
revision uses what they found. The fake model critiques once as insufficient, then as sufficient.
"""

import json

import pytest

from app import llm, search, tracing
from app.agents import reflection

pytestmark = pytest.mark.anyio

USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0}
NEW_SOURCE = {
    "url": "https://example.net/new",
    "title": "New",
    "snippet": "Fact C.",
    "content": "Fact C, long.",
}


async def trace(client) -> tuple[str, dict, list[dict]]:
    """Run `reflection` on a query. Returns the run id, its status and its steps."""
    response = await client.post(
        "/research/query", json={"query": "q", "architecture": "reflection"}
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    status = (await client.get(f"/research/{run_id}/status")).json()
    return run_id, status, (await client.get(f"/research/{run_id}/trace")).json()["steps"]


def kinds(steps: list[dict]) -> list[str]:
    return [f"{s['type']} {s['name']}" if s["name"] else s["type"] for s in steps]


async def test_the_critics_follow_up_query_is_searched(client):
    _, status, steps = await trace(client)
    after = steps[next(i for i, s in enumerate(steps) if s["type"] == "critique") :]
    assert status["status"] == "done"
    assert any(s["type"] == "search" and s["input"]["query"] == "follow-up" for s in after)


async def test_the_revision_uses_a_source_found_after_the_critique(client, monkeypatch):
    fake = search.call_tavily

    async def with_a_new_source(query, *, max_results=5):
        if query == "follow-up":
            return [NEW_SOURCE]
        return await fake(query, max_results=max_results)

    monkeypatch.setattr(search, "call_tavily", with_a_new_source)
    _, _, steps = await trace(client)
    sent = {
        s["name"]: json.dumps(s["input"]["messages"]) for s in steps if s["type"] == "synthesis"
    }
    assert "[3] New" not in sent["draft"] and "[3] New" in sent["revise"]


async def test_a_sufficient_critique_ends_the_run_without_a_revision(client):
    _, _, steps = await trace(client)
    assert steps[-1]["type"] == "critique"
    assert kinds(steps).count("synthesis revise") == 1


async def test_a_critic_that_is_never_satisfied_stops_after_2_rounds(client, monkeypatch):
    fake = llm.call_openrouter

    async def never_satisfied(messages, *, tools=None, schema=None, model=None):
        if schema is reflection.Critique:
            data = {"sufficient": False, "gaps": ["gap"], "follow_up_queries": ["follow-up"]}
            return llm.Reply(text="", tool_calls=[], data=data, usage=USAGE, model="fake")
        return await fake(messages, tools=tools, schema=schema, model=model)

    monkeypatch.setattr(llm, "call_openrouter", never_satisfied)
    _, status, steps = await trace(client)
    assert status["status"] == "done"
    assert kinds(steps) == [
        "plan",
        "search web_search",
        "search web_search",
        "synthesis draft",
        "critique",
        "search web_search",
        "synthesis revise",
        "critique",
        "search web_search",
        "synthesis revise",
    ]


@pytest.mark.parametrize("cap", [2, 4])
async def test_a_cap_still_ends_done_with_a_synthesis(client, monkeypatch, cap):
    monkeypatch.setattr(tracing, "MAX_LLM_CALLS", cap)
    run_id, status, steps = await trace(client)
    metrics = (await client.get(f"/research/{run_id}/result")).json()["metrics"]
    assert status["status"] == "done" and status["error"] is None and metrics["hit_cap"] is True
    assert steps[-1]["type"] == "synthesis"
    assert sum(s["type"] != "search" for s in steps) == cap  # the cap, no more


def critic(follow_ups):
    """A critic that is never satisfied and always asks for these follow-up queries."""
    fake = llm.call_openrouter

    async def call(messages, *, tools=None, schema=None, model=None):
        if schema is reflection.Critique:
            data = {"sufficient": False, "gaps": ["gap"], "follow_up_queries": follow_ups}
            return llm.Reply(text="", tool_calls=[], data=data, usage=USAGE, model="fake")
        return await fake(messages, tools=tools, schema=schema, model=model)

    return call


async def test_a_round_that_cannot_cause_a_search_does_not_happen(client, monkeypatch):
    # three queries use the whole follow-up budget in round 1: round 2 would only polish the text
    monkeypatch.setattr(llm, "call_openrouter", critic(["a", "b", "c"]))
    _, _, steps = await trace(client)
    assert kinds(steps)[3:] == ["synthesis draft", "critique"] + ["search web_search"] * 3 + [
        "synthesis revise"
    ]


async def test_a_critic_with_gaps_but_no_query_ends_the_run(client, monkeypatch):
    monkeypatch.setattr(llm, "call_openrouter", critic([]))
    _, status, steps = await trace(client)
    assert status["status"] == "done"
    assert steps[-1]["type"] == "critique" and "synthesis revise" not in kinds(steps)
