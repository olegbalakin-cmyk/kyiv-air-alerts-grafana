# Project State — current coordination snapshot

**Date:** 2026-11-08. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted technical checkpoint: **C6-PHYSICAL-SHADOW-JSON-01** — physical read-only Neon → frontend JSON PASS (23 cities, 4+2 files). This is not current-source certification or production cutover.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git/JSON publication remains unchanged. No Neon-backed production deployment; source switch and operational rollback require separate approval.
- **Neon reader / C6 physical shadow:** [Actions 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) SUCCESS, research `38539e51`, artifact **13619973574**. Physical read-only Neon snapshot: 32,918 AIR rows, 32,457 C2 corpus episodes; 4 generated JSON + 2 pinned auxiliaries, all 23 cities, 14/14 artifact hashes verified. No HTTP, writes or publication. **Frontend JSON generation PASS, source currency NOT certified.**
- **Live writer / source provenance:** Previous bounded two-capture Kyiv identity proof remains accepted, not full 23-city continuing ingestion. All **23/23** publication gates in physical shadow are BLOCKED for unproven source currency/continuity/active status. An absent current API record is UNKNOWN, not proof of no alert; `lastUpdate` is not episode start.
- **Historical parity:** [Frozen 23-city parity](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03) previously accepted (1,354 explained differences); it is not live source freshness certification.
- **DST / Kyiv:** Three erroneous merges and one missing alert across Kharkiv, Poltava, Zhytomyr and Cherkasy require bounded physical correction. Frozen Kyiv 382 parents → 198 displayed; nine later Git intervals not in frozen B2, ambiguous classifications cannot be rebound automatically.
- **Preview / C3:** [Frozen 23-city preview/rollback proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) accepted; actual production source switch and operational rollback OPEN.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; unchanged by this read-only research checkpoint.

## Concrete next tasks

1. Keep the minimal release contract: historical site outputs, correct intervals, bounded freshness and working recurring ingestion; no new live-status feature. Do not repeat C2 export, offline parity, PG17, browser, CSV or physical shadow proofs.
2. Resolve four DST cases and Kyiv current display membership with narrow physical evidence/repair or explicit nonpublication of incorrect intervals. Keep historical, persistence and casualty tracks separate.
3. Rehearse one production-like JSON source switch and operational rollback, then seek a distinct owner GO/NO-GO for production. **GLOBAL_CUTOVER=NO** meanwhile.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-PHYSICAL-SHADOW-JSON-01 — read-only Neon → JSON physical PASS; production BLOCKED (2026-11-08)

- [Actions 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) SUCCESS at research `38539e51e1ebdd3143d50d627f8f147f76a23821`, artifact **13619973574**, ZIP SHA-256 `b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e`. Independently verified 14/14 file hashes and six frontend outputs (4 Neon-generated + 2 Git auxiliaries) for 23 cities; 32,457 C2 episodes bound to a physical read-only Neon snapshot (32,918 AIR rows), all nine role-risk flags false. No HTTP, DB/production writes or publication.
- **PASS is bounded:** frontend-compatible historical JSON generation only. All 23 source publication gates BLOCKED; active/current freshness, four DST cases, Kyiv selection, recurring writer and operational rollback remain OPEN. **C6/C3 PARTIAL; GLOBAL_CUTOVER NO.**

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
