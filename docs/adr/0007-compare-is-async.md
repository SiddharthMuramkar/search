# `POST /research/compare` returns 202 and the comparison is polled

A comparison runs two research jobs in sequence and takes minutes, and the brief says research must not block the request. So `POST /research/compare` returns 202 with `{comparison_id, run_ids, result_url}`, and the client polls `GET /research/compare/{id}`. The brief does not say whether the POST may block. This is open question 2 in SPEC.md §10, which was never sent, and 202 plus GET is the default the build uses. A comparison is `failed` only when no run finished. Otherwise it completes over the runs that did.

Source: SPEC.md §4, §10 (question 2)
