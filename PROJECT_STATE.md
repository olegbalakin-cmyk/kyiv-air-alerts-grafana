# Project State — coordination snapshot

**2026-11-12 NO-GO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.** Latest accepted: **C3-FINAL-AUTHORIZED-KPI-PR104-EXACT-HEAD-12PASS-01** — final KPI release contract offline PASS; production still Git-only.

Read main:PROJECT_STATE.md and CHANGELOG.md, then PR #78. Verify exact SHA/Actions/artifacts. Keep production, C2/C3, Neon, casualty, WIP/history/backfill and DST separate. Archives: [index](docs/coordination-archive/README.md). Offline test is not release approval.

## Gates

- **Production:** `site-prod@d0a7d22d` still Git-only; C2 #43262387718 23/23 receipts; Netlify current deployment `6adb629bc3ebc570117d82e1` unchanged.
- **Historical data:** PR #103 SQL 33,267/33,267, 23/23, 0 diffs; owner physical #43299402658 SUCCESS artifact #13980242828, 6/6 candidate hashes, 18/18 evidence SHA, no writes. **`NEW_C2_NEON_JSON_PARITY=PASS` historical only**, live current alerts not certified, research authority OFF.
- **Frontend:** PR #100 `19446ba9` guarded Git Neon KPI consumer offline READY, Draft/unmerged.
- **Release contract code:** PR #95 `2064f38c` owner-gated single Git publisher default OFF; PR #104 **`ea71a0e2`**, exact-head [Actions #43302381173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43302381173) 12/12 and PR #95→#104→#100 fixture E2E PASS. Four-file final-authorized KPI / immutable Work A proof binding; Git-only Netlify path unchanged, Neon mode OFF. **`FINAL_NEON_KPI_RELEASE_CONTRACT_CODE_READY=YES` offline**, but no separately owner-authorized final release artifact, no Git push/Netlify deployment/production GO.
- **Rollback:** PR #107 `581b1cff`, offline 32/32+8/8 PASS; **`ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO`** until separately owner-authorized non-prod Netlify alias deploy permission test and a fresh compatible cutover-time Git-only package preserving later C2/casualty/aux.
- **Separate:** Sevastopol `25006→25008`, `25100` unresolved. Casualty and DST distinct; DST OFF.

## Next

1. Verify Netlify CLI deploy authority using PR #107 *non-production alias* only after separate owner permission; alias may be accessible by URL, and does not by itself prove inactive prod restore.
2. Pre-release no-write checklist: exact PR #95/#100/#104 code-only merge order and prevent automatic Netlify deploy before owner GO; release final artifact and six SHA authorization, single writer lock, current compatible Git-only rollback snapshot.
3. Only then request distinct owner approvals for merges, controlled Netlify production deploy and atomic six-JSON Git publish. No repeated physical/SQL parity on same unchanged C2.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C3-FINAL-AUTHORIZED-KPI-PR104-EXACT-HEAD-12PASS-01 — authorized final KPI contract code offline PASS (2026-11-12)

- [Draft PR #104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/104) exact HEAD `ea71a0e2d2313ea86143500b4ef4ee25ab4c7cec`, [Actions #43302381173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43302381173) SUCCESS attempt 1, **12/12 tests**. Four paths only: existing Netlify production workflow and offline workflow, `scripts/c3_final_neon_kpi_contract.py`, corresponding tests. CI read-only checked pinned PR #95 `2064f38c` release binding and PR #100 `19446ba9` frontend predicate; fixture end-to-end final `RELEASE_BINDING.json`, `RELEASE_MANIFEST.json`, six final SHA, exact served KPI byte identity, original immutable Work A proof and source/C2 generation PASSED. Missing owner grant, incorrect final SHA, C2 attempt and generation fail closed. Research `publication_allowed=false`; Git-only Netlify path unchanged and Neon release default OFF.
- **`FINAL_NEON_KPI_RELEASE_CONTRACT_CODE_READY=YES` offline only.** Independent same-run six-JSON physical proof already PASS [#43299402658](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658) artifact #13980242828, not the prior failed #43293835094. No real owner-authorized final release artifact, production merge, deploy or publication. Rollback operational still NO; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-NEW-C2-NEON-SIX-JSON-PHYSICAL-READBACK-23-PASS-01 — new C2 physical Neon→six historical JSON PASS (2026-11-12)

- Owner [Actions #43299402658](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658) SUCCESS attempt 1 on research `9bb62afe088c18ec4bb36f5213319acfd982063c`, pinned C2 #43262387718 attempt 1. [Artifact #13980242828](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658/artifacts/13980242828), GitHub and independently downloaded ZIP SHA-256 `bd67b7607a3b345bc28a18a21676752a8334b90264e25fedbaaf718bdc37b6cc`. Independent SHA-256 checks: 6/6 candidate JSON, 18/18 evidence files vs manifest; `verdict.json` PASS, `PHYSICAL_GENERATION_PASS`, 23/23 historical receipts and freshness <=36h, 33,267 canonical episodes. Read-only Neon table 33,529 rows including 262 superseded; dashboard/index generation `2026-11-12T22:21:25.797295+02:00` same, embedded index identical to root, auxiliary hashes bound to pinned Git. `upstream_http_gets=0`, `neon_writes=0`, `production_file_writes=0`, `publication_allowed=false`.
- **`NEW_C2_NEON_JSON_PARITY=PASS`** historical, **not** live current alerts (`CURRENT_FRESHNESS_NOT_CERTIFIED`), not authorized to publish. PR #95/#104 final KPI contract and operational rollback still OPEN; production and DST unchanged.

## C3-G2-ROLLBACK-OFFLINE-PACKAGE-32-8-PASS-01 — immutable rollback offline PASS, operational NO-GO (2026-11-12)

- [Draft PR #107](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/107) HEAD `581b1cff4ccd3d25a5a96f3fac120c04f8a6255c`, exact-head [Actions #43297683167](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43297683167) SUCCESS attempt 1, [artifact #13980651600](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43297683167/artifacts/13980651600), GitHub SHA-256 `fa81604b686caa8302ebd1f2056a3980a291f7884f766e0d3d798cd79e8ca4d8`. CI verified **32/32 structural checks + 8/8 synthetic no-loss cases**; inner package SHA `f3e2601c5122f413bea8c70851a3006797e0eb8f95c689247d33d3674fd63045`, manifest SHA `e62c673940dbbba0a2d15c464be73eb03ccc39960b422f3857b9afb115726378`. Pinned `site-prod@d0a7d22d`, PR #100 `19446ba9`, PR #104 `a18e2029`, C2 #43262387718: 23/23 cities, generation `2026-11-12T18:47:43.912004+02:00`, 5 Git JSON, 12 static + `data.json`, hashes of 12 casualty tracked files (not bundled for rollback overwrite).
- [Runbook](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/581b1cff4ccd3d25a5a96f3fac120c04f8a6255c/research/c3_g2_git_only_rollback_2026_11_12/RUNBOOK.md): existing C2 Git-only recapture + matched Netlify CLI redeploy, no `git reset`, force or blind older C2/casualty/aux restore. **`ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO`** until fresh cutover-time package, independent operator deploy rights/non-prod alias test (only on separate authorization) and no-loss production recovery proof. No deploy occurred.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
