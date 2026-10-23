# Matt Pocock's skills in this repo: a beginner's reference

Scoped to this repo only: the Deep Research API (FastAPI + PostgreSQL, three agent architectures in
`app/agents/`). Each claim about a skill comes from that skill's `SKILL.md` in the installed plugin
(`mattpocock-skills` 1.3.1).

**How commands look here.** Each skill is typed as `/mattpocock-skills:<name>`, for example
`/mattpocock-skills:to-spec`. Below, **(you)** means the skill is user-invoked only
(`disable-model-invocation: true`): Claude never starts it on its own, so you must type it.
**(auto)** means Claude can also start it by itself when the situation fits. You can still type it.

---

## 0. How to use this file

Type `@REFERENCE.md` plus your question, for example: `@REFERENCE.md the reflection test fails one
run in five, what now?` Claude reads this file and answers with the command to type.

---

## 1. What do I type when…

| Situation | Type this | What happens next |
|---|---|---|
| "I have an idea for a new feature" (for example, a 4th architecture, or a cost limit per run) | `/mattpocock-skills:grill-with-docs` **(you)** | Claude asks questions in rounds, with its recommended answer for each. It writes new terms into `GLOSSARY.md` and big decisions into `docs/adr/` as they are settled. |
| The idea is clear and will take more than one session to build | `/mattpocock-skills:to-spec` **(you)**, in the same session as the grilling | No new interview. Claude checks the test seams with you, then opens one GitHub issue (the spec) labelled `ready-for-agent`. |
| I have a spec issue and need it cut into work items | `/mattpocock-skills:to-tickets #<spec>` **(you)**, still in the same session | Claude proposes tracer-bullet tickets with their blockers and asks if the sizes and edges are right. After your OK, it opens one issue per ticket, blockers first, with native blocking links and `ready-for-agent`. |
| Build one ticket | `/clear`, then `/mattpocock-skills:implement #<ticket>` **(you)** | Claude states the ticket title, builds it test-first with `tdd`, runs `code-review`, and commits to the current branch. Make the branch first. |
| Build the whole spec in one go | `/mattpocock-skills:implement-spec #<spec>` **(you)** | Claude runs implementer subagents in parallel, each in its own worktree, merges them onto one integration branch, then runs one `code-review` over it. Tell it each implementer worktree needs its own `TEST_DATABASE_URL` (create `research_test_<n>`), or parallel pytest runs drop each other's tables. |
| "What do I build next?" | `/mattpocock-skills:triage what's ready for agents to pick up?` **(you)**, or `gh issue list --label ready-for-agent` | The ready frontier: open `ready-for-agent` issues with no open blockers (`docs/agents/issue-tracker.md`). |
| A small change that fits in this session (no spec needed) | `/mattpocock-skills:implement` **(you)**, right here | Same as above, but from the conversation, not from a ticket. |
| "I just want to build this one behaviour test-first" | `/mattpocock-skills:tdd` **(auto)** | Claude asks which seams to test, then works one red → green slice at a time. |
| "Review my branch before I merge" | `/mattpocock-skills:code-review main` **(auto)** | Two parallel subagents: **Standards** (CLAUDE.md hard rules + a code-smell list) and **Spec** (the issue named in your commits). Two reports side by side. |
| Write the PR body | `/mattpocock-skills:pr` **(auto)**; Claude uses it when it writes a PR anyway | Body with three parts: Summary (smallest diagram or diff sketch), Evidence (before/after, e.g. the test that was red and is green), Merge Danger (one-way or two-way door, blast radius). |
| A build just finished (or went badly) | `/mattpocock-skills:retro` **(you)**, before you `/clear` | Claude lists changes to the environment (not the code): navigation pointers, checks, coding standards, steering files, tooling. Most severe first. |
| "`reflection` revised the draft with no new sources" or any hard bug | `/mattpocock-skills:diagnosing-bugs` **(auto)** | Claude first builds one command that goes red on this bug (usually a pytest at the HTTP seam with the fake model). No theories before that. Then minimise, 3-5 ranked hypotheses, fix, regression test. |
| A test passes sometimes and fails sometimes (flaky) | `/mattpocock-skills:diagnosing-bugs` **(auto)** | Same loop. For a flake, the goal is a higher failure rate (loop it 100 times), not a clean repro. |
| Someone else filed an issue or bug report | `/mattpocock-skills:triage` **(you)**, e.g. "show me anything that needs my attention" or "let's look at #42" | Claude checks if it is already built or was rejected before, reproduces bugs, maybe grills you, then labels it and posts an agent brief (or triage notes, or closes it). |
| A huge, foggy effort (e.g. "make this multi-tenant with a real queue") | `/mattpocock-skills:wayfinder` **(you)** | Claude names the destination, then opens a map issue (`wayfinder:map`) with decision tickets as child issues. One ticket per session. It plans; it does not build. |
| A design question that talk cannot settle (e.g. "how should the debate stop rule behave?") | `git worktree add .claude/worktrees/prototype-<name> -b prototype/<name> origin/main`, then `/mattpocock-skills:handoff` **(you)**, open a new session in that folder, then `/mattpocock-skills:prototype` **(auto)** | A throwaway prototype in its own folder. For logic: one HTML file you click through. It is kept on the `prototype/<name>` branch, not on main. |
| A quick fact from docs (e.g. "what does OpenRouter put in `usage.cost`?") | Just ask Claude | Claude looks it up (Context7 for library and API facts, per your global CLAUDE.md). |
| I want a cited notes file in the repo on a topic | `/mattpocock-skills:research` (type it yourself here: your global CLAUDE.md stops Claude from starting it) | A background agent reads primary sources and writes one cited Markdown file. Name the folder (for example `docs/research/`); the repo has no notes convention yet. Take it into `grill-with-docs`. |
| The answer is in someone else's head | `/mattpocock-skills:to-questionnaire` **(you)** | Claude asks you who it is for and what you need back, then writes them a questionnaire. Their answers feed `grill-with-docs` or `to-spec`. |
| I want only the interview, with no docs saved and no wrapper | `/mattpocock-skills:grilling` **(auto)** | The interview primitive: rounds, the frontier, facts are Claude's job and decisions are yours. `grill-with-docs`, `grill-me`, `triage`, `wayfinder` and `improve-codebase-architecture` run it inside. |
| Change the issue tracker, triage labels or doc layout | `/mattpocock-skills:setup-matt-pocock-skills` **(you)**; already run once here | It rewrites `docs/agents/*.md`, which the other skills read. |
| "I have spare time; clean up the architecture" | `/mattpocock-skills:improve-codebase-architecture` **(you)** | Claude scans recent hot spots, writes an HTML report of deepening candidates to `$TMPDIR` and opens it. You pick one, then it grills you on it. |
| "Where should this interface go? Is this module too shallow?" | `/mattpocock-skills:codebase-design` **(auto)** | Vocabulary and rules: module, interface, depth, seam, adapter, leverage, locality, the deletion test. |
| "We say 'judge' for two different things" or "should this be an ADR?" | `/mattpocock-skills:domain-modeling` **(auto)** | Claude challenges the term, proposes one name, and updates `GLOSSARY.md`. It offers an ADR only if the decision is hard to reverse, surprising, and a real trade-off. |
| Claude's last message did not make sense | `/mattpocock-skills:wait-what` **(you)** | Claude says it again in simple English, with the words from `GLOSSARY.md`. |
| I need to set up a secret or API key (e.g. a new provider key in `.env` or a GitHub secret) | `/mattpocock-skills:wizard` **(auto)** | Claude writes a bash script that you run. It opens each URL, asks for each value with hidden input, and writes it into `.env` or GitHub secrets. Claude does not run it. |
| The conversation is long, or a phase just ended | See section 6 | Continue, `/clear`, `/mattpocock-skills:handoff`, a subagent, or `/compact`, in that order of questions. |
| I want to stress-test a plan that has no repo (a talk, a doc) | `/mattpocock-skills:grill-me` **(you)** | Same interview as `grill-with-docs`, but it saves nothing. In this repo, use `grill-with-docs`. |
| I want to learn a topic over many sessions (e.g. OpenTelemetry) | `/mattpocock-skills:teach` **(you)**, in a **separate folder**, not this repo | It treats the current folder as a teaching workspace and writes `MISSION.md`, `lessons/`, `reference/` there. |
| I am editing `CLAUDE.md`, a subagent file or a skill | `/mattpocock-skills:writing-for-agents` **(auto)** | The style guide for documents that agents read: context pointers, short always-loaded text, clear "done" criteria. |
| I don't know which skill fits and this file does not say | `/mattpocock-skills:ask-matt` **(you)** | The router skill: it reads the skills and suggests a flow. |

