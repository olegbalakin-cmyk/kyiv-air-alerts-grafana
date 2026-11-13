# WORK N — CASUALTY: FINAL CLEAN REARM FOR T03–T05

**Track:** isolated research / offline only. **Verdict pending exact-HEAD CI.**
**Branch:** `research-casualty-workn-clean-rearm-2026-11-13`. **Immutable ancestor:** Work M `657fd70564bf5393d3fcd209e47d95fa986f3010`.
**Coordination:** no edits to PR #71/#117. The Actions run, artifact ID/digest and final exact HEAD must be documented in the new Draft PR evidence comment (a Git commit cannot embed its own final hash without changing it).

## Clean rearm and minimal changes
- New research branch is cut directly from Work M immutable HEAD; the consumed Work L launch commit `e1f9c3af1dacd3fe77e2ba899df14afb6dd84858` is not in its history.
- Existing live workflow is bound exclusively to this branch and a push changing only `research/casualty_one_time_capture_2026_11_13/launch.json`. No such file is supplied or authorized here.
- Non-launch pushes use the original complete Work E/G/I/J/K/L offline proof plus Work M exact-live-checkout pre-HTTP proof. PR-to-Work-M checks are offline only.
- Work K runner's base anchor now points to Work M, and the live gate also verifies its ancestry; the future launch's `expected_previous_commit_sha` and `expected_preflight_head_sha` must both match the exact final Work N HEAD approved by the owner.
- The consumed Work L authorization ID and original T01–T10 authorization are explicitly rejected. All owner, branch, exact SHA, commit-parent, first attempt, one-file diff, prior launch history and 24-hour expiry gates remain before first GET.
- Immutable `_wip@43b58049`, `_pr102@bb553f92`, `_site@d0a7d22d` fixtures preserved. Work J/K logic, parser, source blobs, casualty data, WIP, production and Neon unchanged.

## Frozen source and resource contract
- T03 UKRINFORM: https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
- T04 MIG: https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
- T05 Zaporizhzhia Police: https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

Only those three URLs; up to **6 total GET including redirects**; **0 approved redirect URLs**, ≥1 s request spacing, ≤1,000,000 bytes/response, 15 s timeout, **0 retry**, one first-attempt push, ≤24 h owner authorization. Unknown redirect blocked. Original texts remain separate `NEEDS_REVIEW` (2 → 3 never means 2+3). No automatic death credit, PROMOTE or publication.

## Offline proof requirement
- GitHub Actions proof on **the final branch HEAD**, with all **68/68 tests PASS, SKIP=0**, both jobs SUCCESS, synthetic 3-card SHA-256 retention and the real-original 18→20→23 regression.
- `workm-prehttp-proof.json` and `workn-rearm-proof.json` are evidence outputs; SHA-256 of the ZIP must be reported from GitHub.
- No real HTTP permitted even if all offline checks pass. Current authorization template remains `NOT_AUTHORIZED`; no `launch.json` and no new authorization ID.

## Separate owner consent — NOT GIVEN
After exact-head CI passes, the coordinator may offer a **new, separate one-shot consent** explicitly naming the final Work N HEAD, branch, all three URLs, all resource limits and the zero-publication policy. A distinct authorization ID and approval/expiry UTC timestamps are to be created **only after that consent**. The next and only network-eligible commit must add exactly `launch.json` atop the approved HEAD. Pushes/PRs before that are strictly offline.
