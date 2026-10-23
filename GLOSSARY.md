# Deep Research

A service that takes a research question, has an Agent plan, search the web and write a cited report in the background, and compares three agent Architectures on the same question. Every run is stored and traced so that the Architectures can be judged side by side.

## Language

### Research

**Query**:
The research question a caller submits; one Query starts one Run, or one Comparison.
_Avoid_: question, prompt, request, search query

**Run**:
One attempt by one Architecture to answer one Query, from submission to a stored Report or a recorded failure; it begins with a Plan and records an ordered list of Steps.
_Avoid_: job, research job, the research, task, session

**Run status**:
The stage a Run is in: queued, planning, running, then done or failed.
_Avoid_: state, phase

**Research model**:
The one language model every Architecture uses for its Model calls, recorded on each Run; the Judge is a different model.
_Avoid_: LLM, the model (when the Judge could be meant)

**Plan**:
The list of Sub-questions a Run writes before it searches; every Architecture starts with one.
_Avoid_: outline, strategy

**Sub-question**:
One part of the Query that the Plan names for separate investigation.
_Avoid_: subtask, subtopic, sub-query

**Step**:
One recorded unit of work inside a Run, either a Model call or a Search, with its input, output and error.
_Avoid_: event, action, log entry

**Model call**:
One request to a language model inside a Run, labelled by its role in the Architecture.
_Avoid_: LLM call, completion, generation, turn

**Search**:
One web search Step: a Search query sent to the search tool, and the results it returned, which become the Run's Sources.
_Avoid_: tool call, lookup, retrieval

