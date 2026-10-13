#!/usr/bin/env bash
# Walks all 7 routes of SPEC.md section 4 against a running API: one run, then one comparison.
# Usage: BASE=http://localhost:8000 bash scripts/e2e.sh   (needs curl and jq; exits 1 on a wrong status)
BASE=${BASE:-http://localhost:8000}
out=$(mktemp)
trap 'rm -f "$out"' EXIT
failed=0

# call METHOD PATH WANT_STATUS [JSON_BODY [JQ_CHECK]]: prints one line for the call, the body is in
# $out. JQ_CHECK is a jq filter that must be true for the body.
call() {
  local code mark=OK note=
  code=$(curl -s -o "$out" -w '%{http_code}' -X "$1" "$BASE$2" -H 'Content-Type: application/json' ${4:+-d "$4"})
  [ "$code" = "$3" ] || mark=FAIL
  [ -z "$5" ] || jq -e "$5" "$out" >/dev/null 2>&1 || { mark=FAIL; note="  body check failed: $5"; }
  [ $mark = OK ] || failed=1
  printf '%-4s %-4s %-44s %s (want %s)%s\n' "$mark" "$1" "$2" "$code" "$3" "$note"
}

# wait_for PATH SECONDS TRIES: polls the status of a run or a comparison until it is done or failed
# (or the tries are used up). Sets $status.
wait_for() {
  for _ in $(seq "$3"); do
    status=$(curl -s "$BASE$1" | jq -r .status)
    case "$status" in done|failed) break ;; esac
    sleep "$2"
  done
}

call GET /research/architectures 200 "" '[.[].name] | sort == ["orchestrator", "react", "reflection"]'

# --- one run (react) ---
call POST /research/query 202 '{"query": "How do HTTP/2 and HTTP/3 differ?"}'
id=$(jq -r '.id // empty' "$out")
[ -n "$id" ] || exit 1   # no run to follow
echo "run id: $id, first status: $(jq -r .status "$out")"
call GET "/research/$id/result" 409   # the run has just started, so it is not done

wait_for "/research/$id/status" 3 120   # every 3 s, at most 360 s (the run limit is 300 s, D20)
call GET "/research/$id/status" 200
echo "final status: $status $(jq -r '.error // empty' "$out")"
[ "$status" = done ] || failed=1

call GET "/research/$id/result" 200
jq -c '{architecture, model, sources: (.sources | length), metrics}' "$out"
call GET "/research/$id/trace" 200
jq -c '{trace_id, trace_url, steps: [.steps[].type]}' "$out"

call GET /research/00000000-0000-0000-0000-000000000000/status 404
call POST /research/query 422 '{"query": ""}'

# --- one comparison (three runs one after the other, then the judge: several minutes) ---
call POST /research/compare 422 '{"query": ""}'
call GET /research/compare/00000000-0000-0000-0000-000000000000 404
call POST /research/compare 202 '{"query": "How do HTTP/2 and HTTP/3 differ?"}' '.run_ids | length == 3'
cid=$(jq -r '.comparison_id // empty' "$out")
[ -n "$cid" ] || exit 1   # no comparison to follow
echo "comparison id: $cid"

wait_for "/research/compare/$cid" 5 300   # every 5 s, at most 1,500 s (3 runs of up to 300 s, then the judges)
call GET "/research/compare/$cid" 200 "" \
  '.status == "done" and .method == "judge_mean_v1" and has("winner") and (.runs | length == 3)'
echo "comparison status: $status"
jq -c '{winner, runs: [.runs[] | {architecture, status}]}' "$out"

exit $failed
