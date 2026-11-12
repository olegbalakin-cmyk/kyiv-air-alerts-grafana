# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
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

### C3-NEON-GIT-KPI-CONSUMER-OFFLINE-01 — gated Neon Git KPI consumer offline PASS (2026-11-12; proposed)

- [PR #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100) `19446ba9`, exact-head [#43287759219](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43287759219) SUCCESS, artifact #13974983364 SHA-256 `f7a5f7d9b188ca92858ead9f83f232c668533a4800499a017b2b3234bded8a0e`; 4 C3-only files. Dashboard release authority, 23-city/manifest/generation and static fallback guards; short regression PASS. Full 184/184 prior head only. Code ready offline; publication/Netlify/rollback OPEN; NO-GO.

### C6-NEW-C2-SQL-EPISODE-PARITY-23-PASS-01 — new C2 Neon SQL episodes PASS; six JSON pending (2026-11-12; proposed)

- [PR #103](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/103) `f6499f46`, exact-head [#43286177828](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43286177828) SUCCESS, artifact #13975755100 SHA-256 `48d2bf55d2bbb486b5e52f13cc0c0d732c6c2ff87370f329188d20275ec2f80b`. Neon SQL 33,267/33,267, 23/23, 0 diffs, 262 previous versions; CI validates pinned witness offline. Physical JSON still BLOCKED. GO=NO.

### C3-C6-MINIMAL-CUTOVER-RELEASE-GAPS-01 — Work B verified narrow cutover gaps, NO-GO (2026-11-12; proposed on merge)

- [Release plan comment #6832977884](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/78#issuecomment-6832977884): PR #100 `b04e23a7` preview-only Neon predicate; current Netlify workflow rebuilds Git KPI; PR #95 only local candidate and #94 gate OFF. C2 #43262387718 23/23 PASS. Await Work A parity; prepare gated frontend/static consumer, existing one-publisher path and tested fresh two-channel Git-only recovery. `CUTOVER_PREPARATION_READY=NO; ROLLBACK_OPERATIONAL_READY=NO`. No production action.

### C6-POSTPR93-REGULAR-C2-CONTINUITY-23-01 — regular post-PR93 C2 source checkpoints 23/23 PASS (2026-11-12; proposed on merge)

- [Scheduled Actions #43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718) SUCCESS: 23/23 persisted receipts including Sevastopol with same run/attempt; Neon 33,267 episodes (+57, 0 updated), Git `site-prod@d0a7d22d` published. Bundle ZIP SHA `927343c620c1d55438823ad9203a16e986f540a816b35790d496200fe861944f`, manifest SHA `5c3e2326eeb98ae6e90234183764525483e64fbc6a203b20dda8deb685d9b501`, artifact #13967335571. New-run independent Neon→JSON readback and C3 rollback still OPEN; no cutover/DST.

### C3-STATIC-KPI-GENERATION-GUARD-OFFLINE-01 — PR #100 static KPI timestamp guard offline PASS (2026-11-12; proposed on merge)

- [Draft #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100) `b04e23a7`; [exact-head #43278423559](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43278423559) SUCCESS, artifact #13971078119 (GitHub SHA-256 `294d0820b493850dcdd49f3501263987a9277be1524dcf43abab0b12ef390181`). Static KPI fallback now rejects missing/stale generation in offline tests; 184/184 charts, CSV 23, Git rollback preview 23. Code unmerged, original site-prod base predates new data-only C2; no deployment, rollback readiness or publication grant.

<!-- coordination:history:end -->
