# Project State — current coordination snapshot

**Date:** 2026-11-10. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest C6 accepted: **C6-EXPORT-DIAGNOSTIC-STAGED-01** (bundle BLOCKED; no cutover).
Latest casualty accepted: **CASUALTY-WIP-GNEWS-BLOCKED-01** (research; publish OFF).

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git/JSON remains; first enabled run #42817288652 PASS, `site-prod@15a3f15b` published. Bundle export BLOCKED (nonfatal); main PR #54 changes diagnostics only. No Neon switch.
- **Neon reader / historical parity:** frozen 23-city [proof 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03), 0 unexplained diffs; no current full continuity PASS.
- **Live writer / provenance:** first enabled writer PASS, 23/23 source checkpoint bootstrap saved. Prior crash/retry and Kyiv two-capture proofs were bounded; cross-cycle 23-city source continuity remains OPEN.
- **23-city generator / publication:** frozen Neon→JSON [run 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) PASS (research only). Run #42817288652 wrote 23/23 bootstrap metadata, but 0/23 cross-cycle full receipts verified and no same-run bundle; no permission to switch.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** frozen browser/CSV/rollback [proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) research-only; operational cutover and rollback gates OPEN.
- **Operational WIP / historical reference / backfill:** unchanged and separate.
- **Casualty:** [WIP #42893729621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42893729621) blocked by Google News RSS wrappers: 20/20 unresolved, 0 evidence. Next: offline URL fix, then owner-approved HTTP retest.

## Concrete next tasks

1. Inspect next **scheduled** C2 run (no manual dispatch): check 23-city checkpoint overlap, writer/QA/Git JSON, and sanitized exporter `reason=... error_type=...` if bundle still BLOCKED. A workflow SUCCESS is not bundle PASS.
2. Diagnose and fix only a verified failing guard via reviewable PR and narrow tests; preserve fail-closed, raw response isolation and missing-continuity BLOCKED.
3. Exact-SHA PR #48 read-only same-run proof (36h) and DST raw baseline require separate approval. Rollback flags OFF; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`; other tracks separate.
4. Casualty: fix Google News RSS URL resolution offline; separate approval before more HTTP. Publish OFF.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
### CASUALTY-WIP-GNEWS-BLOCKED-01 (2026-11-10)

- [WIP CI #42893729621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42893729621): 1,656 queued, 20 RSS URLs/13 cities, 40 HTTP, 0 resolved pages or proposals; replay +0, input hashes unchanged. PR #58 unmerged. Earlier direct-publisher proof [#42873836462](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42873836462) 81/81 PASS, excerpt proof [#42863730878](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42863730878) 70/70 PASS. Next: offline URL fix; fresh HTTP requires approval. No production/publish.

## C6-EXPORT-DIAGNOSTIC-STAGED-01 — blocked export diagnostics merged (2026-11-10)

- [Run 42817288652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42817288652): first enabled scheduled C2 writer/QA/JSON PASS (`site-prod@15a3f15b`) and 23/23 bootstrap metadata, but bundle `C2_BUNDLE_BLOCKED`, no artifact; full overlap unproven.
- Owner-approved [PR #54](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/54) merged at `main@ee96fa78`: allowlisted exporter diagnostic + 4 tests, [offline run 42829359694](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42829359694) 4/4 PASS. Next regular run to identify safe reason; no manual dispatch or source switch. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-CAPTURE-EXPORT-OPTINS-ON-01 — approved flags ON; bootstrap pending (2026-11-10)

- Owner separately approved `C2_HISTORY_CAPTURE_ENABLED=true` and `C2_SHADOW_BUNDLE_EXPORT_ENABLED=true`. Isolated [Actions #42792678131](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42792678131) SUCCESS at research `c12b2eb7`: both actual GitHub repository variables evaluated `true`; no manual production workflow dispatch.
- Post-merge [updater #42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341) SUCCESS before activation, with canonical writer/23-city QA/Git JSON PASS and bundle export SKIPPED. First activated regular capture **PENDING**; independent full receipts remain unproven. PR #48 draft; `publication_allowed=false; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-GATED-RECEIPTS-STAGED-01 — gated hooks staged OFF; narrow CI PASS (2026-11-10)

- Owner-approved [PR #47](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/47) → `site-prod@cc8bcbe5`; then [PR #46](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/46) → `main@2fbe9d19` (squash). Exact-head [Actions 42686471326](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42686471326) **32/32 offline PASS**; [preflight 42774215008](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774215008) verified both opt-ins OFF. PR #48 remains research draft, DST OFF; no manual Neon proof, source switch or activation.
- Workflow merge triggered updater **42774323341** (verify result). Full physical receipts **0/23**. Next: clean updater verification, separate owner approval for flags, regular bootstrap/overlap, exact same-run read-only proof. Rollback flags OFF / revert. `GLOBAL_CUTOVER=NO`.

## C6-UA-CURRENT-ONEGET-01 — data API access PASS; current semantics OPEN (2026-10-31)

- Owner authorized **one** isolated UkraineAlarm `GET /api/v3/alerts`. [Actions 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954) SUCCESS on workflow `baa18a038f466c6ddb1759bf450d57a1db38b376`; [research proof `d6a6340f`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/d6a6340f8941799d873f02a9bce27881bce81a01); encrypted artifact **13049271828**, all **5** manifest hashes verified. No Swagger/history/regions, redirects or retries.
- HTTP 200, capture `2026-10-31T16:20:05.370939Z`; 35,302 bytes, **72** unique region entries. Of 21 mapped IDs, **9** direct AIR objects; **12** absent = UNKNOWN, not all-clear. Parent propagation, negative-status meaning, full current AIR status and source-cache currency **NOT PROVEN**. Full body AES-256-GCM encrypted using existing token-derived key; no key/token/plaintext in Git. Zero Neon/production/site-prod/Netlify writes. **C6/C3 PARTIAL; GLOBAL_CUTOVER NO.**

## C6-23CITY-CONTINUITY-02 — Kyiv two-cycle bounded PASS; 23-city continuity BLOCKED (2026-10-31)

- Owner-authorized 60-GET / 70-minute ceiling; existing child only. Execution `f20069ef`, [Actions 41208139352](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41208139352) SUCCESS. **5 upstream GET attempts** (4 source / 1 documentation), plus 1 GitHub Environment metadata GET; **27m31.18s**. Protected Environment/child identity passed. No retry/redirect or recurring scheduler.
- Physical Kyiv HTTP 200 twice → original C2/C3 writer → independent READ ONLY UUID/source/checkpoint/run readback; same UUID pair, seq **2 → 3 → 4**, zero exact duplicates. Both post-poll 23-city candidates generated (31,977 AIR parents / 145 observations; 4 JSON + 2 pinned Git auxiliaries each). Bounded observation PASS for **Kyiv only (1/23)**; full current source currency and active status **0/23**.
- UkraineAlarm **Swagger** returned 403; provider stopped before all 21 regionHistory/active calls. Their data API availability is NOT PROVEN. Sevastopol first page: 0 AIR pairs / checkpoint 1; second GET ReadTimeout. **PUBLICATION_BLOCKED**, fail-closed on actual missing sources, no publish/fallback. DST/Kyiv release dependencies remain separate; C6/C3 PARTIAL; GLOBAL_CUTOVER NO. No production/parent/site-prod/WIP/Netlify/writer/repair/backfill/casualty changes.
- [Closeout f5bbd5a4](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/f5bbd5a4d51fea66283cb4202d1bcf8dacb11939/research/neon_23city_continuity_2026_10_31/ACCEPTANCE.md). Artifact **13046430297**, ZIP SHA-256 `808dbfed16200857f0e099642a5258397eec2573c6b827e49c6de03ce18b65f3`; all **85** hashes independently verified, Git verdict bytes matched. Full archive saved at `9704d5fa`, [preservation Actions 41210485947](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41210485947) SUCCESS. Independent reconstruction matched archive SHA-256 and Git blob. Failed 403 body was hashed but not retained; only its logged digest is available. Full evidence details remain in the research closeout.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
