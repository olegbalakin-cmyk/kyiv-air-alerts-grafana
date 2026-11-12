# Project State — coordination snapshot

**2026-11-12 NO-GO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.** Latest: **C3-C6-ROLLBACK-MINIMAL-GIT-ONLY-PLAN-OFFLINE-01** (rollback procedure selected, operational BLOCKED).

Read main:PROJECT_STATE.md and CHANGELOG.md, then newer PR #78. Verify exact SHA/Actions/artifacts. Separate C2/C3 production, Neon, casualty, DST, WIP and historical/backfill. History: [archive index](docs/coordination-archive/README.md). No deployment inferred from offline evidence.

## Release gates

- **Production:** current `site-prod@d0a7d22d` Git-only, regular C2 #43262387718 SUCCESS with 23/23 receipts, Netlify current deployment `6adb629bc3ebc570117d82e1` (2026-10-23) unchanged.
- **Neon:** PR #103: 33,267/33,267 SQL parity, 23/23, zero diffs, 262 superseded retained. Physical read-only #43293835094 FAILED *before JSON generation* at exact PR93 Sevastopol parser blob drift; repair with existing PR #95 pin and new owner SHA grant, no automatic rerun.
- **Frontend:** PR #100 `19446ba9` consumer release guard offline PASS; unmerged.
- **Publisher:** PR #95 `2064f38c`, exact-head #43293275773 offline PASS, owner-gated single C2/Git publisher default OFF. **`NEON_PUBLICATION_CODE_READY=NO`** until PR #104 final KPI SHA contract/E2E tests.
- **Netlify:** PR #104 `a18e2029`, offline base-mode PASS; currently accepts research KPI, not final authorized release SHA. No deploy.
- **Rollback:** **`ROLLBACK_OPERATIONAL_READY=NO`**. Work G selected shortest Git-only recovery: pin fresh 12-file compatible frontend+static package and current C2 Git JSON/casualty/aux, then reproduce normal Git-only C2 + compatible Netlify redeploy. Work G reports 9/9 offline snapshot invariants; no immutable new proof artifact, non-production Netlify CLI deploy authority and no-loss post-snapshot recovery not yet proven. Historic Oct 23 Netlify package cannot serve as rollback. Never rewind whole `site-prod`.
- **Separate:** Sevastopol old `25006→25008`, open `25100`, casualty and DST tracks remain separate; DST OFF.

## Next

1. Exact PR93 parser allowlist fix → separate owner approval for new physical six-JSON run on C2 #43262387718.
2. PR #104 final authorized six-file KPI binding aligned to PR #95/#100; scoped offline end-to-end test.
3. Work G: pin compatible fresh Git-only package with SHA, prove no-loss preservation on simulated newer data and read-only Netlify access; non-production alias deployment ONLY after separate owner authorization. Then release-order/recovery decision and separate merge/deploy/cutover GO.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C3-C6-ROLLBACK-MINIMAL-GIT-ONLY-PLAN-OFFLINE-01 — minimal Git-only two-plane rollback selected; operational NO-GO (2026-11-12)

