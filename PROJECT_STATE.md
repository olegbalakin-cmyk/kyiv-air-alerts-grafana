# Project State — current coordination snapshot

**Date:** 2026-11-12. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-SAME-INCIDENT-DEDUP-25-01**, **25/25 exact-head physical PASS** on frozen site-prod with explicit identity/credit proofs; **research-only**, PR #89 contains 166 main-relative files and is **NOT merge-ready**. Work B **BLOCKED_MISSING_EVIDENCE** (11 sources); October **COVERAGE_INCOMPLETE ≥23**. **No publication**.

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
- **Operational WIP / historical reference / backfill:** unchanged. **Casualty:** [dedup research PR #89](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/89) verifies 0/18/23→23, same-event cumulative, rollback and Sumy+1 at fixed `site-prod@fc726166` (**25/25 PASS**). Its base `main` causes 166 unrelated-diff files; isolate patch against correct production target before any future release. [Source Work B PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88): 11 bodies missing, October ≥23 minimum incomplete. **Release NO-GO**.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty Work A: **do not merge PR #89 as-is** (166 changed files against main). Independently review minimal `update_casualties.py` dedup change against frozen `site-prod@fc726166` (five actual changed files in research compare), package a narrowly scoped isolated PR for the correct target only after owner approval, rerun 25/25 and check operational legacy/Sumy+1 backward compatibility. Human-verify incident identity and baseline-credit evidence; proof handles alone do not validate facts. Never publish October as full month.
5. Casualty Work B: request owner authorization for **bounded source-body capture of up to 11 named candidate articles** from [PR #88 matrix](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88), or recover direct publisher/official archived texts offline first. Confirm real attack date, Zaporizhzhia city, civilian status, unique event and cumulative count; never infer complete October from RSS. Capture in isolated research only, separate proof, no production.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-SAME-INCIDENT-DEDUP-25-01 — read-only exact-head research PASS (2026-11-12)

- [Draft PR #89](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/89) exact `d406875cd5ccbd382fc736fcbb9a3cdc3a448289`, [Actions #43201016241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43201016241) SUCCESS **25 domain PASS, 0 FAIL**, independently downloaded artifact `13936055275` SHA256 `4a7aefc61f4d47683b72d0b33ec81deb57104eff6933873a2b2923d2ada4179f`. Frozen `site-prod@fc726166`; explicit incident identity, cumulative/delta classification and evidence-backed prior credit fix 18→23 to +5, 23→23 +0, 18→20→23 total 23. Reject ambiguous records; preserve pinned Sumy+1, other cities, October row and rollback. Proof handles require human review. **Research PASS only**: PR's `main` comparison contains 166 changed files (vs five actual research files from frozen production); do not merge. Work B source evidence and October completeness still NO-GO.

## CASUALTY-ZAPORIZHZHIA-ADDITIONAL-EVENTS-WORKB-01 — source evidence unavailable (2026-11-12)

- [PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88) final `34bc539d`: 11 WIP candidates / 5 priority Sep–Oct Zaporizhzhia groups, all `BLOCKED_MISSING_SOURCE` (no original publisher body). Retained earlier captures do not match target IDs. **0 additional deaths established by this review** is NOT a finding of zero actual deaths. October remains **≥23 minimum / COVERAGE_INCOMPLETE**. No new HTTP, CI or source ZIP verification claimed; production and WIP unchanged.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
