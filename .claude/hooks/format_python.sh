#!/bin/bash
# PostToolUse (Edit|Write): format the edited Python file. Needs jq.
# Format only: a lint autofix here would remove an import before the next edit uses it.
f=$(jq -r '.tool_input.file_path // empty')
[[ "$f" == *.py ]] || exit 0
ruff="${CLAUDE_PROJECT_DIR:-.}/.venv/bin/ruff"
[[ -x "$ruff" ]] || exit 0
"$ruff" format --quiet "$f" 2>/dev/null
exit 0
