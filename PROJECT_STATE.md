# Project State — current coordination snapshot

**Date:** 2026-11-14. **Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour C6 Neon→Git restored (first scheduled cycle PASS); stabilization OPEN.** `DST_CORRECTION=OFF`; live active-alert status not certified.
Latest accepted C6: **C6-AUTO-GIT-RESTORED-2026-11-14-01**. Browser delivery still uses static Git/Netlify JSON generated from Neon, not direct database access.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted `C6-C3-WORKS-NEON-CUTOVER-PASS-01`; owner-gated [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) SUCCESS, 23-city historical KPI/CSV/browser QA PASS. `GLOBAL_CUTOVER=YES` applies to historical JSON only.
- **Scheduled C2/C6:** owner enabled `C6_AUTO_NEON_GIT_ENABLED=true`. One-shot [#43588351374](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43588351374), attempt 3, PASS. First restored four-hour [scheduled #43625014243](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43625014243) SUCCESS: 21/21 bridge continuity, `NEON_SUCCEEDED`, 23/23 same-run receipts/readback, Git-only `site-prod@f67ee699`, zero Netlify calls. Multi-cycle stability not yet proven.
- **Netlify/UI:** owner confirms another executor verified auto-publishing re-locked; this note is not an independent lock readback. Latest UI PR #152, [Actions #43633525080](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43633525080) PASS, `site-prod@c980c3f7` and Netlify `6af8b9cd9e5cf4983bbb407e` LIVE. Keep UI releases separate from C2 data refresh.
- **Independent open work:** full historical completeness (Sevastopol `25006` source fix `site-prod@98d4aacd`; Neon/JSON pending), DST/active-alert semantics, casualty, WIP and backfill retain their separate gates; `DST_CORRECTION=OFF`. Cutover rollback was prepared, not exercised in the successful release.

## Concrete next tasks

1. Check 1–2 further scheduled C2→Neon→Git cycles: 21/21 continuity, writer, 23/23 readback, Git publication, no unintended Netlify production deploy.
2. Mark migration CLOSED after repeat-cycle stability; continue historical audit/DST/casualty separately.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-SV25006-SOURCE-STAGED-01 — secondary minute end, publication pending

- Owner-approved [PR #158](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/158) → `site-prod@98d4aacd`: #25006 end 17:56Z (secondary, minute precision); offline 15/15 PASS. Neon/JSON NOT yet proven. Next scheduled C2: verify +1, no duplicates, 23/23 parity. No manual run or Netlify deploy.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
