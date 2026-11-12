# Project State — current coordination snapshot

**Date:** 2026-11-12. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-DEDUP-CODE-SITEPROD-MERGED-01** owner-approved [PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91) code-only squash merge to `site-prod@68629fda`; five file contents match 25/25 proven PR head, protected data/JSON unchanged, no Netlify deploy. **Scheduled updater still executes old `main` generator**; runtime transfer separately gated. Work B: 11 bodies missing, October **COVERAGE_INCOMPLETE ≥23**. No new casualty publication.

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
- **Operational WIP / historical reference / backfill:** unchanged. **Casualty code:** PR #91 merged `site-prod@68629fda` (parent `6704c483`), exact five source/proof files, no revision/JSON/frontend change or Netlify deployment. Scheduled `main` updater still uses prior code; **not yet operationally active**. [Work B PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88) has 11 articles without full bodies; October ≥23 remains incomplete, publication NO-GO.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty next code gate: **do not assume site-prod code merge changed the scheduled updater**. The updater runs `main`'s distinct `update_casualties.py`; any independent `main` transfer requires a clean PR, fresh runtime/25/25 regression, and **separate owner approval**, scheduled-collector sequencing and push-trigger safety (push to `main` can automatically run the updater). Before any casualty revision, human-verify incident identity/prior credit and agree partial-month display; no October full-month total.
5. Casualty Work B: request owner authorization for **bounded source-body capture of up to 11 named candidate articles** from [PR #88 matrix](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88), or recover direct publisher/official archived texts offline first. Confirm real attack date, Zaporizhzhia city, civilian status, unique event and cumulative count; never infer complete October from RSS. Capture in isolated research only, separate proof, no production.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-DEDUP-CODE-SITEPROD-MERGED-01 — owner-approved code merge only (2026-11-12)

- [Clean PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91) squash-merged to `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa`, parent `6704c48306289bbc40b6e12da4fc8cac163ec428` retained for rollback. Compared parent→merge: **exactly five approved paths**, and all five blobs equal proven PR head `50446b24`. Earlier strict [CI #43204809570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570) **25/25 PASS**. `revisions.csv` and `dashboard_data.json` blobs unchanged; site-prod Netlify path filters not hit, no deployment. **`main` still runs old script**, so live scheduled casualty update has NOT adopted fix. Work B remains blocked on 11 original article bodies; October `COVERAGE_INCOMPLETE`; data publication NO-GO.

## CASUALTY-DEDUP-CLEAN-SITEPROD-25-01 — correct-base code readiness, no publication (2026-11-12)

- [Draft PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91) exact head `50446b24d33e0fdb4af0414b224c4aab6bbf5598`, base/merge-base `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22`, **5 intended files, +637/−3, zero others**. [Actions #43204809570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570) exact-head STRICT **25/25 PASS**, 0 FAIL, offline; [artifact #13936737623](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570/artifacts/13936737623) ZIP SHA256 `35da0f733505c4ae3227051e3c2a52ac100220fb5aad913f4d813cf46354a210` independently checked; inner checksums 5/5 and 14 input SHA entries. Duplicates/ambiguous corrections fail closed; frozen Sumy +1 and rollback PASS. **CLEAN_PR_READY** is code review readiness only, **no merge/production change**; Work B source completeness separately blocked.

## CASUALTY-SAME-INCIDENT-DEDUP-25-01 — read-only exact-head research PASS (2026-11-12)

- [Draft PR #89](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/89) exact `d406875cd5ccbd382fc736fcbb9a3cdc3a448289`, [Actions #43201016241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43201016241) SUCCESS **25 domain PASS, 0 FAIL**, independently downloaded artifact `13936055275` SHA256 `4a7aefc61f4d47683b72d0b33ec81deb57104eff6933873a2b2923d2ada4179f`. Frozen `site-prod@fc726166`; explicit incident identity, cumulative/delta classification and evidence-backed prior credit fix 18→23 to +5, 23→23 +0, 18→20→23 total 23. Reject ambiguous records; preserve pinned Sumy+1, other cities, October row and rollback. Proof handles require human review. **Research PASS only**: PR's `main` comparison contains 166 changed files (vs five actual research files from frozen production); do not merge. Work B source evidence and October completeness still NO-GO.

## CASUALTY-ZAPORIZHZHIA-ADDITIONAL-EVENTS-WORKB-01 — source evidence unavailable (2026-11-12)

- [PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88) final `34bc539d`: 11 WIP candidates / 5 priority Sep–Oct Zaporizhzhia groups, all `BLOCKED_MISSING_SOURCE` (no original publisher body). Retained earlier captures do not match target IDs. **0 additional deaths established by this review** is NOT a finding of zero actual deaths. October remains **≥23 minimum / COVERAGE_INCOMPLETE**. No new HTTP, CI or source ZIP verification claimed; production and WIP unchanged.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
