# Project State — current coordination snapshot

**Date:** 2026-11-11. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest C6 accepted: **C6-REPLAY-SEVASTOPOL-MERGED-01**. Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) merged `main@fe4ab1c1` (16/16 offline PASS); [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) merged `site-prod@6de49e3b` (8/8 PASS). Live ZIP/SHA, 23/23 source continuity and Neon readback remain **UNPROVEN**. `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-FULL-OFFLINE-45-01** (45/45 PASS, authentic fixture; Odesa +1 held; publish OFF).

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git JSON delivery unchanged; last verified updater `42970870607` published data on `site-prod@390e7635`. Code-only Sevastopol fix merged to `site-prod@6de49e3b`, but no new C2 publication or confirmed Netlify deployment. No Neon cutover.
- **Neon reader / historical parity:** frozen 23-city [proof 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03), 0 unexplained diffs; no current full continuity PASS.
- **Live writer / provenance:** last `NEON_SUCCEEDED` 33,066 episodes/23 cities. 22/23 source checkpoints refreshed; Sevastopol still first-run until fresh C2. Its historic `25006→25008` alert remains unresolved.
- **23-city generator / publication:** previous three exports BLOCKED `CAPTURE_NAIVE_TIMESTAMP`. Work A fix merged to `main@fe4ab1c1`; no actual post-merge C2 ZIP/SHA or independent readback yet.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** frozen browser/CSV/rollback [proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) research-only; operational cutover and rollback gates OPEN.
- **Operational WIP / historical reference / backfill:** separate tracks; no promotion by research proof.
- **Casualty research:** [offline Actions #43034383784](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784) 45/45 PASS (10 new, 35 legacy). Odesa/Dnipro NEEDS_REVIEW; 0 real proposals/duplicates. Synthetic single-attack AUTO_READY PASS. Publication unproven.

## Concrete next tasks

1. Inspect next **regular** C2 after both merges; no manual dispatch. Check writer, 23-city QA/Git JSON and safe export diagnostic; require real same-run ZIP + SHA-256. Workflow SUCCESS alone is not bundle PASS.
2. Verify Sevastopol source checkpoint advances with actual captured raw-page hash, pagination, overlap and provenance; historic alert `25006` remains unresolved. Require independent 23/23 full source receipts; absent proof stays BLOCKED.
3. Separately approve exact-run read-only Neon→JSON proof (PR #48) and DST raw baseline. Do not infer Netlify deployment from `site-prod` merge. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty: check a small set of other *retained real articles* offline for mixed-incident errors and missed safe cases; no new publisher HTTP without owner approval. No merge or casualty publication.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-FULL-OFFLINE-45-01 — full regression accepted (2026-11-11)

- [Actions #43034383784](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784) at `adb0419c`: **45/45 PASS**; original fixture from `05ce47b1` verified by SHA256; [artifact `13863350735`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784/artifacts/13863350735) ZIP SHA256 `14e7c469…8c69d3`. Odesa/Dnipro NEEDS_REVIEW; no real proposals or duplicates. [Full report `f46753e4`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/f46753e4b85e56052639959beb1d96ee408e227e). Research-only; production/publication NOT approved.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
