# Project State — current coordination snapshot

**Date:** 2026-11-13. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01**. [Work R PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) exact `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`; [Actions #43573408615](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615) attempt 1 SUCCESS, 153 PASS/0 FAIL/1 SKIP; ZIP #14104883690 SHA256 and 11/11 hashes independently MATCH. T03/T04/T05 age overlaps suggest same attack, all pair identities INSUFFICIENT_EVIDENCE. SOURCE_REVIEW_REQUIRED; 0 source GET/credits.

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
5. Casualty next: Work R staged bounded, privacy-screened attack-context capture for T03/T04/T05. Owner HTTP approval **NOT GIVEN**. If owner consents to exact prelaunch `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, permit one launch only, ≤3 initial/≤6 total GET, 0 approved redirects, ≥1s, ≤1MB, 15s, 0 retry, ≤24h. No automatic incident match, 2+1 tally, casualty credit, merge/PROMOTE or production publication. Missing date/time/place/target require human evidence review.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 — source identity research PASS offline, full event link pending (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, [CI #43573408615](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615) exact SUCCESS 153 PASS/0 FAIL/1 SKIP, physical 18→20→23 PASS, 5 source-empty clusters BLOCKED. [Artifact #14104883690](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615/artifacts/14104883690) independent ZIP SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, 11/11 manifest PASS. T03 couple 37/38; T04 additional deceased age 69; T05 police 37/38/69: corroborating ages, no independently verified shared attack date/place/object. All 3 pairs INSUFFICIENT_EVIDENCE, SOURCE_REVIEW_REQUIRED. Existing one-shot runner added bounded deidentified review clues (≤8 snippets/source, ≤170 chars/each; total ≤650 chars and 25% body). 0 GET, 0 credits/PROMOTE/deploy. Fresh owner grant required for future source verification; no launch.json or authorization ID.

## CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 — Work Q local parser + CI PASS; incident totals PARTIAL (2026-11-14)

- [Draft PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135) exact `858e255ebea543383a9ca95d07847a40e22742e6`, [CI #43571952329](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329): 145 PASS/0 FAIL/1 SKIP, 18→20→23 PASS, 5 source-empty clusters blocked. [Artifact #14104761484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329/artifacts/14104761484) ZIP SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5` independently MATCH; 10/10 manifest hashes PASS. T03 «двоє»→local 2; T04 additional death ≠ total, 69 age; T05 3 unbound; no automatic 2→3 or credits. Work O auxiliary CI launch.json-only push guard corrected offline, live guards unchanged; 0 source GET, no production/PROMOTE. Full-article T03/T04 totals UNKNOWN (**PARTIAL**).

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
