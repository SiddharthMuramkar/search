"""react: one agent in a loop. The model chooses each next search and when to stop."""

import json

from app import llm, search, tracing

LOOP_PROMPT = (
    "You research the user's question with the web_search tool. Search for one thing at a time, "
    "read the results, then choose the next search. Each result has a source number [n]. "
    "When the sources answer every part of the plan, or a new search adds nothing, reply DONE "
    "without a tool call."
)


async def run(query: str) -> str:
    plan = await llm.complete(
        [{"role": "system", "content": llm.PLAN_PROMPT}, {"role": "user", "content": query}],
        step="plan",
        schema=llm.Plan,
    )
    await tracing.update_run(plan=plan.data, status="running")
    outline = "\n".join(f"- {question}" for question in plan.data["sub_questions"])
    messages = [
        {"role": "system", "content": LOOP_PROMPT},
        {"role": "user", "content": f"Question: {query}\n\nPlan:\n{outline}"},
    ]
    try:
        while not tracing.current.get().hit_cap:  # each turn the model searches again or stops
            reply = await llm.complete(messages, step="act", tools=[search.TOOL])
            if not reply.tool_calls:
                break
            calls = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
                }
                for call in reply.tool_calls
            ]
            messages.append(
                {"role": "assistant", "content": reply.text or None, "tool_calls": calls}
            )
            for call in reply.tool_calls:
                content = await use_tool(call)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    except tracing.CapReached:
        pass  # no model call is left for the loop: the report is written with what the run has
    messages.append({"role": "user", "content": llm.REPORT_PROMPT})
    return (await llm.complete(messages, step="synthesis")).text


async def use_tool(call: dict) -> str:
    """The tool message for one tool call. A refused search is told to the model."""
    query = call["arguments"].get("query") if call["name"] == "web_search" else None
    if not query:
        return "Error: call web_search with a query."
    try:
        results = await search.search(query)
    except tracing.CapReached:
        return "Search limit reached."
    found = (f"[{r['n']}] {r['title']}\n{r['url']}\n{r['content']}" for r in results)
    return "\n\n".join(found) or "No results."