---

## 2. The main flow

```
  idea
   │
   ▼
 /mattpocock-skills:grill-with-docs ──► GLOSSARY.md, docs/adr/NNNN-*.md
   │
   │  a question needs running code?
   ├──► worktree ─► /handoff ─► new session there: /prototype ─► /handoff back
   │                       (prototype/<name> branch, own folder)
   ▼
 multi-session build? ── no ──► /implement right here ─────────────┐
   │ yes                                                           │
   ▼                                                               │
 /mattpocock-skills:to-spec ─────► GitHub issue (spec, ready-for-agent)
   │                                                               │
   ▼                                                               │
 /mattpocock-skills:to-tickets ──► ticket issues + blocking links   │
   │                                                               │
   ├─► per ticket: /clear → branch → /implement #N                 │
   │       (tdd inside, code-review at the end, commit)            │
   │                                                               │
   └─► or all at once: /implement-spec #spec                       │
           (parallel worktrees → integration branch → code-review) │
   │                                                               │
   ▼ ◄─────────────────────────────────────────────────────────────┘
 push → gh pr create (body from /pr) → gh pr merge <branch> --squash
   │                         (.claude/hooks/pr_gate.sh: ruff + pytest green)
   ▼
 /mattpocock-skills:retro ───────► suggested environment changes
```

