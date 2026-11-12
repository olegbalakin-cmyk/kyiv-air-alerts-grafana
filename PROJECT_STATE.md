# Project State — coordination snapshot

**2026-11-12 RELEASE NO-GO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF. Latest accepted: C6-C3-WORKK2-55PASS-RELEASE-CODE-READY-01.**

Read main PROJECT_STATE.md and CHANGELOG.md first; newer PR #78 governs. Verify exact commits, CI/artifacts. Keep production, Neon historical, casualty, backfill, DST separate. Previous transitions are below and in the [immutable archive](docs/coordination-archive/README.md).

## Current gates

- **Historical Neon:** independent physical [#43299402658](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43299402658) 23 cities, 33,267 episodes and six JSON PASS for C2 #43262387718; live current-alert status NOT certified.
- **Release code:** PR #95 `329eb5f60adc75ea52547f98530ef837d1a00cda` exact [#43309443728](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43309443728) 55/55 offline PASS; PR #104 `ea71a0e2` and PR #100 `19446ba9` contract PASS. K2 corrected prepare/publisher `final-run.json` placement. **`FINAL_RELEASE_ARTIFACT_PREPARE_WORKFLOW_READY=YES; RELEASE_CODE_INTEGRATION_READY=YES` offline code only; real prepared ZIP NOT CREATED.**
- **Missing source:** C2 #43262387718 has original C2 artifact #13967335571 but **no matching `c6-neon-git-preparation-43262387718-1` artifact**. `MATCHING_C2_PREPARATION_ARTIFACT=NO`. Final prepare requires same-run C2 prep, independent Work A, owner prepare receipt and fresh hashes; no substitution.
- **Rollback:** Work I2 Netlify alias `6af629b311d9632a220e652a` physically PASS; `NETLIFY_NONPROD_REDEPLOY_PROVEN=YES` but `ROLLBACK_OPERATIONAL_READY=NO` until proven production restore authority and fresh no-loss C2/casualty/aux Git-only package.
- **Production:** Git-only `site-prod@d0a7d22d`; Netlify production `6adb629bc3ebc570117d82e1` unchanged. Pause C2 and automatic site-prod Netlify `--prod` **before** owner-approved merges. Single JSON publisher afterward. **`CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.**

## Next

No more broad research. Separately authorize safe C2/Netlify pause and code-only merges; obtain one matching C2 preparation + independent Work A, pin final ZIP, capture fresh rollback and production redeploy permission, then owner-gated Netlify-first/one-Git-publisher cutover. No merge or deployment authorized by K2.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-C3-WORKK2-55PASS-RELEASE-CODE-READY-01 — Work K2 final workflow fixed, code-ready offline (2026-11-12)

- Verified Draft [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) exact `329eb5f60adc75ea52547f98530ef837d1a00cda`; [Actions #43309443728](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43309443728) SUCCESS attempt 1, **55/55** (14 staging, 6 publisher, 5 binding, 18 Work K/K2, 12 PR104→PR100). [Offline artifact #13983919719](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43309443728/artifacts/13983919719) independently SHA-256 verified `4035c68db1ca97ce0ed4a55fb5186ff576b9c031b2a43280034074fae6e2dd01` — CI proof, not final release ZIP.
- Exactly two changed files against `d25f02f2`: `.github/workflows/update-netlify-site.yml` deletes prepare-only undefined `$FINAL_RUN_ID` and fetches `final-run.json` after release job defines ID; `tests/test_c6_neon_final_prepare.py` adds passed placement regression. Default OFF, prepare `contents:read/actions:read`, single-writer concurrency, Git-only updater and publisher Python unchanged. No physical prepare dispatch, merge, Netlify or Git publication.
- **`FINAL_RELEASE_ARTIFACT_PREPARE_WORKFLOW_READY=YES; RELEASE_CODE_INTEGRATION_READY=YES` (offline code).** C2 #43262387718 has five artifacts including `c2-shadow-inputs` #13967335571 but no `c6-neon-git-preparation-43262387718-1`. Required same-run C2 preparation + matching independently proven Work A missing; `MATCHING_C2_PREPARATION_ARTIFACT=NO; REAL_AUTHORIZED_FINAL_RELEASE_ARTIFACT=NOT_CREATED; CUTOVER_PREFLIGHT_READY=NO; ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. No owner release GO.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
