# Project State — coordination snapshot

**2026-11-12 NO-GO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.** Latest: **C6-PHYSICAL-PR93-BUILDER-DRIFT-WORKF-PARTIAL-01**.

Coordination: read main PROJECT_STATE.md and CHANGELOG.md, then PR #78. Verify exact SHA/Actions/artifacts; isolate C2, C3, Neon, casualty, DST, WIP, history/backfill. Historical evidence: [archive index](docs/coordination-archive/README.md). No inference of production release from offline proof.

## Release gates

- **Production:** regular C2 [#43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718) 23/23; live Git `site-prod@d0a7d22d`, unchanged. Netlify still Git-only.
- **C2↔Neon:** PR #103 SQL 33,267/33,267 exact, 0 unexplained diffs, 262 older versions preserved, PASS.
- **New-C2 physical six JSON:** owner [#43293835094](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43293835094) FAILED at `PREPARE_GENERATOR` with `BLOCKED_GENERATOR_INPUT:BUILDER_CODE_DRIFT:scripts/add_sevastopol_exact.py` (artifact #13978646521). Environment/run/receipt checkout and C2 ZIP download passed. No six files, not Neon parity failure. Existing exact-PR93 parser pin in PR #95 can be reused; new protected research SHA needs fresh owner grant before rerun.
- **Frontend:** PR #100 `19446ba9` gated Neon Git KPI consumer offline PASS; not deployed.
- **Publication:** PR #95 `2064f38c`, exact-head #43293275773 offline PASS. Single default-OFF release job, owner grant, final release manifest and six files tested; **`NEON_PUBLICATION_CODE_READY=NO`** because PR #104 still expects research KPI rather than final authorized KPI SHA.
- **Netlify:** PR #104 `a18e2029`, offline static binding PASS for research artifact, but not final release artifact. Narrow C3 contract change + offline end-to-end proof required.
- **Rollback:** `ROLLBACK_OPERATIONAL_READY=NO`; fresh compatible Git-only static/Git pair and no-loss restore including C2/casualty/aux/inactive Netlify package unproven. Sevastopol historical `25006→25008`, open `25100` remain separate.

## Next

1. Patch only exact PR93 parser-hash allowlist for physical research generator (reuse pinned PR #95 compatibility logic); offline test, obtain new separately owner-approved SHA, rerun read-only #43262387718 once. No writer.
2. Adapt PR #104 to pin *final* owner-authorized root KPI and six SHA while independently binding original Work A proof; verify final C3/C6/Netlify offline, default OFF.
3. Continue practical two-plane rollback (Work G). Only after physical PASS, publisher/Netlify contract PASS, rollback and distinct owner merge/deploy/publication grants consider GO.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
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