Keep grill-with-docs → to-spec → to-tickets in **one session**. Do not `/clear` until the tickets
exist. Do not `/compact` either, unless the session nears ~150k tokens; then `/compact` at the
nearest phase boundary (for example, after grilling) with a goal.

With `implement-spec`, tell it each implementer worktree needs its own `TEST_DATABASE_URL` (create
`research_test_<n>`), or parallel pytest runs drop each other's tables (`tests/conftest.py` runs
`drop_all` on one shared `research_test` by default).

| Step | You do | Claude does | Leaves behind |
|---|---|---|---|
| `grill-with-docs` | Answer each round of questions. Type "yes" to accept a recommended answer. | Asks the open questions in rounds, looks up facts itself (often with a subagent), challenges fuzzy terms. | Updated `GLOSSARY.md`; an ADR in `docs/adr/` only for hard-to-reverse decisions. Files are created only when there is something to write. |
| `prototype` (detour) | Click through the prototype; decide. | Builds throwaway code that answers one question. | A `prototype/<name>` branch, linked from the issue. Only the decision goes to main. |
| `to-spec` | Confirm the test seams. | Writes the spec from the conversation (no new interview). | One GitHub issue: Problem, Solution, User Stories, Implementation and Testing Decisions, Out of Scope. Label `ready-for-agent`. |
| `to-tickets` | Approve the breakdown: size, blockers, merge or split. | Cuts tracer-bullet vertical slices, prefactoring first. | One issue per ticket, blockers first, with native blocking links and `ready-for-agent`. Sub-issues of the spec when the source was an issue. |
| `implement` | Make the branch; read the review. | `tdd` at agreed seams, runs single tests often and the full suite at the end, `code-review`, commit. | Commits on the current branch. |
| `implement-spec` | Start it; read the result. | Works the ready frontier in parallel, merges each ticket onto the integration branch, one review, fixes. | One integration branch (and a draft PR if the tracker closes work through PRs or you ask). |
| `pr` | Run the merge. | Writes the body: Summary, Evidence, Merge Danger. | The PR. |
| `retro` | Choose which suggestions to apply. | Reads the session, lists environment fixes, most severe first. | A list. You apply the ones you want (often as a new ticket). |

