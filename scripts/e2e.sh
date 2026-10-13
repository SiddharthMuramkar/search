#!/usr/bin/env bash
# Walks the single-run routes of SPEC.md section 4 against a running API; M7 adds the other routes.
# Usage: BASE=http://localhost:8000 bash scripts/e2e.sh   (needs curl and jq; exits 1 on a wrong status)
BASE=${BASE:-http://localhost:8000}
out=$(mktemp)
trap 'rm -f "$out"' EXIT
failed=0

# call METHOD PATH EXPECTED_STATUS [JSON_BODY]: prints one line for the route, the body is in $out
call() {
  local code mark=ok
  code=$(curl -s -o "$out" -w '%{http_code}' -X "$1" "$BASE$2" -H 'Content-Type: application/json' ${4:+-d "$4"})
  [ "$code" = "$3" ] || { mark=FAIL; failed=1; }
  printf '%-4s %-4s %-44s %s (want %s)\n' "$mark" "$1" "$2" "$code" "$3"
}

call POST /research/query 202 '{"query": "How do HTTP/2 and HTTP/3 differ?"}'
[ $failed = 0 ] || exit 1   # no run to follow
id=$(jq -r .id "$out")
echo "run id: $id, first status: $(jq -r .status "$out")"
call GET "/research/$id/result" 409   # the run has just started, so it is not done

for _ in $(seq 80); do   # every 3 s, at most 240 s
  status=$(curl -s "$BASE/research/$id/status" | jq -r .status)
  case "$status" in done|failed) break ;; esac
  sleep 3
done
call GET "/research/$id/status" 200
echo "final status: $status $(jq -r '.error // empty' "$out")"
[ "$status" = done ] || failed=1

call GET "/research/$id/result" 200
jq -c '{architecture, model, sources: (.sources | length), metrics}' "$out"
call GET "/research/$id/trace" 200
jq -c '{trace_id, trace_url, steps: [.steps[].type]}' "$out"

call GET /research/00000000-0000-0000-0000-000000000000/status 404
call POST /research/query 422 '{"query": ""}'

exit $failed
