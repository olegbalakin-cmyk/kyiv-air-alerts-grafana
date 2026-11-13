# Project State — current coordination snapshot

**Date:** 2026-11-13. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-WORKL-FIRST-OWNER-LAUNCH-PREHTTP-CI-BLOCK-01**. Owner-approved Work L single launch [#43502247617](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43502247617) at `e1f9c3af` failed in pre-HTTP offline test: `_pr102/.../capture_once.py` missing. Grant/commit gates PASS; capture step SKIPPED; **0 source GET**, no evidence, no publication. **Authorization consumed; no retry.**

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git JSON updated and remote publication confirmed in C2 #43055353190 (`site-prod@cf960d7c`); frontend/source still Git, no Neon cutover. Netlify deployment not independently verified.
- **Neon reader / historical parity:** frozen 23-city [proof 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03), 0 unexplained diffs; no current full continuity PASS.
- **Live writer / provenance:** C2 #43055353190 `NEON_SUCCEEDED`, 33,135 episodes (69 inserted), 23/23 checkpoints match run/attempt/workflow SHA. Sevastopol checkpoint advanced; its historical alert `25006→25008` remains unresolved.
- **23-city generator / publication:** first real post-merge same-run export PASS (`C2 ZIP SHA-256=ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, artifact `13873291895`, manifest SHA `f6462093...3e433`); no `CAPTURE_NAIVE_TIMESTAMP`. Independent Neon→JSON readback still OPEN.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** frozen browser/CSV/rollback [proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) research-only; operational cutover and rollback gates OPEN.
- **Operational WIP / historical reference / backfill:** separate. **Casualty:** Work C/D/E and joint F/H PASS in isolated research; I strict redirects PASS; owner-authorized one-time #118 transport 10/10 HTTP 200, but fact parser 0 reports and no claim excerpts saved. WIP, site-prod casualty ledger, scheduled ingestion and publication unchanged. No more HTTP authorized.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty Work H: PR #114 current site-prod frontend compatibility accepted in isolated browser (no merge/production). Work I PR #115 strict redirects accepted offline. Monitor exact site-prod baseline before future release.
5. Casualty next: fix Work L live workflow test fixture checkout (`_pr102/.../capture_once.py`) in separate offline-only research branch; prove complete live-job pre-network safety locally/CI before requesting NEW owner grant and fresh one-shot SHA. Do not re-run #43502247617 or modify existing launch branch.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKL-FIRST-OWNER-LAUNCH-PREHTTP-CI-BLOCK-01 — one authorized launch blocked before GET (2026-11-13)

- [Actions #43502247617](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43502247617) attempt 1, exact `e1f9c3af1dacd3fe77e2ba899df14afb6dd84858`: launch-only owner/commit gate PASS, offline safety test FAIL because `_pr102/research/casualty_zaporizhzhia_http_capture_2026_11_12/capture_once.py` missing. Source capture job SKIPPED; no artifact, **0 HTTP GET**, 0 source facts, 0 casualty credit, production unchanged. Owner one-shot authorization treated CONSUMED; new offline fix and fresh approval required. Never rerun or reuse this launch branch grant.

## CASUALTY-WORKL-THREE-SOURCE-LIVE-PREFLIGHT-OFFLINE-PASS-01 — bounded three-source pilot offline PASS, new owner grant required (2026-11-13)

- [PR #124](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/124) HEAD `78fd147294cc2cd2b7c5d8f608aee8778a20beca`; [Actions #43500434087](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43500434087) SUCCESS 68/68 offline, 0 source GET. [Artifact #14072718715](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43500434087/artifacts/14072718715) independently SHA256 MATCH `f3d8742828897bda7c102ce7a4d9cb985db18b784ad9ca94eb46c93a86feb2e0`, 4/4 inner JSON hashes. Proposed T03/T04/T05 exact three sources, max six GET, redirect-default-deny, one-shot launch.json-only research workflow, no active grant or launch. Trigger availability not independently verified. 3 synthetic cards, Work J excerpts & privacy holds PASS offline; real event identity/2→3/prior credits unknown. No publication or production changes.

## CASUALTY-WORKK-THREE-SOURCE-RUNNER-OFFLINE-PASS-01 — evidence runner offline PASS (2026-11-13)

- [PR #122](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/122) `69e7d023`, [CI #43439055939](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939) 59+10 PASS, [ZIP #14044811680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939/artifacts/14044811680) SHA256 independently MATCH `369c98cce533fe7e4fac0032d9f80b48b0c03cd86da578bce8f6bac2cfcbc766`. Three mock cards and hash manifest verified; real +23 regression PASS. No new HTTP or launch authorization; real 2→3 claim and official match still NEEDS_REVIEW.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