---

## 3. Worked example in this repo: a 4th architecture, `debate`

The idea: two debaters with opposite positions each search, then answer each other; a third role
writes the report.

**Session 1: plan (one unbroken session)**

1. `/mattpocock-skills:grill-with-docs` then say: "I want a 4th architecture, `debate`."
   Typical questions you get, each with a recommended answer:
   - Who decides the next step: the code, a debater, or the moderator? (The architecture-reviewer
     subagent fails it if it is only `react` with different prompts.)
   - How are the caps split? The caps (10 model calls, 6 searches) and the 300 s time limit are the
     same for all architectures (SPEC.md section 7, D11, D20). Like D19 for `reflection`, maybe 3 searches per
     side.
   - What is the stop rule: a fixed number of exchanges, or the moderator says "settled"?
   - Domain check: "You said 'judge' for the role that writes the report. `SPEC.md` and the code
     use **judge** for the evaluation model (`JUDGE_MODEL`) that scores runs. Call it **moderator**?"
     That answer goes into `GLOSSARY.md` at once.
   - Domain check: "You said 'round' for one back-and-forth between the debaters. `GLOSSARY.md`
     already defines **Round** as a reflection term (one pass of Critique, new Searches and
     Revision). Widen that definition, or call the debate one an **exchange**?"
   - Compare: `POST /research/compare` runs every architecture, so one comparison grows from
     3 to 4 runs plus 4 judge calls. Is that OK?

   Produces: `GLOSSARY.md` entries (debate, debater, moderator, and exchange or a widened Round).
   Maybe `docs/adr/0010-debate-search-split.md` if the cap split is hard to reverse, surprising and a
   real trade-off (number it after the highest existing ADR, as `docs/adr/README.md` says). The ADR
   cites the `D*` it extends (D19).

2. (Only if the stop rule is still unclear) Make a separate folder on a prototype branch:
   `git worktree add .claude/worktrees/prototype-debate-stop -b prototype/debate-stop origin/main`.
   Then type `/mattpocock-skills:handoff "prototype the debate stop rule"` **(you)**; it writes a
   file to `$TMPDIR`. Open a new session in the new folder, give it that file's path, type
   `/mattpocock-skills:prototype`, click through the HTML prototype, then
   `/mattpocock-skills:handoff` back and point to it in session 1.

3. `/mattpocock-skills:to-spec`. Claude proposes the seam. The highest existing seam here is the
   HTTP API (`POST /research/query` with `architecture: "debate"`, then `/result` and `/trace`), with
   only `call_openrouter` and `call_tavily` faked, as in `tests/test_reflection.py`. You confirm.
   Produces: GitHub issue "Spec: debate architecture", label `ready-for-agent`.

4. `/mattpocock-skills:to-tickets #<spec>`. A likely breakdown:

   | # | Ticket | Blocked by | Delivers |
   |---|---|---|---|
   | 1 | Debate tracer bullet: plan, one round, moderator report | none | `architecture: "debate"` returns a cited report; listed by `GET /research/architectures` |
   | 2 | Rebuttal exchanges, stop rule, caps | 1 | exchanges stop on the rule; at a cap the run still writes a report with `hit_cap` |
   | 3 | Compare includes debate | 1 | a comparison stores 4 runs and the winner rule still holds |
   | 4 | Docs and the end-to-end script cover debate | 2, 3 | the docs show the measured numbers for 4 architectures |

   You approve. Produces: 4 issues, sub-issues of the spec, with native GitHub blocking links,
   each `ready-for-agent`. Tickets 2 and 3 are both unblocked once 1 is done (that is the frontier).

