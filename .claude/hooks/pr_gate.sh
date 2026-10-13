#!/bin/bash
# PreToolUse (Bash): `gh pr merge <branch>` passes only when that branch is clean, pushed, and
# ruff + pytest are green. Exit 2 blocks the merge. Needs jq.
cmd=$(jq -r '.tool_input.command // empty')
# Only a real command counts: at the start of a line or after && || ; |. Not text in a message.
grep -qE '(^|&&|\|\||;|\|)[[:space:]]*gh[[:space:]]+pr[[:space:]]+merge' <<<"$cmd" || exit 0
fail() { echo "Blocked: $1" >&2; exit 2; }
cd "${CLAUDE_PROJECT_DIR:-.}" || fail "no project folder"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"
# The branch is the first plain word after "gh pr merge".
branch=$(sed -E 's/.*gh pr merge//' <<<"$cmd" | tr ' ' '\n' | grep -m1 -E '^[A-Za-z0-9]')
# The folder that has this branch checked out: the main folder or a worktree.
# shortcut: a folder path with a space is not found, use `git worktree list -z` then.
dir=$(git worktree list --porcelain | awk -v b="refs/heads/$branch" '$1=="worktree"{d=$2} $1=="branch"&&$2==b{print d}')
[[ -n "$dir" ]] && cd "$dir" || fail "merge by branch name (gh pr merge step-N ...); no folder has '$branch' checked out"
[[ -z "$(git status --porcelain)" ]] || fail "uncommitted changes in $dir"
git fetch -q origin "$branch" 2>/dev/null
[[ "$(git rev-parse HEAD)" == "$(git rev-parse "origin/$branch" 2>/dev/null)" ]] || fail "$branch is not pushed"
out=$(uv run ruff check . 2>&1 && uv run ruff format --check . 2>&1 && uv run pytest -q 2>&1) \
  || { tail -30 <<<"$out" >&2; fail "ruff or pytest is red on $branch"; }
exit 0
