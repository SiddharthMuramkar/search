---
name: milestone
description: Build one milestone of SPEC.md end to end - code, checks, audit and a review summary. Use as /milestone M2.
argument-hint: [milestone id, for example M2]
disable-model-invocation: true
---

Build milestone `$ARGUMENTS` of this project.

1. **Read.** In `SPEC.md` section 13, find the row for `$ARGUMENTS`. Read each requirement it lists
   (section 3) and the design sections those requirements depend on. Read the hard rules in `CLAUDE.md`.
2. **Check the docs.** For each library API that this repository does not use yet, read the current
   documentation first. Several libraries in this stack changed in the last weeks.
3. **Build.** Write the smallest version that meets the "Done when" check of the milestone. Do not
   build a later milestone. The contract tests in `tests/` are skipped until `app/main.py` exists;
   make the tests of this milestone pass and leave the later ones as they are.
4. **Verify.** Run `uv run ruff check .` and `uv run pytest -q`. Repair what fails. If the check needs
   the running stack (Docker, the API) and the shell cannot start it, give the user the exact commands
   and wait for the result. Do not report a check as passed if it did not run.
5. **Audit.** Run the `spec-auditor` subagent with scope `$ARGUMENTS`. If `app/agents/`, `app/llm.py`,
   `app/search.py`, `app/tracing.py` or `app/evaluate.py` changed, run `architecture-reviewer` too.
   Repair real gaps. Record a new assumption or a changed decision in `SPEC.md` sections 10 and 11.
6. **Report for review.** In this order: what was built (5 lines at most); the main design decision
   and its tradeoff; the files to read first; what was not done or not checked.
7. **Commit.** Propose a commit message. Ask before you commit.