**Session 2+: build (one fresh session per ticket)**

5. `/clear`, then make a branch named after the ticket, e.g.
   `git switch -c debate-1-tracer origin/main` (pull `main` first). For tickets 2 and 3 at the same
   time, use a worktree each: `.claude/worktrees/<branch>`, with its own `TEST_DATABASE_URL`.
6. `/mattpocock-skills:implement #<ticket-1>`. Claude uses `tdd` at the agreed seam and must follow
   the CLAUDE.md hard rules:
   - every model call through `llm.complete`, every search through `search.search`
     (`from app import llm, search`), so tests can replace `call_openrouter` and `call_tavily`;
   - every step recorded through `tracing.step()` (span + `steps` row);
   - same model (`LLM_MODEL`), caps, search tool and report template as the others; no model id in
     the architecture file; catch `tracing.CapReached` (D11);
   - the architecture is `async def run(query: str) -> str` in `app/agents/debate.py`, registered in
     `ARCHITECTURES` in `app/agents/__init__.py`;
   - a `plan` step first; no shared session inside `asyncio.gather`.
   At the end it runs `code-review` (Standards against CLAUDE.md, Spec against the ticket) and commits.
   Commit messages and the PR body reference the ticket ("Closes #N") so `code-review`'s Spec axis
   and GitHub can find it. `implement` does not add it by itself: ask for it.
7. Because `app/agents/` changed, ask Claude: "run the architecture-reviewer subagent". It checks
   structural difference, the fair comparison and the recording rules. Note: its brief says "2-3"
   architectures and "do not propose a new architecture", so it may need an update for 4 (a good
   `/retro` finding).
8. Push, then open the PR. Claude writes the body with `pr`. Merge with
   `gh pr merge debate-1-tracer --squash`. `.claude/hooks/pr_gate.sh` blocks the merge unless the
   branch is clean, pushed, and `ruff check`, `ruff format --check` and `pytest` are green.
9. Repeat 5-8 for tickets 2, 3, 4. Or, instead of 5-9, one `/mattpocock-skills:implement-spec #<spec>`.
10. `/mattpocock-skills:retro` in the last build session, before `/clear`.

---

## 4. On-ramps

These start somewhere else and then join the main flow.

### `/mattpocock-skills:triage` (you)

- **When:** issues or bug reports that **someone else** filed, or anything that arrives raw.
- **When not:** tickets from `to-tickets` or the spec from `to-spec`. They are already
  `ready-for-agent`. Do not triage them.
- **Example:** a user files "compare returns 500 when one run fails". Triage reads it, checks if it
  is already built or was rejected before (`.out-of-scope/`), tries to reproduce it, then gives
  `bug` + `ready-for-agent` with an agent brief. Later, `/mattpocock-skills:implement #<issue>` picks
  it up. Every triage comment starts with "This was generated by AI during triage."
- In this repo, PRs are not a triage surface (`docs/agents/issue-tracker.md`).

### `/mattpocock-skills:diagnosing-bugs` (auto)

- **When:** a bug that resists a first look, a flaky test, a regression between two good commits,
  a slow path.
- **When not:** an obvious one-line fix; just fix it, with a test.
- **Example:** "a `reflection` run sometimes ends with `hit_cap` and no revision". Phase 1 is one
  red command, e.g. `uv run pytest tests/test_reflection.py -k <name> -q` with a fake model that
  replays the bad critique. Then minimise, 3-5 ranked hypotheses (shown to you), tagged debug logs
  (`[DEBUG-xxxx]`), a regression test at a real seam, cleanup. If no good seam exists, that is the
  finding: take it to `improve-codebase-architecture`. Run `/mattpocock-skills:retro` after the fix.

