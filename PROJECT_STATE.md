# Project State — coordination snapshot

**2026-11-12 NO-GO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.** Latest: **C6-C3-WORKD-STATIC-BINDING-PASS-PUBLISHER-BLOCKED-01**.

Coordination: read main PROJECT_STATE.md and CHANGELOG.md, then PR #78. Verify SHA/Actions/artifacts. Keep C2, C3, production, Neon, casualty, DST, WIP and backfill separate. Historic evidence: [archive index](docs/coordination-archive/README.md).

## Release gates

- **Production:** Git `site-prod@d0a7d22d`, C2 #43262387718 23/23 PASS. Netlify still Git-only.
- **Neon:** PR #103 33,267/33,267 SQL parity PASS; physical six-JSON on latest C2 OPEN.
- **Frontend:** PR #100 `19446ba9` exact-head offline PASS, unmerged.
- **Netlify:** PR #104 `a18e2029` guarded static binding offline PASS; no deploy.
- **Git publisher:** PR #95 `e2ebbdcb` prototype tested but NOT wired; candidate has publication OFF. Match release authority with PR #100 before GO; keep OFF.
- **Rollback:** NO. Fresh Git-only static/runtime baseline, no-loss C2/casualty/aux and inactive Netlify restore unproven. Sevastopol old `25006→25008` and open `25100` unchanged.

## Next

1. One physical protected read-only Neon→six-JSON proof on C2 #43262387718.
2. Wire exactly one existing C2/Git publisher with authority/manifest synchronization; default OFF.
3. Verify practical two-plane Git-only rollback; seek separate owner merge/deploy/publication GO.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
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
