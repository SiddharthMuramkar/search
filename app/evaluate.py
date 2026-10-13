"""Evaluation of a run (SPEC.md section 8): the counted metrics, the judge and the winner rule."""

import uuid
from statistics import fmean
from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import db, llm, tracing

RUBRIC_VERSION = "v1"
METHOD = "judge_mean_v1"

# the judge sees the query, the report and the cited snippets, never the architecture name
JUDGE_PROMPT = (
    "You grade a research report. You get the question, the report and the text of the sources "
    "that the report cites as [n]. Score each criterion from 1 (poor) to 5 (excellent) with a "
    "one-line reason: coverage (every part of the question is answered), grounding (each claim is "
    "supported by the cited source text), depth (specific facts and analysis, not generalities), "
    "clarity (the answer is easy to find and follow). Do not reward length: a short report that "
    "is complete and supported beats a long one. Reply with JSON: "
    '{"coverage": {"score": 1, "reason": "..."}, "grounding": {...}, "depth": {...}, '
    '"clarity": {...}}.'
)


class Criterion(BaseModel):
    score: Annotated[int, Field(ge=1, le=5)]
    reason: str


class Judgment(BaseModel):
    coverage: Criterion
    grounding: Criterion
    depth: Criterion
    clarity: Criterion


def metrics(
    run: tracing.Run, report: str, sources: list[db.Source], latency_s: float
) -> tuple[str, dict]:
    """Count the metrics of a finished run. Returns the report to store and the metrics.

    Marks each cited source. A marker [n] with no stored source is counted, then removed from
    the report: `citation_validity` is the share of valid markers before that removal.
    """
    stored = {source.n: source for source in sources}
    markers = [int(n) for n in llm.CITATION.findall(report)]
    for n in markers:
        if n in stored:
            stored[n].cited = True
    report = llm.CITATION.sub(lambda m: m[0] if int(m[1]) in stored else "", report)
    cited = [source for source in sources if source.cited]
    valid = sum(n in stored for n in markers)
    return report, {
        "latency_s": round(latency_s, 2),
        "llm_calls": run.llm_calls,
        "searches": run.searches,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cost_usd": round(run.cost_usd, 6),
        "sources_found": len(sources),
        "sources_cited": len(cited),
        "domains_cited": len({source.domain for source in cited}),
        # no marker at all is 0, not 1: a report without citations is not grounded
        "citation_validity": round(valid / len(markers), 2) if markers else 0.0,
        "words": len(report.split()),
        "hit_cap": run.hit_cap,
    }


async def judge(run_id: uuid.UUID, comparison_id: uuid.UUID) -> dict[str, int]:
    """Judge the report of a finished run with one model call, store the evaluation and return the
    scores. A failed call raises: the caller leaves that evaluation missing (SPEC.md section 8)."""
    last_seq = select(func.max(db.Step.seq)).where(db.Step.run_id == run_id)
    cited = (
        select(db.Source).where(db.Source.run_id == run_id, db.Source.cited).order_by(db.Source.n)
    )
    async with db.SessionLocal() as session:
        run = await session.get(db.Run, run_id)
        sources = (await session.scalars(cited)).all()
        seq = await session.scalar(last_seq) or 0
    evidence = "\n\n".join(f"[{s.n}] {s.title or s.url}\n{s.snippet or ''}" for s in sources)
    content = (
        f"Question: {run.query}\n\nReport:\n{run.report}\n\nCited sources:\n{evidence or '(none)'}"
    )
    # A new Run object: the run's caps (it may have hit one) must not limit the judge, and the
    # judge step is stored on the judged run with its seq continuing. The comparison job is one
    # task, no gather, so setting it here is safe (tracing.Run explains why a worker must not).
    # The judge span starts after research.run ended: it is a one-span trace of its own.
    tracing.current.set(tracing.Run(id=run_id, seq=seq))
    model = llm.judge_model()
    messages = [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": content}]
    reply = await llm.complete(messages, step="judge", schema=Judgment, model=model)
    scores = {name: criterion["score"] for name, criterion in reply.data.items()}
    async with db.SessionLocal() as session:
        session.add(
            db.Evaluation(
                run_id=run_id,
                comparison_id=comparison_id,
                scores=scores,
                reasons={name: criterion["reason"] for name, criterion in reply.data.items()},
                raw=reply.data,
                judge_model=model,
                rubric_version=RUBRIC_VERSION,
            )
        )
        await session.commit()
    return scores


def pick_winner(rows: list[dict]) -> uuid.UUID | None:
    """The winner rule `judge_mean_v1` over the judged runs. A row is a plain dict:
    `id`, `scores` ({criterion: score}), `citation_validity`, `latency_s`.

    Highest mean score; a tie goes to the higher citation_validity; a tie again goes to the lower
    latency_s. None if no run was judged."""
    if not rows:
        return None
    best = max(
        rows, key=lambda r: (fmean(r["scores"].values()), r["citation_validity"], -r["latency_s"])
    )
    return best["id"]