### `/mattpocock-skills:wayfinder` (you)

- **When:** a huge, foggy effort that does not fit in one session, where you cannot yet see the way.
- **When not:** a well-scoped feature (a 4th architecture is well scoped: use `grill-with-docs`).
- **Example:** "run Runs on a durable queue with many API processes" (SPEC.md section 14
  says this is out of v1). Wayfinder opens a `wayfinder:map` issue and decision tickets typed
  `wayfinder:research`, `prototype`, `grilling` or `task`. One ticket per session (research tickets
  can run in parallel). When the way is clear, go to `/mattpocock-skills:to-spec`, not straight to
  `implement`.
- **One-time setup:** the `wayfinder:*` labels do not exist in this repo yet. Create them first, e.g.
  `gh label create wayfinder:map`.

---

## 5. Upkeep

- **`/mattpocock-skills:improve-codebase-architecture` (you).** Use it when you have spare time.
  It looks at recent hot spots in `git log`, finds shallow modules, and writes an HTML report to
  `$TMPDIR` (nothing in the repo). Each candidate has a before/after diagram and a badge
  (`Strong`, `Worth exploring`, `Speculative`). You pick one; it grills you on it. A picked candidate
  is a new idea: take it into `grill-with-docs` → `to-spec`. If you reject one for a lasting reason,
  it offers an ADR so the next scan does not suggest it again. In this repo it respects
  CLAUDE.md and the ADRs, so it will not re-argue "no agent framework" (D2) without a strong reason.
- **`/mattpocock-skills:codebase-design` (auto).** The vocabulary for module shape. Use it for
  questions like "should `search.search` hide the citation numbering?" Key rules: the interface is
  the test surface; one adapter is a hypothetical seam, two adapters are a real seam (here,
  `call_tavily` has a real adapter and a test fake: a real seam).
- **`/mattpocock-skills:domain-modeling` (auto).** The discipline that keeps `GLOSSARY.md` clean.
  `GLOSSARY.md` holds terms only, no implementation details. ADRs only when a decision is hard to
  reverse, surprising, and a real trade-off. `grill-with-docs` runs this for you.

---

## 6. Context hygiene and phase boundaries

A **phase** is one chunk of work: grilling, building, QA. Decide only **at the boundary** between two
phases. In the middle of a phase, continue, or send the rest to subagents.

Ask these questions in order. The first **yes** wins:

```
1. Can I continue here?
   (the next phase needs this one as a primary source, or ~150k tokens of smart zone remain)
      yes → CONTINUE
2. Is this context useless for what comes next?            yes → /clear
3. Must the work travel? (new harness, new folder or repo,
   a colleague, or a side task found mid-phase)             yes → /mattpocock-skills:handoff
4. Can it run with me away (AFK), tightly scoped?           yes → a SUBAGENT
5. Otherwise                                                    → /compact <what comes next>
```

- **Smart zone:** about 150k tokens. Past it, the model reasons less sharply.
- **Grilling → spec → tickets:** continue. Never clear before `to-tickets`. If the session nears
  ~150k tokens first, `/compact` at the nearest phase boundary (for example, after grilling) with a
  goal.
- **Between tickets:** `/clear`. Each ticket stands alone.
- **Prototype:** it lives in its own folder (a worktree on a `prototype/<name>` branch), so use
  `handoff` out and back.
- **Code review, architecture-reviewer, spec-auditor:** good subagent jobs.
- **`/compact`** is the default at the bottom, not the first thing to try. Give it a goal:
  `/compact we're going to QA the debate stop rule`.
- **`retro`:** run it in the session it reviews, before `/clear`.
- `/clear` is not final: the old session can be resumed. But clearing a context you still need loses
  the **why**, and reading the diff does not bring it back.
- `handoff` writes to `$TMPDIR`, not the repo, and points to issues and ADRs instead of copying them.

---

## 7. Words Matt uses

