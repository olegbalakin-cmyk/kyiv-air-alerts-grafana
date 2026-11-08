# Project State — current coordination snapshot

**Date:** 2026-11-08. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest verified research preparation: **C6-MINIMAL-PRECUTOVER-PREVIEW-01** (review pending). The physical proof is **C6-PHYSICAL-SHADOW-JSON-01**, independently checked below; PR #44 separately proposes its main acceptance and is untouched. Main at task start remains `0546986e`, whose last accepted technical checkpoint is C6-UA-CURRENT-ONEGET-01. No production cutover follows from these research results.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** existing Git/JSON site unchanged. Existing scheduled [run 42452793451](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42452793451) SUCCESS: C2 32,656 episodes / 34 inserted, independent receipt CONFIRMED, UkraineAlarm history continuity 21/21 through `2026-11-08T06:23:07.719975Z`. No run was started here. A new writer or scheduler is unnecessary.
- **Neon / physical generation:** [run 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608), research `38539e51`, artifact 13619973574: physical read-only Neon → four JSON + two auxiliaries / 23 cities PASS; 14/14 artifact hashes independently matched. C2 corpus 32,457 / physical AIR snapshot 32,918. This is not current-source certification.
- **Prepared source switch:** [implementation and bounded evidence](research/c6_minimal_precutover_2026_11_08/README.md). Isolated assembler defaults to Git; Neon is explicit opt-in. It uses existing proof bytes and production frontend, changes only the preview data base and frozen-data banner, preserves casualty/cause auxiliaries, rejects unsuitable inputs and restores the exact same-run Git outputs. No production mode or deployment. Manual workflow prepared, not dispatched/registered in main.
- **Historical freshness blocker:** existing writer persists same-run history but declares source provenance partial. The accepted generator intentionally has no certified per-city capture bindings. Reuse current captures/checkpoint metadata; bind them to the corpus/readback. Match the current site's 36h hard ceiling and historical continuity; full live-status/all-clear certification is not a release condition for this interface.
- **DST blocker:** three known wrong parent UUIDs still appear in the physical candidate lineage; the missing Cherkasy interval remains covered by accepted four-case evidence. Narrow UTC writer fix plus guarded four-case repair plan is prepared; no new physical check or write. See `04b0938d` and `7265e40a`. No new historical audit.
- **Kyiv:** all 2,819 displayed intervals match the physical proof's same-run Git set exactly (no extra/missing UTC intervals). Stage enforces equality and preserves cause JSON byte-for-byte. No classification rebind. The 28 unresolved suppressed-parent classifications can remain a separate post-cutover task under this contract; source freshness remains a separate requirement.
- **Preview / release:** new isolated source routing and byte-exact rollback checks pass. Prior frozen parity/browser/CSV/PG17/rollback proofs remain accepted and were not repeated. Production wiring/promotion and deployment-specific rollback remain separate gates. PRs #42/#44 unchanged.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; not modified. Existing casualty objects and auxiliaries are copied, not regenerated.

## Concrete next tasks

1. Owner: authorize a bounded **read-only** dependency/lineage preflight for the four known DST cases using the established reader. No new source HTTP, DML, credential or grant change is included.
2. Prepare the small historical capture-metadata binding on the existing same-run writer path, with activation separately authorized. No new poller, current-status feature or full historical audit.
3. After data blockers pass, review production JSON wiring and one controlled deployment-specific preview/rollback gate; obtain explicit owner GO before cutover. The static preview is already reproducible. **GLOBAL_CUTOVER=NO**.

## Latest research preparation and accepted history

<!-- coordination:history:start -->
## C6-MINIMAL-PRECUTOVER-PREVIEW-01 — static source switch prepared; release NO-GO (2026-11-08)

- Review-pending research closeout. Existing physical proof 42487688608 / artifact 13619973574 verified, not rerun. Existing production 42452793451 proves recurring C2 and 21-city bridge continuity; no new source/DB operations.
- Production frontend + retained 4+2 JSON staged in an isolated directory; Git default / explicit Neon; exact auxiliary/casualty/Kyiv membership checks, fail-closed input handling and new byte-exact source rollback tests PASS. Static-only banner/noindex; production wiring and deployment remain disabled. Details and tests: [research closeout](research/c6_minimal_precutover_2026_11_08/README.md).
- Real data blockers: four DST cases and historical source/corpus/readback binding. Kyiv same-run 2,819 interval membership matches; classification reassignment and live-status certification are outside this minimum site contract. C6/C3 PARTIAL; GLOBAL_CUTOVER NO. PRs #42/#44 untouched.

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
