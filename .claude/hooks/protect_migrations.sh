#!/bin/bash
# PreToolUse (Edit|Write): a committed migration must not change. Exit 2 blocks the edit. Needs jq.
f=$(jq -r '.tool_input.file_path // empty')
[[ "$f" == */migrations/versions/*.py ]] || exit 0
# Any git error (no repository, file not in HEAD) means "not committed": the edit is permitted.
if git -C "$(dirname "$f")" cat-file -e "HEAD:./$(basename "$f")" 2>/dev/null; then
  echo "Blocked: $f is a committed migration. Add a new revision: uv run alembic revision --autogenerate -m \"...\"" >&2
  exit 2
fi
exit 0
