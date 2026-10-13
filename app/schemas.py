"""Request and response bodies of the API contract (SPEC.md section 4)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.agents import ARCHITECTURES

# --- one research run ---------------------------------------------------------------------------


class Query(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    architecture: str = "react"

    @field_validator("architecture")
    @classmethod
    def known(cls, name: str) -> str:
        if name not in ARCHITECTURES:
            raise ValueError(f"unknown architecture, use one of: {', '.join(ARCHITECTURES)}")
        return name


class Accepted(BaseModel):
    id: uuid.UUID
    status: str
    architecture: str


class Status(Accepted):
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class NotDone(BaseModel):
    status: str
    error: str | None


class Source(BaseModel):
    n: int
    url: str
    title: str | None
    snippet: str | None
    cited: bool


class Result(BaseModel):
    id: uuid.UUID
    query: str
    architecture: str
    model: str
    report: str
    sources: list[Source]
    metrics: dict


class Step(BaseModel):
    seq: int
    type: str
    name: str | None
    input: dict | None
    output: dict | None
    error: str | None
    span_id: str
    parent_span_id: str | None
    started_at: datetime
    ended_at: datetime | None


class Trace(BaseModel):
    id: uuid.UUID
    trace_id: str | None
    trace_url: str | None
    plan: dict | None
    steps: list[Step]
