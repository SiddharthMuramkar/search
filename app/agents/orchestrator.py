"""orchestrator: a planner, one worker for each sub-question at the same time, one writer.

The code does the fan-out and the fan-in. No model loop chooses the next step.
"""

import asyncio

from pydantic import BaseModel

from app import llm, search, tracing

MAX_SUB_QUESTIONS = 4  # also keeps the workers inside the caps: 1 plan + 4 workers + 1 synthesis
WORKER_PROMPT = (
    "You research one sub-question. Read the numbered sources and answer in 2 to 4 sentences. "
    "Write facts only, each one cited as [n], one number in each pair of brackets, using only "
    'the sources given. Reply with JSON: {"summary": "...", "source_numbers": [1, 2]}, where '
    "source_numbers lists the numbers you cited."
)
EMPTY = {"summary": "", "source_numbers": []}


class Findings(BaseModel):
    """The short reply of one worker. The writer sees this and never the raw pages."""

    summary: str
    source_numbers: list[int]


async def run(query: str) -> str:
    plan = await llm.complete(
        [{"role": "system", "content": llm.PLAN_PROMPT}, {"role": "user", "content": query}],
        step="plan",
        schema=llm.Plan,
    )
    await tracing.update_run(plan=plan.data, status="running")
    questions = plan.data["sub_questions"][:MAX_SUB_QUESTIONS] or [query]
    done = await asyncio.gather(*(work(question) for question in questions), return_exceptions=True)
    for found in done:  # a plain gather would raise at the first failure and leave the rest running
        if isinstance(found, BaseException):
            raise found
    notes = "\n\n".join(
        f"### {question}\n{found['summary'] or 'No findings.'}\n"
        f"Sources: {', '.join(map(str, found['source_numbers']))}"
        for question, found in zip(questions, done, strict=True)
    )
    prompt = f"Question: {query}\n\nFindings of the workers:\n\n{notes}\n\n{llm.REPORT_PROMPT}"
    return (await llm.complete([{"role": "user", "content": prompt}], step="synthesis")).text


async def work(question: str) -> dict:
    """One worker: its own search and its own messages. Returns its findings (a `Findings` dict).

    A cap, or a search with no results, gives empty findings: the writer still runs.
    """
    try:
        results = await search.search(question)
        if not results:
            return EMPTY
        sources = "\n\n".join(
            f"[{r['n']}] {r['title']}\n{r['url']}\n{r['content']}" for r in results
        )
        reply = await llm.complete(
            [
                {"role": "system", "content": WORKER_PROMPT},
                {"role": "user", "content": f"Sub-question: {question}\n\nSources:\n{sources}"},
            ],
            step="worker",
            schema=Findings,
        )
    except tracing.CapReached:
        return EMPTY
    return reply.data
