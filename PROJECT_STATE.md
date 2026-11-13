# Project State — current coordination snapshot

**Date:** 2026-11-13. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01** and **CASUALTY-STRICT-REDIRECT-WORKI-OFFLINE-01**. [H PR #114](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/114) current-site frontend integrated SHADOW PASS 42+32 Chromium; [I PR #115](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/115) exact redirect-path safety 36/36 offline PASS. Both proof ZIP hashes independently verified. Oct Zaporizhzhia **≥23 INCOMPLETE** remains only a research lower bound. **Publisher HTTP NOT_AUTHORIZED; casualty publication NO-GO.**

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
- **Operational WIP / historical reference / backfill:** separate. **Casualty:** Work C/D/E isolated PASS; F #112 integrated archived-source PASS; H #114 tested current site-prod frontend PASS; G #111 capture preflight PASS and I #115 strict redirects PASS (offline only). Regular WIP discovery and existing site-prod source unchanged; automatic capture and casualty publication OFF.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty Work H: PR #114 current site-prod frontend compatibility accepted in isolated browser (no merge/production). Work I PR #115 strict redirects accepted offline. Monitor exact site-prod baseline before future release.
5. Casualty next: owner must separately approve one-time exact PR #111 ten URL/seven host scope, ≤20 GET incl redirects and ≤24h, with PR #115 strict guard and manually reviewed research-only execution. No auto-PROMOTE/publication; September prior-credit and possible 5 Oct late death remain blocked.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01 — real current frontend browser PASS (2026-11-13)

- [PR #114](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/114) exact `46728a37d3fae3e6fd48663714a1dd7e6dfb7195`, [Actions #43397597547](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547) SUCCESS: Work F E/A/C scratch +23/replay 0 through Work D to real current site-prod `f0cfcbc8`, `≥23 INCOMPLETE` and original KPI/trend/alerts. 42/42 Work D +32/32 current Chromium, CSV/PNG/embed, 375px, Sumy +1 and 23 alert cities preserved, rollback PASS. [ZIP #14023123111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547/artifacts/14023123111) SHA256 independently MATCH `c68ea1bc107a2d1a427ac57a7a086fc724998fd093ae37b4058098ddef753cc9`; final proof manifest SHA256 `ad207c6f74cf8ad70d7b711260ecb1050e9600a5eada54d73587ea555ca68b42`. Shadow only; no production changes or publication.

## CASUALTY-STRICT-REDIRECT-WORKI-OFFLINE-01 — exact-URL redirect guard PASS (2026-11-13)

- [PR #115](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/115) exact `da49571a9e22e2e1e62a2842f902f984cbd0ab10`, [Actions #43397030680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680) SUCCESS 10/10 E +12/12 G+14/14 I; same-host new path blocked before second GET. [ZIP #14023795533](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680/artifacts/14023795533) SHA256 independently MATCH `e4780a0b3e19b8c4c45098751e5b36a58870b5b9f65fb6db9eb6f7057085c327`. Ten targets, seven hosts, max 20 requests; 0 external source HTTP, owner authorization NOT_GRANTED; no auto-credit, merge or production.

## CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01 — joined historical-source shadow PASS (2026-11-13)

- [PR #112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/112) `2274276`, [CI #43387209190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387209190) SUCCESS; E/A → scratch REVIEW/PROMOTE → generator +23/replay 0 → chart `≥23 INCOMPLETE`. Work C 11/11, D 42/42; Sumy +1 preserved. Proof ZIP #14018663260 SHA256 MATCH. Current frontend not browser-tested; no publication.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
