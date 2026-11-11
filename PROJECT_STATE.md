# Project State — current coordination snapshot

**Date:** 2026-11-11. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**.
Latest casualty research: **CASUALTY-EXPLICIT-MILITARY-STATUS-54-01**, 54/54 offline PASS; still unpublished, next bounded task cumulative 18→20→23 in Zaporizhzhia. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.

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
- **Operational WIP / historical reference / backfill:** remain separate, not promoted. **Casualty:** [military-status PR #69](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/69) 54/54 PASS in isolated offline research; Ivano-Frankivsk explicit military deaths now fail closed. Zaporizhzhia chronological 18→20→23 and false warning-place remain open. No casualty merge, publication or production change.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty track: independently fix chronological same-incident **18→20→23** official updates for Zaporizhzhia using original retained evidence; keep separate attacks, retractions, civilian military status, source, date/geography and dedup gates; offline-only research, no media HTTP, operational revisions or merge. Investigate unrelated warning text as attack place in another scoped task.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-EXPLICIT-MILITARY-STATUS-54-01 — bounded offline safety fix PASS (2026-11-11)

- [Research PR #69](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/69) draft, final `03cfaecb`; exact [Actions #43069489502](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43069489502) **54/54 PASS** (9 targeted +45 legacy), artifact `13876734185` ZIP SHA256 `e441eeed9817bbc41f73036376cc1c6c85047d097cc8ed97e0a28844d64540a4`. LB.ua Ivano-Frankivsk `Загиблі — військовослужбовці` now `civilian_ambiguous`/`facts.civilian=None`, `NEEDS_REVIEW`, 0 proposed civilian deaths; synthetic complete-source military case held independently. Civilian-positive controls PASS, replay duplicates 0, protected inputs unchanged. [Full report](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/03cfaecb71111bfd3b896e4a19ca6f027118963f/research/casualty_military_status_fix_2026_11_11/FINAL_REPORT.md). Earlier [3-real-article proof PR #67](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/67) remains: Zaporizhzhia 18→20→23 last total missed (`NEEDS_REVIEW`), a separate place-extraction defect persists.
- **Research accepted only; no merge, production, WIP/ledger or casualty publication approval.** Earlier casualty proof/transition details remain in draft [coordination PR #65](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/65); this new coordination branch is based on current `main`, preserving newer C6 checkpoints.

## C6-POSTMERGE-C2-EXPORT-23-01 — physical same-run export and checkpoints PASS (2026-11-11)

- [Actions #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) scheduled C2 SUCCESS (16:08:40–16:36:22 UTC), after Work A `main@fe4ab1c1` and Work B `site-prod@6de49e3b`. `NEON_SUCCEEDED`: 33,135 canonical episodes (+69), 23-city QA, Git JSON publication `site-prod@cf960d7c` PASS.
- Actual C2 ZIP artifact [#13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895) uploaded (`c2-shadow-inputs-43055353190-1`, 3,669,061 bytes), export ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`. `CAPTURE_NAIVE_TIMESTAMP` absent; 23/23 persistent source checkpoints share GitHub run ID `43055353190`; Sevastopol now updated, historical `25006→25008` remains unresolved.
- **Proof boundary:** successful export/capture does not establish independent Neon readback/parity, source freshness all-city PASS in readback, Netlify deployment, approved DST/rollback or permission for global source switch. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

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
