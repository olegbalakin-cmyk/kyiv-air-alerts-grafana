# Project State — current coordination snapshot

**Date:** 2026-11-12. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-ZAPORIZHZHIA-PLUS23-OFFLINE-PREVIEW-01** `PREVIEW_BLOCKED` (19 pass/3 duplicate-event fails) and **CASUALTY-ZAPORIZHZHIA-OCTOBER-COVERAGE-WORKB-01** `COVERAGE_INCOMPLETE` (≥23 minimum, not monthly final). **No publication**.

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
- **Operational WIP / historical reference / backfill:** unchanged. **Casualty:** [PR #86](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/86) preview confirms single +23 generates Oct row, rollback PASS, but event-level dedup **FAIL**; [PR #85](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/85) proves only **≥23** for October, with other unverified attacks. **Both release gates NO-GO; no full-month publication.**

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty Work A: scoped research-only fix for **same-incident duplicate prevention in confirmed revision overlay**. Exact 0/18/23 previously credited and cumulative 18→20→23 tests must pass with unchanged schema, fail-closed ambiguity, rollback and all independent city data intact. Reconcile current site-prod again before any release.
5. Casualty Work B: independently prioritize retained evidence for possible separate Zaporizhzhia city attacks (notably Oct 18, 22–23, 26; Sep 26–27). Do not infer complete October from WIP titles or 764 alert-check receipts; decide how to display **incomplete ≥23 minimum** outside normal full-month series. No new media HTTP or production writes without separate authorization.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-ZAPORIZHZHIA-PLUS23-OFFLINE-PREVIEW-01 — duplicate-event BLOCKED (2026-11-12)

- [Draft PR #86](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/86) HEAD `fb32184e`, exact [Actions #43195244991](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43195244991) runner SUCCESS but **domain 19 PASS / 3 FAIL**. Isolated +23 creates October row (316→339), frontend Node render/rollback PASS, frozen production files unchanged; **same incident with prior credit 18/23 re-adds +23; 18→20→23 separate confirmed rows become 61**. Event-canonical dedup correction required. Artifact `13931798566`, SHA256 `f5f7894b…d8237b0` verified; **PREVIEW_BLOCKED, no release**.

## CASUALTY-ZAPORIZHZHIA-OCTOBER-COVERAGE-WORKB-01 — incomplete monthly coverage (2026-11-12)

- [Draft PR #85](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/85) final `19fad288`, read-only inventory: WIP `c66c242a` contains **208** Zaporizhzhia-tagged candidates, **197** published Sep 19–Oct 31, all `needs_review`. Other suspected city attacks (Oct 18/22–23/26) lack independently checked publisher evidence. Original 10 Oct attack confirms **≥23**, but full October and Sep 19–30 coverage NOT proven; **COVERAGE_INCOMPLETE**. No new CI for this methodology report. Never display 23 as a complete monthly total.

## CASUALTY-ZAPORIZHZHIA-LEDGER-DELTA-23-01 — published series reconciled read-only (2026-11-12)

- [Exact-head CI #43185423680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43185423680) SUCCESS at research `3dbff8f3`. Frozen `site-prod@fc726166`: Zaporizhzhia city validated through **18 Sep 2026** (316 confirmed deaths; last monthly row Sep), no October row, **0** confirmed city revisions; only confirmed production revision is Sumy +1. Public Netlify `app.js` and served raw dashboard JSON byte-hash matched pinned Git. Thus **0 of 23** credited for 10 Oct Zaporizhzhia attack in verified published series; **+23 RECONCILED_DELTA_FOR_REVIEW**, never automatically apply. Artifact `13928441241` SHA256 `d0e1ba44…068c8` verified. 16 related WIP titles remain unconfirmed, not ledger entries. Future production snapshots need fresh reconciliation.

## CASUALTY-FALSE-ATTACK-PLACE-76-01 — real place guard PASS (2026-11-12)

- [PR #81](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/81) final `503bd73e`, [exact CI #43180557264](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180557264) **76/76 PASS**; artifact `13926406047` verified. Ivano warning now `place=unlocated`, military `NEEDS_REVIEW`; true places protected. Zaporizhzhia shadow total 23 still PASS, replay 0, SHA unchanged. **Research only, no release.** Full proof in CHANGELOG.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
