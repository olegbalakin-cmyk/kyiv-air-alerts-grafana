# WORK M — CASUALTY: FIX PRE-HTTP CI BLOCKER

**Scope:** offline CI and minimal fixture checkout repair, based on the frozen Work L pre-launch HEAD `78fd147294cc2cd2b7c5d8f608aee8778a20beca`. No source HTTP authorized.

## Confirmed root cause

The first owner-approved launch Actions #43502247617 attempt 1 at `e1f9c3af1dacd3fe77e2ba899df14afb6dd84858` completed the grant and launch-only checks but failed before source HTTP on `FileNotFoundError: _pr102/research/casualty_zaporizhzhia_http_capture_2026_11_12/capture_once.py`. HTTP source step was skipped, real external source GET = **0**. Never rerun this workflow or reuse its authorization.

The live workflow omitted the immutable `_pr102` checkout present in offline Work L. Work G `test_preflight.py` also needs `_site/kyiv-air-alerts-grafana/data/casualties` for test 11. Both are pinned already by the accepted offline workflow.

## Minimal changes

- `.github/workflows/research-casualty-workl-three-live-once.yml` — add checkout of `_pr102@bb553f9285...` and `_site@d0a7d22d...`, plus cleanliness/pin verification. Existing live trigger, budget, safety suite and capture step unchanged.
- `.github/workflows/research-casualty-workl-offline.yml` — enable offline-only push CI for this independent research branch, with a dedicated exact-live-checkout pre-HTTP job alongside the original complete offline proof.
- `research/casualty_workm_prehttp_ci_fix_2026_11_13/verify_prehttp.py` — full 68-test suite, mocked grant and negative cases, socket/HTTP network guards, three synthetic Work J cards and digest validation.
- This `FINAL_REPORT.md` — frozen scope and evidence record.

## Safety boundary

Separate immutable base branch `research-casualty-workm-prelaunch-base-2026-11-13` is pinned to the true pre-launch HEAD, making the new Draft PR a narrow diff without copying the consumed `launch.json`. This Work M branch never includes a `launch.json`. The real live workflow remains branch/path filtered exclusively to the *different* Work L research branch. No live trigger is enabled here.

The future scope remains **only T03/T04/T05**, ≤6 GET including redirects, no unknown redirects, ≥1 s interval, ≤1 MB response, 15 s timeout, 0 retries, one run, ≤24 h authorization. All retained casualty evidence is unverified, NEEDS_REVIEW; no PROMOTE/ledger changes.

## CI evidence

Exact-HEAD GitHub Actions physical proof, artifact ID/digest and final result are recorded in this Draft PR's follow-up evidence after running. A PASS is **not** permission for real HTTP; a new explicit owner authorization, new exact SHA, new unique authorization ID and a new launch-only configuration would all be required.

**Owner grant: NOT AUTHORIZED. HTTP source GET: 0 in this repair.**