- Work G read-only report (no new PR/Actions artifact) selects **fresh compatible Git-only C2 runtime JSON + frontend/static Netlify package**, not stale deployment `6adb629bc3ebc570117d82e1` (published 2026-10-23). Existing [PR #101](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/101) confirms previous offline guards but not production rollback. Worker reports 9/9 offline structural/no-loss assertions on `site-prod@d0a7d22d`: 23 cities, dashboard/index generation, Kyiv 2,857 intervals, rejection of stale restore when new C2/casualty/aux appear. **9/9 is a worker-reported result, not an independently reproduced immutable proof.**
- Independently checked Netlify project `ukraine-air-alerts`: current deploy `6adb629bc3ebc570117d82e1` ready, published Oct 23; API read access does NOT prove Netlify CLI write/deploy authority. **`ROLLBACK_OPERATIONAL_READY=NO`** until immutable compatible cutover-time package and non-production alias deploy rights/path proven with separate owner authorization. Use existing Netlify/Git-only C2; no full `site-prod` reset, no older casualty/aux overwrite, no new rollback architecture. No production action.

## C6-PHYSICAL-PR93-BUILDER-DRIFT-WORKF-PARTIAL-01 — physical owner run blocked before JSON; Work F partial offline PASS (2026-11-12)

- Owner [C6 physical Actions #43293835094](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293835094) at research `82a7cc775ed2f2a6fd0134440db709690f0c04d1`, attempt 1, FAILED. Approved environment, pinned 40-hex SHA, C2 identity, checkouts, dependencies and exact artifact #13967335571 download PASS. [Fail-closed artifact #13978646521](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293835094/artifacts/13978646521) has `verdict.json: error_stage=PREPARE_GENERATOR; reason=BLOCKED_GENERATOR_INPUT:BLOCKED_GENERATOR_INPUT:BUILDER_CODE_DRIFT:scripts/add_sevastopol_exact.py`; six-file set empty, no write/source HTTP. Current C2 input SHA `68629fd` parser Git blob `d31c5ac4` (merged PR #93) not allowlisted by pinned generator; PR #95 already contains exact-blob fail-closed patch `scripts/c6_pr93_generator_compat.py`. **`NEW_C2_NEON_JSON_PARITY=BLOCKED`** technical pre-generation guard, not a data discrepancy. No automatic retry or transferred owner authorization.
- [Work F PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) final HEAD `2064f38c86f28653bab0ee0255180ec740dfba31`, exact-head [Actions #43293275773](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293275773) SUCCESS with 14/6/5 staged tests and safe offline local Git; default-OFF single release job and final metadata binding now exist. **`NEON_PUBLICATION_CODE_READY=NO`** until PR #104 accepts immutable *final authorized* KPI bytes/SHAs (not original research candidate) and end-to-end offline proof passes. PR #100 consumer READY code-only. Rollback still BLOCKED. No merge/Netlify/Git publication/cutover.

## C6-C3-WORKD-STATIC-BINDING-PASS-PUBLISHER-BLOCKED-01 — Netlify code PASS, publisher integration BLOCKED (2026-11-12)

- [PR #104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/104) HEAD `a18e20295a7aa148c57fce4c5913ad68c3bd4c34`; [Actions #43288071274](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43288071274) SUCCESS, 6 offline tests, no artifact or deployment. **`NETLIFY_STATIC_BINDING_READY=YES` code-only**, Git build unchanged/default OFF.
- [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) HEAD `e2ebbdcbfe5ec04e096d1988660d7a8ac386f18a`; [Actions #43288267641](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43288267641) SUCCESS, artifact #13976546185, GitHub digest `2e2a18995ce265af9be788291c610a384de616f3ac810cfc2fc42cf9c1d5598c`. One-shot publisher prototype is **not connected** to existing workflow; no remote push. Prepared dashboard requires `publication_allowed=false`; PR #100 accepts production Neon KPI only with explicit true release authorization and matching manifest. **`NEON_PUBLICATION_CODE_READY=NO; ROLLBACK_OPERATIONAL_READY=NO`.** Next task narrow: connect owner-gated single publisher and reconcile exact release metadata/SHAs; keep default OFF. Work A six JSON and real two-plane restore still open. No cutover/deploy/merge.

## C3-NEON-GIT-KPI-CONSUMER-OFFLINE-01 — frontend consumer offline PASS (2026-11-12)

- [Draft #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100) HEAD `19446ba9b9513ec962be08a128b4132de3f1912c`; [Actions #43287759219](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43287759219) SUCCESS; artifact #13974983364 GitHub SHA-256 `f7a5f7d9b188ca92858ead9f83f232c668533a4800499a017b2b3234bded8a0e`. Four C3-only files; C2/casualty/aux untouched.
- Release authority, branch, manifest, 23 cities and generation gated; static timestamp/Git fallback intact. Short browser/CSV/rollback PASS; earlier 184/184 not rerun. **`PRODUCTION_NEON_KPI_CONSUMER_READY=YES` code-only**; physical Neon JSON/Netlify/rollback OPEN; no merge/deploy/cutover.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
