"""Engine, session factory and the five tables of SPEC.md section 5."""

import os
import uuid
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# `or`: an empty DATABASE_URL (a blank line in .env) also gives the compose database
engine = create_async_engine(
    os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://research:research@localhost:5432/research"
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar = {datetime: DateTime(timezone=True), dict: JSONB}


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str]
    architecture: Mapped[str]
    status: Mapped[str]
    model: Mapped[str]
    plan: Mapped[dict | None]
    report: Mapped[str | None]
    error: Mapped[str | None]
    metrics: Mapped[dict | None]
    trace_id: Mapped[str | None]
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comparisons.id", name="fk_runs_comparison_id")
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"))
    seq: Mapped[int]
    type: Mapped[str]
    name: Mapped[str | None]
    input: Mapped[dict | None]
    output: Mapped[dict | None]
    error: Mapped[str | None]
    span_id: Mapped[str]
    parent_span_id: Mapped[str | None]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("run_id", "url"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"))
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("steps.id"))
    n: Mapped[int]
    url: Mapped[str]
    domain: Mapped[str]
    title: Mapped[str | None]
    snippet: Mapped[str | None]
    cited: Mapped[bool] = mapped_column(default=False)


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str]
    status: Mapped[str]
    # use_alter: runs and comparisons refer to each other, so this key is added after both tables
    winner_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", name="fk_comparisons_winner_run_id", use_alter=True)
    )
    method: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"))
    comparison_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comparisons.id"))
    scores: Mapped[dict]
    reasons: Mapped[dict]
    raw: Mapped[dict | None]
    judge_model: Mapped[str]
    rubric_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