| Word | Plain meaning |
|---|---|
| **Tracer bullet** | A thin first version that goes through every layer end to end and works, so you see at once that the path is right. |
| **Vertical slice** | A ticket that cuts through all layers (route, job, agent, DB, test) for one small behaviour. Not "all the models first". |
| **Seam** | The place where you can change or observe behaviour without editing inside: where tests go. Here: the HTTP API, and `call_openrouter` / `call_tavily`. |
| **Blocking edge** | "Ticket B cannot start until ticket A is done." On GitHub, a native "blocked by" link. |
| **Frontier** | All work you can do now: open tickets with no open blockers (and, in wayfinder, not claimed). In grilling: the questions you can ask now. |
| **Smart zone** | The part of the context window (about 150k tokens) where the model still thinks well. |
| **Deep module** | A lot of behaviour behind a small interface. `search.search` is deep: one call hides the cap check, the step, the span, de-duplication and citation numbers. |
| **Interface** | Everything a caller must know: the signature, plus rules, order, errors, config, speed. |
| **ADR** | Architecture Decision Record: a short file in `docs/adr/` about one hard-to-reverse decision and why. |
| **GLOSSARY.md** | The project's word list at the repo root. One meaning per word. No implementation details. |
| **Triage roles / labels** | Category: `bug`, `enhancement`. State: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Exactly one of each per triaged issue. |
| **AFK agent** | An agent that works while you are away from the keyboard. `ready-for-agent` means an AFK agent can take it. |
| **Integration branch** | The one branch where `implement-spec` merges all ticket branches before review. |
| **Expand-contract** | How to do a wide rename safely: add the new form beside the old, move callers in batches, then delete the old form. |
| **Primary / secondary source** | The real session or code vs a summary of it. Every move except "continue" turns one into the other. |
| **One-way / two-way door** | A change you cannot easily undo (e.g. a migration that drops data) vs one you can revert. |

---

## 8. How this repo's own rules fit in

- **`SPEC.md` is the frozen v1 build spec.** Read its requirements (`R1`-`R16`) and decisions
  (`D1`-`D20`) for context. New work is not added to it.
- **New decisions** that are hard to reverse, surprising and a real trade-off → an ADR in
  `docs/adr/`, in the same change. It cites the `D*` it extends or replaces. Smaller decisions go in
  the spec or ticket issue.
- **New work** → GitHub Issues (`docs/agents/issue-tracker.md`). Labels: one category (`bug`,
  `enhancement`) plus one of the five state labels in `docs/agents/triage-labels.md`; `wayfinder:*`
  labels must be created first.
- **Domain docs** → `GLOSSARY.md` and `docs/adr/` at the root (single context,
  `docs/agents/domain.md`). Both exist: `GLOSSARY.md` defines Query, Run, Step, Source, Architecture,
  Judge and more, and `docs/adr/` holds ADRs 0001-0009. `docs/adr/README.md` is the index; a new ADR
  takes the next number after the highest file.
- **`CLAUDE.md` hard rules** still apply to every skill. `code-review`'s Standards axis checks the
  diff against them (there is no `CODING_STANDARDS.md`).
- **Merge gate:** `.claude/hooks/pr_gate.sh` runs on `gh pr merge <branch>`. It blocks unless the
  branch is checked out somewhere, clean, pushed, and ruff + pytest are green. Merge by branch name.
- **Other hooks:** `protect_migrations.sh` blocks edits to a committed migration (add a new revision);
  `format_python.sh` runs `ruff format` on each edited `.py` file.
- **Branches:** one branch and one PR per ticket (or one per spec with `implement-spec`), named after
  it. Never push to `main` (denied in `.claude/settings.json`). Do not put the letters `main` in a
  branch name (`domain`, `remaining`): the deny rule `git push*main*` blocks the push. The push
  allow-list only covers `step-*` branches, so a push of another branch name asks for permission
  first. Commit messages and the PR body reference the ticket ("Closes #N") so `code-review`'s Spec
  axis and GitHub can find it.
