"""Evaluation of a run: the counted metrics of SPEC.md section 8."""

from app import db, llm, tracing


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
