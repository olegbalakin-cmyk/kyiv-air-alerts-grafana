# Project State — current coordination snapshot

**Date:** 2026-11-13. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-WORKN-T03T05-HTTP200-FACT-EXTRACTION-BLOCKED-01**. Owner-approved single capture PR #128 at `5e5628a8cd8215593630f2f375bf26e5dda14696`: [Actions #43510162714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714) SUCCESS, T03/T04/T05 3/3 HTTP200, 3/6 GET, 0 redirects, 3 NEEDS_REVIEW cards; publishers 0 parseable fatal totals, police count 3 unlinked, zero excerpts, 0 credits. ZIP #14076819100 SHA256 independently MATCH. **Grant consumed; publication OFF.**

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
5. Casualty next: investigate Work J HTML→clean-text→fatal-claim/excerpt rejection **offline** using retained receipts, code and synthetic fixtures; real source response bodies/excerpts not persisted so exact publisher rejection cannot yet be reproduced. Keep T03/T04/T05 NEEDS_REVIEW, no automatic credits. Any new source HTTP needs a fresh owner grant; do not reuse run #43510162714.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKN-T03T05-HTTP200-FACT-EXTRACTION-BLOCKED-01 — 3/3 physical source capture, fact parsing still blocked (2026-11-13)

- [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) launched once at `5e5628a8cd8215593630f2f375bf26e5dda14696`, [Actions #43510162714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714) SUCCESS, 68/68 safety, 3 HTTP200 / 3 GET, zero redirects. [Artifact #14076819100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714/artifacts/14076819100) ZIP independently SHA256 MATCH `dc7d1ba10d66e6b3e39f7f3a85fffbb7522e8930390117b139185e5eb6627da6`; 4 JSON hashes independently MATCH. T03/Ukrinform and T04/MIG returned claim_deaths=null, `NO_PARSEABLE_FATAL_TOTAL`; T05/police claim_deaths=3, no independently verified incident/date. 3 cards all NEEDS_REVIEW and 0 excerpts, 0 structured reports or credits, no publication/production change. Source bodies NOT persisted; exact real-text parser issue cannot be replayed offline. Owner authorization `CASUALTY-T03-T05-OWNER-20261113212231234-PR128-ONCE` CONSUMED. Diagnose offline; fresh approval required for new HTTP.

## CASUALTY-WORKN-LAUNCH-STATE-FIX-OFFLINE-PASS-01 — clean rearm and launch-present pre-HTTP proof PASS (2026-11-13)

- [PR #127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/127) `4ae85477`, [CI #43507349125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43507349125) 2 jobs/68 tests PASS, ZIP #14077111596 SHA256 `0fdb04a6168747a4de0a59445b9abed52fb19c32818a44e19145fbddae2df8b4` independently MATCH. Live 68-test suite required absence of owner launch.json; detected prior to HTTP, so #127 never launched. Isolated [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) exact `236d3d3af785ea89f44504995498bcd0915d2e10` [CI #43508802671](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43508802671) 2/2 PASS incl synthetic launch-present 68/68. ZIP #14076498074 SHA256 `2eb23ffc7fab82ee660f765becd147ca65609a24a1fc36f01a3b73d0ff3d5d84` independently MATCH; supplemental #14076383178 verified. Source GET 0, no production. Owner grant only covers #127, NOT #128; new explicit approval needed.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
