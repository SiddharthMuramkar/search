"""The only way to call the model: complete() records each call, call_openrouter() is the network."""

import json
import os
import re
from dataclasses import asdict, dataclass

from pydantic import BaseModel

from app import tracing

# shortcut: not a model id yet, set the free default from the OpenRouter model list with
# call_openrouter (an empty LLM_MODEL then fails loudly instead of using a random model)
DEFAULT_MODEL = "unset"

# a citation marker [n], with the space before it, so a removed marker leaves no gap
# shortcut: a list like [1, 2] is not a marker and is not checked, parse it if real reports use it
CITATION = re.compile(r" ?\[(\d+)\]")

# the plan and the report template are the same for every architecture (SPEC.md section 7)
PLAN_PROMPT = (
    "Plan the research for the user's question. Split it into 2 to 4 sub-questions that "
    "together answer it, each one specific enough for a web search. "
    'Reply with JSON: {"sub_questions": ["..."]}.'
)
REPORT_PROMPT = (
    "Write the research report in Markdown, in this order: a # title; ## Summary; ## Findings, "
    "where each claim cites its sources as [n], one number in each pair of brackets, using only "
    "the numbered sources above; ## Limits and open questions. Write 600 to 1,000 words. "
    "Do not write a list of sources: it is added for you."
)


@dataclass
class Reply:
    text: str
    tool_calls: list[dict]  # {id, name, arguments}; arguments is a parsed dict
    data: dict | None  # the parsed JSON when a schema is given
    usage: dict  # prompt_tokens, completion_tokens, cost
    model: str  # the model that really answered


class Plan(BaseModel):
    sub_questions: list[str]


def configured_model() -> str:
    return os.environ.get("LLM_MODEL") or DEFAULT_MODEL


async def call_openrouter(messages, *, tools=None, schema=None, model=None) -> Reply:
    raise NotImplementedError("call_openrouter is not written yet (M3)")


async def complete(messages, *, step, name=None, tools=None, schema=None, model=None) -> Reply:
    """Call the model as a recorded step. A reply that does not parse or does not match `schema`
    is retried one time (SPEC.md section 12); the failed attempt stays a step with its error."""
    model = model or configured_model()
    try:
        return await _call(messages, step, name, tools, schema, model)
    except ValueError:  # pydantic's ValidationError and json's JSONDecodeError are ValueErrors
        return await _call(messages, step, name, tools, schema, model)


async def _call(messages, step, name, tools, schema, model) -> Reply:
    run = tracing.current.get()
    span_name = f"{step} {name}" if name else step
    async with tracing.step(step, name, {"model": model, "messages": messages}, span_name) as (
        row,
        span,
    ):
        span.set_attributes({"gen_ai.operation.name": "chat", "gen_ai.request.model": model})
        reply = await call_openrouter(messages, tools=tools, schema=schema, model=model)
        row.output = asdict(reply)
        async with run.lock:
            run.prompt_tokens += reply.usage["prompt_tokens"]
            run.completion_tokens += reply.usage["completion_tokens"]
            run.cost_usd += reply.usage["cost"]
        span.set_attributes(
            {
                "gen_ai.response.model": reply.model,
                "gen_ai.usage.input_tokens": reply.usage["prompt_tokens"],
                "gen_ai.usage.output_tokens": reply.usage["completion_tokens"],
                "output": reply.text or json.dumps(reply.data or reply.tool_calls),
                "citations": sorted({int(n) for n in CITATION.findall(reply.text)}),
            }
        )
        if schema is not None:
            reply.data = schema.model_validate(reply.data).model_dump()
    return reply
