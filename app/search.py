"""The only way to search: search() records the step and the sources, call_tavily() is the network."""

import json
import os
from urllib.parse import urlsplit

import httpx
from opentelemetry.trace import StatusCode

from app import db, tracing

TAVILY_URL = "https://api.tavily.com/search"
PAGE_CHARS = 4000

# the one tool of the agents, in the OpenAI tools format
TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web. Returns numbered sources [n] with their text.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for."}},
            "required": ["query"],
        },
    },
}


async def call_tavily(query: str, *, max_results: int) -> list[dict]:
    body = {"query": query, "max_results": max_results, "include_raw_content": True}
    headers = {"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(TAVILY_URL, json=body, headers=headers)
    if response.is_error:
        # the body names the reason (432 is the plan limit), the status line does not
        raise RuntimeError(f"Tavily {response.status_code}: {response.text[:200]}")
    return [
        {
            "url": r["url"],
            "title": r["title"],
            "snippet": r["content"],
            # shortcut: the page text is cut at 4,000 characters, raise it if reports lack detail
            "content": (r.get("raw_content") or r["content"])[:PAGE_CHARS],
        }
        for r in response.json()["results"]
    ]


async def search(query: str, *, max_results: int = 5) -> list[dict]:
    """Search once as a recorded step and store the new sources.

    Returns the results with their citation number `n`. A URL that the run already has keeps
    its first number and is not stored again. A failed search is an error step and returns [].
    """
    run = tracing.current.get()
    arguments = {"query": query, "max_results": max_results}
    async with tracing.step("search", "web_search", arguments, "execute_tool web_search") as (
        row,
        span,
    ):
        span.set_attributes(
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "web_search",
                "gen_ai.tool.call.arguments": json.dumps(arguments),
            }
        )
        try:
            results = await call_tavily(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001 - the run continues without them (SPEC.md 12)
            row.error = str(exc) or type(exc).__name__
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, row.error)
            return []
        new = []
        async with run.lock:  # n is given out under one lock: parallel workers cannot collide
            for result in results:
                if result["url"] not in run.sources:
                    run.sources[result["url"]] = n = len(run.sources) + 1
                    new.append(
                        db.Source(
                            run_id=run.id,
                            step_id=row.id,
                            n=n,
                            url=result["url"],
                            domain=urlsplit(result["url"]).hostname or "",
                            title=result["title"],
                            snippet=result["snippet"],
                        )
                    )
            numbered = [{**result, "n": run.sources[result["url"]]} for result in results]
        async with db.SessionLocal() as session:
            session.add_all(new)
            await session.commit()
        row.output = {"results": [{k: r[k] for k in ("n", "url", "title")} for r in numbered]}
        span.set_attribute("gen_ai.tool.call.result", json.dumps(row.output["results"]))
    return numbered
