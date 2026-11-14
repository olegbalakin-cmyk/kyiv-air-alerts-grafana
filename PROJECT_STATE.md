# Project State — current coordination snapshot

**Date:** 2026-11-14. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01**: PR #141 CI #43589692637 PASS (offline). No real PROMOTE.

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
- **Operational WIP / casualty:** Work V/W/X offline PASS. Live verification and credits blocked.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty H/I: PRs #114/#115 PASS offline, no release.
5. Casualty next: owner-controlled Work W code transfer (PROMOTE OFF); independent incident/credit proof required before live updates.
6. Separately verify actual Netlify frontend asset and its GitHub Raw JSON fetch read-only; until then live casualty parity is UNVERIFIED.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01 (2026-11-14)

- [PR #141](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/141) `4e083db7` / CI #43589692637 PASS. Protected write OFF; research only, zero production changes.

## CASUALTY-WORKX-INDEPENDENT-SCAN-EVIDENCE-OFFLINE-PASS-01 — offline PASS (2026-11-14)

- [PR #142](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/142) `b07a5957`, Actions #43589727392 169 PASS/1 SKIP, artifact #14111089895 (SHA in CHANGELOG). 23-city independent RSS plan and retained cards tested; 3/3 T03–T05 NEEDS_REVIEW. No live HTTP, credits, merge or deployment.

## CASUALTY-WORKV-REVIEWER-OPERATOR-OFFLINE-E2E-PASS-01 — physical offline chain PASS (2026-11-14)

- [PR #140](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/140) exact `663f3eeb`, [Actions #43587369075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43587369075) SUCCESS; artifact #14110980955 (uploader SHA in CHANGELOG; independent ZIP hash pending). Scratch reviewer/operator→generator 18→20→23 = 23, replay +0, unknown proofs BLOCKED, Sumy +1/22 cities unchanged. T03–T05 NEEDS_REVIEW; 0 live HTTP, PROMOTE or publication.

## CASUALTY-WORKTU-CONTRACT-AND-LIVE-JSON-GATES-01 — Work T code mismatch verified; Work U live parity unresolved (2026-11-14)

- Exact Git blobs: `main@413d34ac` reviewer `cf65d85c`, operator `740b985b`, workflow `3771a501`; `site-prod@2fa9044a` generator `f5840c20`. The reviewer does not emit generator's incident/proof fields; operator preview calculates a raw delta sum, not the cumulative effective credit. PR #105 [shadow Actions #43290975899](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290975899) SUCCESS does not prove scheduled operation. No new code deployed.
- Work U: Zaporizhzhia Git JSON compared against PR #139, 316 deaths, September last validated month, October absent. Current Netlify deploy `6af76b2d` is READY/locked, but the actual served frontend/data fetch was not captured; `LIVE_PARITY=UNVERIFIED`. Live site may fetch GitHub Raw directly; do not equate locked deploy with frozen JSON. T03–T05 remains blocked, death credits 0.

## CASUALTY-WORKR-OWNER-ONE-SHOT-HTTP200-CONTEXT-CAPTURE-PASS-IDENTITY-REVIEW-01 — one physical Work R source capture PASS, event identity reviewer-only (2026-11-14)

- Owner-authorized one-shot [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) launch `b9d8d6183f882fbe5108f0641f80b16e3821d4a4`, exact prelaunch `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, launch.json-only diff; [Actions #43574791160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160) first-attempt SUCCESS, owner/ancestry and 68 safety checks PASS, 3/3 T03/T04/T05 HTTP200, 3 GET, 0 redirects/retries. [Artifact #14105343291](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160/artifacts/14105343291) ZIP SHA256 `8248b426baa23d822b0ba92332137ab59c63146b648b22271c41af7ff0a3177b` independently MATCH and 4/4 manifest hashes PASS, five JSON files only, full bodies absent. New bounded clues: T03 strike on Zaporizhzhia private house + local 2; T04 earlier 2 then count rose, later deceased aged 69; T05 evening missile near private sector and 3 dead aged 37/38/69. Supports same-incident 2→3 hypothesis but attack date/location identity NOT independently verified; article-wide T03/T04 totals NULL, T05 3 unbound. All NEEDS_REVIEW, 0 automatic links/credits, no PROMOTE/production publication. Authorization `CASUALTY-T03-T05-OWNER-20261114081321838-WORKR-ONCE` CONSUMED; next offline human review, no repeat GET.

## CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 — source identity research PASS offline, full event link pending (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, [CI #43573408615](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615) exact SUCCESS 153 PASS/0 FAIL/1 SKIP, physical 18→20→23 PASS, 5 source-empty clusters BLOCKED. [Artifact #14104883690](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615/artifacts/14104883690) independent ZIP SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, 11/11 manifest PASS. T03 couple 37/38; T04 additional deceased age 69; T05 police 37/38/69: corroborating ages, no independently verified shared attack date/place/object. All 3 pairs INSUFFICIENT_EVIDENCE, SOURCE_REVIEW_REQUIRED. Existing one-shot runner added bounded deidentified review clues (≤8 snippets/source, ≤170 chars/each; total ≤650 chars and 25% body). 0 GET, 0 credits/PROMOTE/deploy. Fresh owner grant required for future source verification; no launch.json or authorization ID.

## CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 — Work Q local parser + CI PASS; incident totals PARTIAL (2026-11-14)

- [Draft PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135) exact `858e255ebea543383a9ca95d07847a40e22742e6`, [CI #43571952329](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329): 145 PASS/0 FAIL/1 SKIP, 18→20→23 PASS, 5 source-empty clusters blocked. [Artifact #14104761484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329/artifacts/14104761484) ZIP SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5` independently MATCH; 10/10 manifest hashes PASS. T03 «двоє»→local 2; T04 additional death ≠ total, 69 age; T05 3 unbound; no automatic 2→3 or credits. Work O auxiliary CI launch.json-only push guard corrected offline, live guards unchanged; 0 source GET, no production/PROMOTE. Full-article T03/T04 totals UNKNOWN (**PARTIAL**).

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
