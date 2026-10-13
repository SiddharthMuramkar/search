"""Background jobs. A job gets a run id and opens its own sessions, never a caller's session."""

import asyncio
import logging
import uuid
from datetime import datetime

from opentelemetry.context import Context
from opentelemetry.trace import StatusCode, format_trace_id
from sqlalchemy import select, update

from app import db, evaluate, tracing
from app.agents import ARCHITECTURES

RUN_TIMEOUT_S = 300  # D20: reflection is sequential by design; a real run took 173 s on GLM-5.3
log = logging.getLogger(__name__)


async def run_research(run_id: uuid.UUID) -> None:
    """Run one research job and store its outcome: `done`, or `failed` with the reason."""
    async with db.SessionLocal() as session:
        run = await session.get(db.Run, run_id)
    attributes = {
        "run.id": str(run_id),
        "run.architecture": run.architecture,
        "run.query": run.query,
    }
    # an empty Context: a run is a trace of its own, never a child of the request that started it
    with tracing.tracer.start_as_current_span(
        "research.run", context=Context(), attributes=attributes
    ) as span:
        tracing.current.set(tracing.Run(id=run_id))
        started_at = db.utcnow()
        try:
            async with asyncio.timeout(RUN_TIMEOUT_S) as limit:
                await tracing.update_run(
                    status="planning",
                    started_at=started_at,
                    trace_id=format_trace_id(span.get_span_context().trace_id),
                )
                body = await ARCHITECTURES[run.architecture][1](run.query)
            await finish(run_id, body, started_at)
        except Exception as exc:  # noqa: BLE001 - every failure is stored on the run (R14)
            # expired(): a TimeoutError raised inside the run (a database connect) is no time limit
            error = "time limit" if limit.expired() else (str(exc) or type(exc).__name__)
            span.set_status(StatusCode.ERROR, error)
            await tracing.update_run(status="failed", error=error, finished_at=db.utcnow())


def link_text(source: db.Source) -> str:
    # a title like "Report [7]" would put a citation marker with no source back into the report
    return (source.title or source.url).replace("[", r"\[").replace("]", r"\]")


async def finish(run_id: uuid.UUID, body: str, started_at: datetime) -> None:
    """Store the report, the metrics and the cited sources in one transaction."""
    async with db.SessionLocal() as session:
        query = select(db.Source).where(db.Source.run_id == run_id).order_by(db.Source.n)
        sources = (await session.scalars(query)).all()
        finished_at = db.utcnow()
        report, metrics = evaluate.metrics(
            tracing.current.get(), body, sources, (finished_at - started_at).total_seconds()
        )
        # the service writes the source list from the stored rows, so no URL can be invented
        cited = [f"- [{s.n}] [{link_text(s)}]({s.url})" for s in sources if s.cited]
        if cited:
            report = f"{report.rstrip()}\n\n## Sources\n\n" + "\n".join(cited) + "\n"
        await session.execute(
            update(db.Run)
            .where(db.Run.id == run_id)
            .values(status="done", report=report, metrics=metrics, finished_at=finished_at)
        )
        await session.commit()


async def fail_stale_runs() -> None:
    """At startup: a run does not survive a restart, so an unfinished run can never finish."""
    async with db.SessionLocal() as session:
        await session.execute(
            update(db.Run)
            .where(db.Run.status.in_(("queued", "planning", "running")))
            .values(
                status="failed", error="the API restarted during the run", finished_at=db.utcnow()
            )
        )
        await session.commit()


async def update_comparison(comparison_id: uuid.UUID, **values) -> None:
    async with db.SessionLocal() as session:
        await session.execute(
            update(db.Comparison).where(db.Comparison.id == comparison_id).values(**values)
        )
        await session.commit()


async def run_comparison(comparison_id: uuid.UUID) -> None:
    """Run each architecture on the query one after the other (D8), judge the runs that are done
    and pick the winner. The comparison is `failed` only when no run finished (SPEC.md section 4)."""
    # shortcut: a crash outside run_research and the judge leaves the comparison `running`,
    # fail_stale_runs does not sweep comparisons; add a sweep of them if that ever happens
    await update_comparison(comparison_id, status="running")
    query = select(db.Run).where(db.Run.comparison_id == comparison_id)
    async with db.SessionLocal() as session:
        run_ids = {run.architecture: run.id for run in (await session.scalars(query)).all()}
    for architecture in ARCHITECTURES:  # in registry order, never with gather: fair latency
        await run_research(run_ids[architecture])
    async with db.SessionLocal() as session:
        done = (await session.scalars(query.where(db.Run.status == "done"))).all()
    judged = []
    for run in done:
        try:
            scores = await evaluate.judge(run.id, comparison_id)
            judged.append({"id": run.id, "scores": scores, **run.metrics})
        except Exception:  # a failed judge call leaves that evaluation missing (SPEC.md section 8)
            log.exception("the judge failed for run %s", run.id)  # its step holds the error too
    await update_comparison(
        comparison_id,
        status="done" if done else "failed",
        winner_run_id=evaluate.pick_winner(judged),
        method=evaluate.METHOD,
        finished_at=db.utcnow(),
    )
