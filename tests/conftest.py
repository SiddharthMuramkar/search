"""Shared fixtures. No test calls the network: the model and the search provider are replaced.

Only the two network functions are replaced (`llm.call_openrouter`, `search.call_tavily`), so the
caps, the step rows and the spans of the real code also run under test. See SPEC.md section 6.
"""

import asyncio
import os

import httpx
import pytest

# Tests use their own database on the compose PostgreSQL and no trace exporter.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://research:research@localhost:5432/research_test"
)
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
os.environ.setdefault("LLM_MODEL", "fake/llm")
os.environ.setdefault("JUDGE_MODEL", "fake/judge")

REPORT = "# Report\n\n## Summary\n\nFact A [1]. Fact B [2].\n"
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0}
SCORE = {"score": 4, "reason": "ok"}
SEARCH_RESULTS = [
    {
        "url": "https://example.com/a",
        "title": "A",
        "snippet": "Fact A.",
        "content": "Fact A, long.",
    },
    {
        "url": "https://example.org/b",
        "title": "B",
        "snippet": "Fact B.",
        "content": "Fact B, long.",
    },
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Make fresh tables in the test database once."""
    from app import db

    async def create():
        async with db.engine.begin() as conn:
            # drop first: create_all never changes a table that already exists
            await conn.run_sync(db.Base.metadata.drop_all)
            await conn.run_sync(db.Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(create())
    yield


def make_fake_llm():
    """A model that plans, searches once, asks for one more search round, then writes REPORT."""
    critiques = 0

    async def call_openrouter(messages, *, tools=None, schema=None, model=None):
        nonlocal critiques
        from app.llm import Reply

        if schema is not None:
            name = schema.__name__
            if name == "Critique":
                critiques += 1
                first = critiques == 1
                data = {
                    "sufficient": not first,
                    "gaps": ["gap"] if first else [],
                    "follow_up_queries": ["follow-up"] if first else [],
                }
            else:
                data = {
                    "Plan": {"sub_questions": ["What is A?", "What is B?"]},
                    "Findings": {"summary": "Fact A [1].", "source_numbers": [1]},
                    "Judgment": dict.fromkeys(("coverage", "grounding", "depth", "clarity"), SCORE),
                }[name]
            return Reply(text="", tool_calls=[], data=data, usage=USAGE, model="fake")
        if tools and not any(m.get("role") == "tool" for m in messages):
            call = {"id": "call_1", "name": "web_search", "arguments": {"query": "fake query"}}
            return Reply(text="", tool_calls=[call], data=None, usage=USAGE, model="fake")
        return Reply(text=REPORT, tool_calls=[], data=None, usage=USAGE, model="fake")

    return call_openrouter


async def fake_tavily(query, *, max_results=5):
    return SEARCH_RESULTS[:max_results]


@pytest.fixture
async def client(monkeypatch):
    from app import db, llm, search
    from app.main import app

    monkeypatch.setattr(llm, "call_openrouter", make_fake_llm())
    monkeypatch.setattr(search, "call_tavily", fake_tavily)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await db.engine.dispose()


@pytest.fixture
async def seed_run():
    """Insert a run row directly, for states that a finished background job never shows."""
    from app import db

    async def seed(status="queued", **fields):
        async with db.SessionLocal() as session:
            run = db.Run(
                query="seeded", architecture="react", model="fake/llm", status=status, **fields
            )
            session.add(run)
            await session.commit()
            return str(run.id)

    return seed
