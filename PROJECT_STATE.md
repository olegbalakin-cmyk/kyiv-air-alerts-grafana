# Project State — current coordination snapshot

**Date:** 2026-11-10. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-CAPTURE-EXPORT-OPTINS-ON-01**. Both owner-approved flags are ON ([Actions 42792678131](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42792678131) PASS). Post-merge updater [42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341) PASS before activation; first activated scheduled source capture still PENDING. No cutover or DST.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** existing Git/JSON source; updater #42774323341 succeeded with C2 writer and publication, new `site-prod@1157c81b`. Capture/export flags are now ON but have not yet run. No production Neon source switch.
- **Neon reader / historical parity:** [frozen proof 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03): all 1,354 candidate differences explained (847 DST, 457 legacy, 49 timestamps, 1 marker), 0 unexplained. Bounded offline evidence only, not recurring freshness.
- **Live writer / provenance:** canonical writer PASS in updater #42774323341; previously accepted crash/retry and two-capture Kyiv UUID chain remain bounded (C6-LIVE-WRITER-PHYSICAL-03; C6-23CITY-CONTINUITY-02). New real source receipts and overlap for 23 cities not yet proven; source cache/active-state semantics OPEN.
- **23-city generator / publication:** Frozen generator and Kyiv continuity are bounded research proofs, not current 23-city freshness. [Actions 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) generated Neon→JSON for 23 cities, but physical full source-capture receipts remain **0/23** until bootstrap, overlap and exact same-run readback. No freshness PASS, silent Git fallback or source switch; current/active, DST and casualty gates remain separate.
- **UkraineAlarm current API (research-only):** [Actions 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954) SUCCESS: one HTTP 200 at `2026-10-31T16:20:05Z`, 35,302 bytes, 72 region rows; 9/21 mapped IDs directly have AIR, 12 absent (UNKNOWN). Encrypted full response in artifact 13049271828, metadata proof `d6a6340f`; no Neon writes. Ancestor/negative/cache status NOT PROVEN. Production history API passed 21/21 independently (run 41210446729).
- **DST / Kyiv:** four-case offline correction commit `14e1b0b9` passed 17 tests; rolling guard remains BLOCKED until new private full raw reader baseline. DST OFF, no physical repair/rebind; Kyiv provenance remains OPEN.
- **Preview / C3:** [frozen browser/CSV/rollback proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) and Actions #41139538902 are research-only, not a production source switch. Operational release and recurring freshness gates OPEN.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; no change or promotion is established by these research or documentation checkpoints. Consult the relevant pinned evidence through the archive index before acting on a track.

## Concrete next tasks

1. Await next scheduled C2 run (existing 4-hour cron, no manual dispatch). Confirm real Kyiv/UkraineAlarm/Sevastopol capture receipts, metadata-only checkpoints, exact same-run bundle SHA, C2 writer and Git JSON publication. First bootstrap cannot prove overlap.
2. Inspect following scheduled run for independent checkpoint overlap and 23/23 receipts; report any missing city BLOCKED, never synthesize freshness. #48 research read-only proof within 36h and private DST baseline each need separate authorization.
3. On regression turn both flags OFF; keep current Git JSON, `GLOBAL_CUTOVER=NO`, `DST_CORRECTION=OFF`; current active-state, backfill and casualty tracks separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
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
