# Project State — current coordination snapshot

**Date:** 2026-11-13. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-WORKK-THREE-SOURCE-RUNNER-OFFLINE-PASS-01**. [PR #122](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/122) `69e7d023`, [Actions #43439055939](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939) SUCCESS 59+10 offline; source-specific Work J cards now in three-source runner. Live T03–T05 text/incident/prior credits still UNPROVEN. **HTTP NOT_AUTHORIZED, casualty publication OFF.**

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
5. Casualty next: before T03/T04/T05 live capture, separately authorize max 6 GET incl redirects, ≤24h, one run, and implement safe reviewed single-use execution (currently absent). Verify 2→3 cumulative counts, official event link and previous credit after capture; no auto-PROMOTE or publication.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKK-THREE-SOURCE-RUNNER-OFFLINE-PASS-01 — evidence runner offline PASS (2026-11-13)

- [PR #122](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/122) `69e7d023`, [CI #43439055939](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939) 59+10 PASS, [ZIP #14044811680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939/artifacts/14044811680) SHA256 independently MATCH `369c98cce533fe7e4fac0032d9f80b48b0c03cd86da578bce8f6bac2cfcbc766`. Three mock cards and hash manifest verified; real +23 regression PASS. No new HTTP or launch authorization; real 2→3 claim and official match still NEEDS_REVIEW.

## CASUALTY-PARSER-DIAGNOSTIC-WORKJ-OFFLINE-01 — offline parser diagnostics / bounded audit cards PASS, live texts unavailable (2026-11-13)

- [PR #121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/121) HEAD `a92e2ddb42060a77be966135c7fc0db9cca71c54`, [Actions #43433677112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43433677112) exact SUCCESS, 45/45 E/G/I/J + 10/10 inherited E, no publisher GET. [ZIP #14040641691](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43433677112/artifacts/14040641691) independently SHA256 MATCH `1d47ae01cb9395bc6c2de89ed55133eff8f0ec9c843b4712945e153c285aa595`. Work J records rejection reasons, fixes guarded count wording, adds short factual cards; retained original Zaporizhzhia +23 PASS. Pilot #118's ten bodies were NOT kept: their parser reasons remain unknown; PR #118 runner does not yet call minimal cards. 3-URL T03/T04/T05 recapture only after new consent; publication NO.

## CASUALTY-ONE-TIME-SOURCE-TRANSPORT-PASS-FACT-EXTRACTION-BLOCKED-01 — owner-approved one-shot HTTP transport PASS; zero fact extraction (2026-11-13)

- [PR #118](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/118) live launch `fbc721e79c3cec16bd584431dbcd6d9b18b6163f`, [Actions #43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) SUCCESS: ten approved exact URLs T01–T10 returned HTTP 200, 10/20 GET budget, 0 redirects/retries, 36/36 pre-request safety tests. [Artifact #14027391709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445/artifacts/14027391709) ZIP independently SHA256 MATCH `d43e81484c043d45a9ebee7435f041207303060590fb5ba0687bbaa1d9205bf3`, manifest hashes match. Six publisher originals -> seven in-memory candidate bindings, four police originals. **0 Work E/A structured reports; no article bodies or factual excerpts persisted.** 0 credited deaths, no production/WIP/C2/Neon. HTTP permission spent; no repeated GET without new owner approval. `COVERAGE_INCOMPLETE` still applies.

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
