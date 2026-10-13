"""reflection: plan, one search pass, draft, then up to 2 rounds of critic, new searches, revise.

The critic decides when to stop and what to search next. Its follow-up queries are searched and
the revision sees the new sources, so a round adds evidence and does not only polish the text.
"""

from pydantic import BaseModel

from app import llm, search, tracing

FIRST_PASS = 3  # searches of the first pass; with FOLLOW_UPS this is MAX_SEARCHES, so no cap is hit
FOLLOW_UPS = 3  # searches for the critic's queries, shared by all rounds
ROUNDS = 2

CRITIC_PROMPT = (
    "You review a draft research report against the user's question, the plan and the numbered "
    "sources. Find parts of the question that the sources do not answer and claims that no source "
    "supports. Set sufficient to true only when the draft answers every part of the question and "
    "every claim is supported. For each gap that a new web search could fill, give one specific "
    "search query in follow_up_queries (at most 3 in all). "
    'Reply with JSON: {"sufficient": true, "gaps": ["..."], "follow_up_queries": ["..."]}.'
)


class Critique(BaseModel):
    sufficient: bool
    gaps: list[str]
    follow_up_queries: list[str]


async def run(query: str) -> str:
    plan = await llm.complete(
        [{"role": "system", "content": llm.PLAN_PROMPT}, {"role": "user", "content": query}],
        step="plan",
        schema=llm.Plan,
    )
    await tracing.update_run(plan=plan.data, status="running")
    questions = plan.data["sub_questions"]
    context = f"Question: {query}\n\nPlan:\n" + "\n".join(f"- {q}" for q in questions)
    pool: dict[int, str] = {}  # the evidence: citation number n -> source text
    await gather(questions[:FIRST_PASS], pool)
    text = await write(context, pool, "draft")
    left = FOLLOW_UPS
    try:
        for _ in range(ROUNDS):
            critique = await criticize(context, pool, text)
            if critique["sufficient"]:
                break
            queries = critique["follow_up_queries"][:left]
            left -= len(queries)
            await gather(queries, pool)
            text = await write(context, pool, "revise", text, critique["gaps"])
    except tracing.CapReached:
        pass  # no model call is left for the critic: the last text is the report
    return text


async def gather(queries: list[str], pool: dict[int, str]) -> None:
    """Search each query and add the sources to the pool. A refused search ends the gathering."""
    # shortcut: the searches run one after the other, use asyncio.gather if latency matters
    for query in queries:
        try:
            results = await search.search(query)
        except tracing.CapReached:
            return
        for r in results:
            pool[r["n"]] = f"[{r['n']}] {r['title']}\n{r['url']}\n{r['content']}"


def sources_text(context: str, pool: dict[int, str]) -> str:
    return context + "\n\nSources:\n\n" + "\n\n".join(pool[n] for n in sorted(pool))


async def criticize(context: str, pool: dict[int, str], text: str) -> dict:
    messages = [
        {"role": "system", "content": CRITIC_PROMPT},
        {"role": "user", "content": f"{sources_text(context, pool)}\n\nDraft:\n{text}"},
    ]
    return (await llm.complete(messages, step="critique", schema=Critique)).data


async def write(
    context: str, pool: dict[int, str], name: str, draft: str = "", gaps: list[str] | None = None
) -> str:
    """The draft, or the revision of `draft` with the critic's gaps. Both use the report template."""
    messages = [{"role": "user", "content": sources_text(context, pool)}]
    if draft:  # the sources above now include the ones found after the critique
        notes = "\n".join(f"- {gap}" for gap in gaps or [])
        messages += [
            {"role": "assistant", "content": draft},
            {
                "role": "user",
                "content": (
                    f"A critic found these gaps:\n{notes}\n\nRevise the report to close them. "
                    "The reader sees only the final report: do not mention the critic, the gaps "
                    "or that this is a revision."
                ),
            },
        ]
    messages.append({"role": "user", "content": llm.REPORT_PROMPT})
    return (await llm.complete(messages, step="synthesis", name=name)).text
