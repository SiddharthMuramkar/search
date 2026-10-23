"""The tracer provider, the caps, the current run and step(): one span and one `steps` row."""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import format_span_id
from sqlalchemy import update

from app import db

MAX_LLM_CALLS = 10
MAX_SEARCHES = 6

# Spans are recorded without an exporter too, so every run gets a real trace id. The SDK
# truncates long span attributes (prompts, reports); the steps rows keep the full text. The
# resource reads OTEL_SERVICE_NAME by itself.
provider = TracerProvider(span_limits=SpanLimits(max_span_attribute_length=1000))
# the SDK logs a warning for each truncated attribute; the truncation is wanted, so keep errors only
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)
tracer = provider.get_tracer("app")

# the exporter reads the endpoint from the env var and adds /v1/traces; 1 s delay shows a trace in
# Jaeger within seconds. An empty value turns it off.
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(), schedule_delay_millis=1000))


class CapReached(Exception):
    """A cap of SPEC.md section 7 refused a step: write the report with what the run has."""


@dataclass
class Run:
    """The current run. One object for the whole job: change its fields under `lock`.

    Never call `current.set()` inside a job: asyncio.gather gives each worker a copy of the
    context, so a new object set in a worker is lost, while this shared one is seen by all.
    """

    id: uuid.UUID
    seq: int = 0
    llm_calls: int = 0
    searches: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    hit_cap: bool = False
    sources: dict[str, int] = field(default_factory=dict)  # url -> citation number n
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


current: ContextVar[Run] = ContextVar("current_run")


async def update_run(**values) -> None:
    """Write columns of the current run in a short session of its own."""
    async with db.SessionLocal() as session:
        await session.execute(update(db.Run).where(db.Run.id == current.get().id).values(**values))
        await session.commit()


@asynccontextmanager
async def step(kind: str, name: str | None, input: dict, span_name: str | None = None):
    """Record one step of the current run: a span and a `steps` row, opened and closed together.

    Checks the caps first. A model call that is not a `synthesis` stops one call early, so an
    architecture stopped by a cap can still write its report.
    Yields the row and the span: the caller sets `row.output`, or `row.error` for an error it
    handles itself.
    """
    run = current.get()
    async with run.lock:
        if kind == "search":
            counter, cap = "searches", MAX_SEARCHES
        elif kind == "synthesis":
            counter, cap = "llm_calls", MAX_LLM_CALLS
        else:
            counter, cap = "llm_calls", MAX_LLM_CALLS - 1
        if getattr(run, counter) >= cap:
            run.hit_cap = True
            raise CapReached(counter)
        setattr(run, counter, getattr(run, counter) + 1)
        run.seq += 1
        seq = run.seq
    with tracer.start_as_current_span(span_name or kind) as span:
        row = db.Step(
            run_id=run.id,
            seq=seq,
            type=kind,
            name=name,
            input=input,
            output=None,
            error=None,
            span_id=format_span_id(span.get_span_context().span_id),
            parent_span_id=format_span_id(span.parent.span_id) if span.parent else None,
            started_at=db.utcnow(),
        )
        async with db.SessionLocal() as session:
            session.add(row)
            await session.commit()
        try:
            yield row, span
        except BaseException as exc:  # BaseException: a step cut by the time limit is recorded too
            row.error = str(exc) or type(exc).__name__
            raise
        finally:
            async with db.SessionLocal() as session:
                await session.execute(
                    update(db.Step)
                    .where(db.Step.id == row.id)
                    .values(output=row.output, error=row.error, ended_at=db.utcnow())
                )
                await session.commit()
