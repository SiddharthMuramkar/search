"""The FastAPI app: the startup sweep and the routes of the API contract (SPEC.md section 4)."""

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app import db, jobs, llm, schemas
from app.agents import ARCHITECTURES


@asynccontextmanager
async def lifespan(app: FastAPI):
    await jobs.fail_stale_runs()
    yield


app = FastAPI(title="Deep Research API", lifespan=lifespan)

# --- the architectures --------------------------------------------------------------------------


@app.get("/research/architectures", response_model=list[schemas.Architecture])
async def architectures():
    return [{"name": name, "description": entry[0]} for name, entry in ARCHITECTURES.items()]


# --- one research run ---------------------------------------------------------------------------


async def get_run(run_id: uuid.UUID) -> db.Run:
    async with db.SessionLocal() as session:
        run = await session.get(db.Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run


RunById = Annotated[db.Run, Depends(get_run)]


@app.post("/research/query", status_code=202, response_model=schemas.Accepted)
async def submit(body: schemas.Query, background_tasks: BackgroundTasks):
    run = db.Run(
        query=body.query,
        architecture=body.architecture,
        status="queued",
        model=llm.configured_model(),
    )
    async with db.SessionLocal() as session:
        session.add(run)
        await session.commit()  # committed before the job is queued: the job loads it by id
    background_tasks.add_task(jobs.run_research, run.id)
    return run


@app.get("/research/{run_id}/status", response_model=schemas.Status)
async def status(run: RunById):
    return run


@app.get(
    "/research/{run_id}/result",
    response_model=schemas.Result,
    responses={409: {"model": schemas.NotDone}},
)
async def result(run: RunById):
    if run.status != "done":
        return JSONResponse({"status": run.status, "error": run.error}, status_code=409)
    query = select(db.Source).where(db.Source.run_id == run.id).order_by(db.Source.n)
    async with db.SessionLocal() as session:
        sources = (await session.scalars(query)).all()
    return {
        "id": run.id,
        "query": run.query,
        "architecture": run.architecture,
        "model": run.model,
        "report": run.report,
        "sources": sources,
        "metrics": run.metrics,
    }


@app.get("/research/{run_id}/trace", response_model=schemas.Trace)
async def trace(run: RunById):
    query = select(db.Step).where(db.Step.run_id == run.id).order_by(db.Step.seq)
    async with db.SessionLocal() as session:
        steps = (await session.scalars(query)).all()
    return {
        "id": run.id,
        "trace_id": run.trace_id,
        "trace_url": run.trace_id and f"http://localhost:16686/trace/{run.trace_id}",
        "plan": run.plan,
        "steps": steps,
    }


# --- one comparison -----------------------------------------------------------------------------


@app.post("/research/compare", status_code=202, response_model=schemas.CompareAccepted)
async def compare(body: schemas.CompareQuery, background_tasks: BackgroundTasks):
    comparison = db.Comparison(query=body.query, status="queued")
    async with db.SessionLocal() as session:
        session.add(comparison)
        await session.flush()  # the runs refer to the comparison: it is inserted first
        runs = {
            name: db.Run(
                query=body.query,
                architecture=name,
                status="queued",
                model=llm.configured_model(),
                comparison_id=comparison.id,
            )
            for name in ARCHITECTURES
        }
        session.add_all(runs.values())
        await session.commit()  # committed before the job is queued: the job loads the runs by id
    background_tasks.add_task(jobs.run_comparison, comparison.id)
    return {
        "comparison_id": comparison.id,
        "run_ids": {name: run.id for name, run in runs.items()},
        "result_url": f"/research/compare/{comparison.id}",
    }


@app.get("/research/compare/{comparison_id}", response_model=schemas.Comparison)
async def compare_result(comparison_id: uuid.UUID):
    async with db.SessionLocal() as session:
        comparison = await session.get(db.Comparison, comparison_id)
        if comparison is None:
            raise HTTPException(404, "comparison not found")
        run_rows = select(db.Run).where(db.Run.comparison_id == comparison_id)
        judged = select(db.Evaluation).where(db.Evaluation.comparison_id == comparison_id)
        runs = (await session.scalars(run_rows.order_by(db.Run.created_at))).all()
        evaluations = (await session.scalars(judged.order_by(db.Evaluation.created_at))).all()
    return {
        "id": comparison.id,
        "query": comparison.query,
        "status": comparison.status,
        "runs": runs,
        "evaluations": evaluations,
        "winner": comparison.winner_run_id,
        "method": comparison.method,
    }