**Search query**:
The text sent to the search tool in one Search, chosen by an Agent, a Sub-question or a Critique; the Search queries a Critique proposes are its follow-up queries.
_Avoid_: query (that word is the caller's Query), keyword

**Source**:
One web page a Search returned to a Run, numbered once within that Run; a Run never holds the same page twice.
_Avoid_: document, result, page, reference, evidence

**Citation**:
A numbered marker [n] in a Report that points to the Source with that number; a Citation may only point to a Source the Run retrieved.
_Avoid_: reference, footnote, link

**Citation validity**:
The share of Citations in a Report that point to a Source the Run actually retrieved, measured before the invalid ones are removed.
_Avoid_: grounding (that is a Rubric criterion), accuracy, faithfulness

**Report**:
The stored answer of a Run, written to the Report template and ending with the list of the Sources it cites; the text above that list is the report body.
_Avoid_: answer, result, output, summary

**Report template**:
The fixed shape every Architecture's Report follows: title, summary, findings with Citations, limits and open questions.
_Avoid_: format, schema, structure

**Synthesis**:
The Model call that writes a Report from the evidence a Run gathered; in reflection it writes the Draft and each Revision.
_Avoid_: writer, writing step, final answer, summary call

### Architectures

**Architecture**:
One control structure for doing a Run; the Architectures share the Research model, the search tool, the Caps and the Report template, and differ only in how the next Step is chosen. A Run uses exactly one Architecture.
_Avoid_: design, strategy, mode, pipeline

**Agent**:
A model-driven actor inside an Architecture that chooses its own next Step, such as the react loop or a Worker; an Architecture may hold one Agent or several.
_Avoid_: using it for the Architecture itself, bot

**react**:
The Architecture where one Agent loops, and the Research model decides at each turn whether to Search again or stop.
_Avoid_: ReAct agent, loop agent, single agent

**orchestrator**:
The Architecture where the Plan splits the Query into Sub-questions, one Worker per Sub-question runs at the same time, and one Synthesis combines their Findings.
_Avoid_: planner-worker, multi-agent, fan-out agent

**reflection**:
The Architecture that writes a Draft, has a Critic find its gaps, Searches for them and writes a Revision, for a bounded number of Rounds.
_Avoid_: self-critique agent, critic loop, reflexion

**Worker**:
In orchestrator, the Agent that investigates one Sub-question in its own context and returns Findings.
_Avoid_: sub-agent, child agent, researcher

**Findings**:
The short summary a Worker returns, with the numbers of the Sources it relied on; never the raw pages.
_Avoid_: result, notes, worker output

**Critic**:
In reflection, the role that reads a Draft or Revision and decides whether it is sufficient or which gaps need new Searches.
_Avoid_: reviewer, judge (the Judge scores Reports in a Comparison), evaluator

**Critique**:
The Critic's output for one Round: whether the text is sufficient, its gaps, and the follow-up queries that would fill them.
_Avoid_: review, feedback, reflection

**Evidence pool**:
In reflection, the numbered Sources gathered so far that the Draft and every Revision are written from.
_Avoid_: context, corpus, memory

**Round**:
In reflection, one pass of Critique, new Searches and Revision.
_Avoid_: iteration, cycle, loop

**Draft**:
In reflection, the first Report text, written after the first search pass and before any Critique.
_Avoid_: first version, initial report

**Revision**:
In reflection, a rewrite of the current text that answers a Critique using the new Sources of that Round; the Step that produces it is named revise.
_Avoid_: rewrite, edit, refinement

### Limits

**Cap**:
The most Model calls or Searches one Run may make; a Run that reaches a Cap stops gathering, still writes its Report and is marked as having hit the Cap.
_Avoid_: budget, quota, limit (without saying which), time limit

**Hit cap**:
The mark on a Run whose Architecture was refused a Step by a Cap; the Run can still be done.
_Avoid_: capped out, truncated, over budget

**Time limit**:
The longest a Run may take; a Run that passes it fails with no Report.
_Avoid_: cap, timeout, deadline

### Comparison

**Comparison**:
One Query answered by every Architecture, one Run each, one after the other, followed by an Evaluation of each finished Run and a Winner.
_Avoid_: compare job, benchmark, experiment, A/B test

**Comparison status**:
The stage a Comparison is in: queued, running, then done or failed; it is done when at least one of its Runs finished, and failed only when none did.
_Avoid_: state, phase

**Judge**:
The model, from a different family than the Research model, that scores one Report against the Rubric without knowing which Architecture wrote it.
_Avoid_: grader, evaluator, critic

**Judgment**:
The Judge's raw reply for one Report: a score and a one-line reason per Rubric criterion, before it is stored.
_Avoid_: using it for the stored record (that is the Evaluation)

**Evaluation**:
The stored record of one Judgment of one Run in one Comparison, with the judge model and Rubric version; a finished Run has at most one Evaluation per Rubric version.
_Avoid_: judge score, grade, rating

**Rubric**:
The four criteria the Judge scores from 1 to 5: coverage, grounding, depth, clarity; each version has a name so a Run can be judged again under a new one.
_Avoid_: grading rubric (that is the take-home's marking scheme, not this), scorecard, criteria

**Metrics**:
The numbers counted in code for every finished Run, in a Comparison or not (latency, Model calls, Searches, tokens, cost, Sources found and cited, Citation validity, words, Hit cap); a failed Run has none.
_Avoid_: stats, scores (scores come from the Judge), telemetry

**Winner rule**:
The written rule that picks the Winner among the evaluated Runs: highest mean Judge score, then higher Citation validity, then lower latency; cost and latency are shown, not scored. Each version has a name, and the API calls it the method.
_Avoid_: ranking, tie-break

**Winner**:
The Run the Winner rule picks in a Comparison, or none when no Run was judged.
_Avoid_: best run, champion

### Observability

**Trace**:
The connected record of one Run's research Steps as Spans under one root, viewable outside the API; a Judge's Model call is recorded on the Run but traced on its own, outside this Trace.
_Avoid_: log, history, timeline

**Span**:
One timed node in a Trace; every Step has exactly one.
_Avoid_: event, log line

**Startup sweep**:
The check at service start that marks every unfinished Run and Comparison as failed, since a restart loses work in progress.
_Avoid_: recovery, cleanup, reaper
