# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-C3-WORKK-54PASS-FINAL-WORKFLOW-NOGO-01 — Work K 54/54 offline PASS with workflow runtime NO-GO (2026-11-12; accepted)

- [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `d25f02f2`, [#43307825507](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43307825507) SUCCESS 54/54, artifact #13983708946 SHA `c44dfb4f552c2afbfafa751dcd79f150194dbbc7edfc5650d33bf5b9bb14b214`. Prepare-only uses undefined `FINAL_RUN_ID`; publisher does not download required `final-run.json`. Exact #43262387718 C2 bundle exists, same-run C6 preparation artifact absent. Work K2 narrow fix + future matching provenance needed. `RELEASE_CODE_INTEGRATION_READY=NO; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO`.

### C3-G2-WORKI2-NETLIFY-ALIAS-PHYSICAL-PASS-01 — physical Git-only Netlify alias PASS (2026-11-12; accepted)

- Owner-approved [Actions #43306339282](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43306339282) SUCCESS at `382ea915`, [artifact #13984106982](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43306339282/artifacts/13984106982) verified ZIP SHA `106673981e7233bcfc44522f0843227a1ee3a7efa1ea501e2bb71ab11b0301b0`; Netlify alias `6af629b311d9632a220e652a` ready/branch-deploy. 13/13 HTTP 200, 12/13 file SHA exact (index RUM inserted; sole HTML diff not proven), 23/23 cities, 184/184 graphs, 23 CSV, Kyiv/casualty PASS, zero JS errors. Production `6adb629bc3ebc570117d82e1` and site-prod `d0a7d22d` unchanged. `NETLIFY_NONPROD_REDEPLOY_PROVEN=YES`; production authority/fresh no-loss rollback OPEN, `ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

### C3-C6-WORKJ-FINAL-RELEASE-PREFLIGHT-NOGO-01 — Work J confirms final artifact ordering and rollback NO-GO (2026-11-12; accepted)

- Proofs: physical #43299402658 23 cities/18 SHA/33,267 historical, #43302381173 PR95→104→100 12/12 offline, rollback #43297683167 32/32+8/8. PR #95 currently creates FINAL binding + six files only in Git-publishing job; #104 requires pre-existing pinned artifact for Netlify. Work K: one default-OFF prepare-only final artifact output, no release. PR #104/#100 merges may auto Netlify `--prod`; Netlify manual workflow absent on main. Pause C2/Netlify before merges and maintain sole writer afterward. Work I2 nonprod alias separately approved but unproven, fresh production rollback remains blocked. `RELEASE_CODE_INTEGRATION_READY=NO; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C3-FINAL-AUTHORIZED-KPI-PR104-EXACT-HEAD-12PASS-01 — PR #104 final authorized KPI contract exact-HEAD offline PASS (2026-11-12; accepted)

- [PR #104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/104) `ea71a0e2` exact [#43302381173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43302381173) SUCCESS: 12/12 cases and real pinned PR #95→#104→#100 fixture E2E, six final SHA, immutable original proof and byte-identical static KPI, fail-closed negatives. Four code-only paths, Git-only default unchanged, Neon release OFF. Physical historical six-JSON #43299402658 already PASS; no real authorized final artifact, Netlify deployment or Git publication. `FINAL_NEON_KPI_RELEASE_CONTRACT_CODE_READY=YES` offline; `ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-NEW-C2-NEON-SIX-JSON-PHYSICAL-READBACK-23-PASS-01 — current-C2 Neon physical six historical JSON PASS (2026-11-12; accepted)

- Owner [#43299402658](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658) SUCCESS exact SHA `9bb62afe`, [artifact #13980242828](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658/artifacts/13980242828) ZIP SHA-256 `bd67b7607a3b345bc28a18a21676752a8334b90264e25fedbaaf718bdc37b6cc`; 6/6 candidate SHA, 18/18 proof SHA, 23/23 historical receipts <=36h, 33,267 canonical episodes, matching dashboard/KPI generation. No writer/source HTTP/prod writes. **`NEW_C2_NEON_JSON_PARITY=PASS` historical only.** Research authority OFF, live current not certified, no cutover; PR #104 final KPI and operational rollback pending.

### C3-G2-ROLLBACK-OFFLINE-PACKAGE-32-8-PASS-01 — 32/32 Git-only rollback offline PASS, operational BLOCKED (2026-11-12; accepted)

- [PR #107](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/107) `581b1cff`, exact-head [#43297683167](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43297683167) SUCCESS, artifact #13980651600 GitHub SHA-256 `fa81604b686caa8302ebd1f2056a3980a291f7884f766e0d3d798cd79e8ca4d8`: 32 checks, 8 no-loss synthetic cases, 23/23, 5 Git JSON + 12 static + `data.json`; casualty tracked only by hashes. Inner package SHA `f3e2601c…fd63045`, manifest SHA `e62c6739…726378`. Requires owner-approved Netlify non-prod alias test and refreshed cutover-time rollback package; no real redeploy. `ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-PR93-GENERATOR-PREFLIGHT-OFFLINE-PASS-01 — PR93 exact generator fix offline PASS, new physical run pending (2026-11-12; proposed)

- Research [`9bb62afe`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/9bb62afe088c18ec4bb36f5213319acfd982063c), exact-head [Actions #43297121030](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43297121030) SUCCESS: only allowlist merged PR93 Sevastopol parser blob `d31c5ac4`, six negative/positive tests; physical workflow unchanged. Earlier #43293835094 failed before six JSON. **Generator offline ready; current-C2 Neon six-JSON proof still BLOCKED** until new separately owner-approved read-only run for `9bb62afe`. No writer/HTTP/publication/cutover; `GLOBAL_CUTOVER=NO`.

### C3-C6-ROLLBACK-MINIMAL-GIT-ONLY-PLAN-OFFLINE-01 — selected minimal Git-only rollback; operational BLOCKED (2026-11-12; proposed)

- Work G reports 9/9 offline structural/no-loss tests on `site-prod@d0a7d22d`, no new PR/artifact; reproducible proof still open. Oct 23 Netlify deployment `6adb629bc3ebc570117d82e1` is stale for current Git JSON, read-only Netlify API confirms current site but not CLI deploy rights. Recovery: pin **fresh compatible** frontend/static KPI + Git C2/casualty/aux; return Git-only by existing C2, redeploy matching Netlify package, avoid reset/force/reverting newer data. Authorize a non-production alias deploy only separately. `ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-PHYSICAL-PR93-BUILDER-DRIFT-WORKF-PARTIAL-01 — owner physical attempt PREPARE_GENERATOR FAIL, PR #95 release code partial (2026-11-12; proposed)

- [#43293835094](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293835094) FAIL, artifact #13978646521: `BUILDER_CODE_DRIFT:scripts/add_sevastopol_exact.py` (PR #93 parser pin), inputs/permissions/C2 download PASS, zero six JSON. No SQL parity failure. Existing PR #95 exact PR93 blob patch reusable; require separately approved new research SHA. [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `2064f38c`, exact-head [#43293275773](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293275773) offline PASS: default-OFF owner-gated Git publisher, final manifest; code NOT READY until PR #104 pins final authorized KPI, E2E offline PASS. Git/Netlify production unchanged, rollback BLOCKED, GO=NO.

### C6-C3-WORKD-STATIC-BINDING-PASS-PUBLISHER-BLOCKED-01 — Work D Netlify static OFF/PASS, Git publisher BLOCKED (2026-11-12; proposed)

- [PR #104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/104) `a18e2029`, [#43288071274](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43288071274) 6 offline tests PASS (no artifact). [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `e2ebbdcb`, [#43288267641](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43288267641) SUCCESS, artifact #13976546185 SHA-256 `2e2a18995ce265af9be788291c610a384de616f3ac810cfc2fc42cf9c1d5598c`. Publisher not wired, candidate authority OFF vs frontend required release grant; Netlify static code-ready only. Rollback and new-C2 physical JSON OPEN. No production actions.

<!-- coordination:history:end -->
