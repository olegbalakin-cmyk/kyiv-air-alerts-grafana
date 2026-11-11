# Project State — current coordination snapshot

**Date:** 2026-11-11. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest C6 accepted: **C6-REPLAY-SEVASTOPOL-MERGED-01**. Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) merged `main@fe4ab1c1` (16/16 offline PASS); [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) merged `site-prod@6de49e3b` (8/8 PASS). Live ZIP/SHA, 23/23 source continuity and Neon readback remain **UNPROVEN**. `GLOBAL_CUTOVER=NO`.
Latest casualty research checkpoint: **CASUALTY-MULTI-ATTACK-HOLD-01** (attribution 4/4 PASS; proposed Odesa +1 UNSAFE due cross-attack mixing; publish OFF).

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
- **Casualty research:** Source capture 5 HTML/4 excerpts PASS. [Attribution offline #43007370603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43007370603) 4/4 PASS, but Odesa +1 AUTO_READY uses cross-attack details and is **REJECTED for promotion**. Reviewer incident extraction requires locality guard.

## Concrete next tasks

1. Inspect next **regular** C2 after both merges; no manual dispatch. Check writer, 23-city QA/Git JSON and safe export diagnostic; require real same-run ZIP + SHA-256. Workflow SUCCESS alone is not bundle PASS.
2. Verify Sevastopol source checkpoint advances with actual captured raw-page hash, pagination, overlap and provenance; historic alert `25006` remains unresolved. Require independent 23/23 full source receipts; absent proof stays BLOCKED.
3. Separately approve exact-run read-only Neon→JSON proof (PR #48) and DST raw baseline. Do not infer Netlify deployment from `site-prod` merge. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty: narrow offline incident-locality guard for multi-attack articles; Odesa Nov 7 must NOT be AUTO_READY on mixed paragraphs. Preserve direct-attribution fix and Dnipro hold; no media HTTP/merge/ledger changes.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-MULTI-ATTACK-HOLD-01 — attribution fixed, unsafe mixed-incident auto-proposal (2026-11-11)

- [Research `6d3c35d`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/6d3c35d452a034034a17bb671bf62400cb2eab55); [Actions #43007370603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43007370603) 4/4 PASS on frozen four publisher excerpts. Odesa MVA phrase `повідомив очільник …` now attributed; Dnipro remains unattributed. Odesa `AUTO_READY=1` and offline +1 **NOT ACCEPTED**: parsed place `residential-buildings`, slot `night`, weapon `drone` came from other attacks described in the same article. Artifact `13849147170`, ZIP SHA256 `d24d4bbf…2876d2cbf` verified; replay proposals 0, inputs unchanged.
- **Gate BLOCKED:** do not merge research parser or write `revisions.csv`. Next: narrowly prevent cross-incident fact mixing, keep evidence provenance, offline negative regression; no new source HTTP or publication.

## CASUALTY-FIVE-HTTP-SHADOW-PARTIAL-01 — five real WIP URLs; reviewer blocked (2026-11-11)

- [Live run #42998441793](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793): exact five pinned RSS IDs, 20 HTTP, **5 publisher HTML downloaded, 4 retained excerpts**, one `HTML_NO_ARTICLE_PARAGRAPHS`; unchanged reviewer **0 AUTO_READY/0 proposals**. Job failed only due research-harness 5-download vs 4-usable assertion; corrected without new publisher HTTP. Original artifact `13844887603`, 5/5 hashes PASS.
- [Offline replay #42998990269](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269) SUCCESS on same evidence: 0 duplicate proposals/deaths, protected hashes unchanged; artifact `13845600971`, 12/12 hashes PASS. Research [PR #66](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/66) draft. Next: offline factual attribution/incident extraction; publish OFF.

## CASUALTY-FIVE-WIP-INPUTS-01 — research selection validated (2026-11-11)

- [Final selection `d342b791`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/d342b7919e54cf49cac618fa8b7586477d199508/research/casualty_five_candidate_selection_2026_11_11/FINAL_SELECTION.md): five unique IDs all still `needs_review`, exact metadata matches WIP blob `f3f7141aa6d7584c63ff42510b40239a18834d15` (1,657 rows); selection blob `050d8560` unchanged. `main`/WIP revisions header-only, site-prod has only unrelated Sumy row. Research-only input PASS; publisher HTTP and actual casualty evidence **NOT** proven. Next ≤5 URL shadow requires separate owner authorization. No merge/publish.

## C6-REPLAY-SEVASTOPOL-MERGED-01 — two scoped fixes staged in production branches (2026-11-11)

- Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) squash-merged to `main@fe4ab1c14bffa03ff58f1f9debc3cc510f1099b0`, exact-head [Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850) **16/16 offline PASS** (UkraineAlarm event timestamp replay only).
- Owner-approved [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) squash-merged to `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20`, exact-head [Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821) **8/8 offline PASS** (Sevastopol checkpoint eligibility only). No synthetic event closure, no cutover.
- First post-merge C2 and exact ZIP/SHA, source receipt continuity across all 23 cities, independent Neon readback and any Netlify deployment **not yet verified**. Prior source checkpoint 22/23; `25006` still unresolved. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-THREE-RUN-EXPORT-01 — exact blockers after activated cycles (2026-11-11)

- [42902124611](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42902124611) and [42908463331](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42908463331) SUCCESS; [42970870607](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42970870607) data/Neon/23-city QA/Git PASS (`site-prod@390e7635`, 33,066 episodes), overall FAIL at artifact upload.
- All three bundle exports BLOCKED `CAPTURE_NAIVE_TIMESTAMP`, no ZIP/SHA; 22/23 checkpoints refreshed, Sevastopol stuck since bootstrap. Cutover NO.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