- **Subagents (ask Claude to run them):**
  - `architecture-reviewer`: after any change in `app/agents/`, `llm.py`, `search.py`, `tracing.py`
    or `evaluate.py`.
  - `spec-auditor`: checks the code against `SPEC.md` requirements. Run it after a change that touches
    an `R*` and before a release. For a GitHub spec issue, `code-review`'s Spec axis does that job.
- **Secrets:** keys live only in `.env`. The rule is CLAUDE.md hard rule 8; the setting only denies
  the Edit tool on `.env` (not Write or the shell). For a new key,
  use `wizard`: you run the script and type the key with hidden input. Use `<your-key>` in examples.

---

## 9. Beginner mistakes

- Running `triage` on tickets that `to-tickets` made. They are already `ready-for-agent`.
- Skipping `to-spec` for work that needs more than one session. The tickets then have nothing to
  point at, and `code-review`'s Spec axis has nothing to check against.
- Doing `/clear` between `grill-with-docs` and `to-tickets`, or `/compact` there while the session
  is still well under ~150k tokens. The spec then rests on a summary, not on the real reasoning.
- Not doing `/clear` between tickets. Each ticket is meant to start fresh.
- Going from `wayfinder` straight to `implement`. Go through `to-spec` first, unless the effort
  turned out small.
- Using `wayfinder` for a well-scoped feature. It is slow and dense; use `grill-with-docs`.
- Answering grilling questions with facts Claude could look up ("what is the search cap?"). Facts are
  Claude's job; decisions are yours.
- Asking Claude to start `to-spec`, `implement` or `retro` "by itself". User-only skills must be
  typed.
- Running `/implement` on `main`. It commits to the current branch: switch to a ticket branch first.
- Forgetting the architecture-reviewer subagent after changing `app/agents/`.
- Editing `SPEC.md` for a new decision instead of writing an ADR.
- Running `/teach` in the repo root. It writes `MISSION.md` and `lessons/` into the current folder.
- Running `retro` after `/clear`. Run it in the session it reviews (or point it at that session's log).

---

## 10. Learning path (one week)

| Day | Try | On this repo |
|---|---|---|
| 1 | `/mattpocock-skills:wait-what`, `/mattpocock-skills:codebase-design`, `/mattpocock-skills:domain-modeling` | Ask "explain the seams in `app/llm.py` and `app/search.py`". Read `GLOSSARY.md`, then ask `domain-modeling` to challenge one term. |
| 2 | `/mattpocock-skills:code-review` and `/mattpocock-skills:pr` | Review the last merged change: `/mattpocock-skills:code-review HEAD~1`. Read both axes. |
| 3 | `/mattpocock-skills:tdd` and `/mattpocock-skills:diagnosing-bugs` | Add one small behaviour test-first (e.g. a 404 case), or chase a real flaky test. |
| 4 | `/mattpocock-skills:grill-with-docs` | Grill a small idea (e.g. "show `cost_usd` in `/status`"). Watch `GLOSSARY.md` change. |
| 5 | `/mattpocock-skills:to-spec` → `/mattpocock-skills:to-tickets` → `/mattpocock-skills:implement` → PR | Take day 4's idea through the full flow, in the same session until the tickets exist. |
| 6 | `/mattpocock-skills:retro`, then `/mattpocock-skills:improve-codebase-architecture` | Retro day 5's session. Then read the architecture report; do not build anything yet. |
| 7 | `/mattpocock-skills:triage`, `/mattpocock-skills:handoff`, `/mattpocock-skills:prototype` | File a test issue as if from a user and triage it. Then prototype the `debate` stop rule from section 3. Ask "what's ready for agents to pick up?" through `triage`. Leave `implement-spec`, `wayfinder` and `to-questionnaire` for when you have a real job for them; `setup-matt-pocock-skills` only when you change tracker or labels. |
