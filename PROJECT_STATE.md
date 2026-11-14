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
- **Independent open work:** full historical completeness (including Sevastopol `25006→25008`), DST/active-alert semantics, casualty, WIP and backfill retain their separate gates; `DST_CORRECTION=OFF`. Cutover rollback was prepared, not exercised in the successful release.

## Concrete next tasks

1. Check 1–2 further scheduled C2→Neon→Git cycles: 21/21 continuity, writer, 23/23 readback, Git publication, no unintended Netlify production deploy.
2. Mark migration CLOSED after repeat-cycle stability; continue historical audit/DST/casualty separately.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-AUTO-GIT-RESTORED-2026-11-14-01 — cutover and first scheduled Git-only cycle PASS (2026-11-14)

- Earlier owner-approved historical cutover `C6-C3-WORKS-NEON-CUTOVER-PASS-01` (PR #78) physically published via [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769), both SUCCESS: historical 23-city QA PASS, `GLOBAL_CUTOVER=YES` (not live-active alerts).
- Controlled [one-shot #43588351374](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43588351374), attempt 3, SUCCESS. Owner-enabled first four-hour [scheduled C2 #43625014243](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43625014243), attempt 1, SUCCESS 2026-11-14 18:09–18:38 UTC: bridge continuity 21/21, writer `NEON_SUCCEEDED`, 23/23 capture receipts, physical Neon→six-JSON readback, [Git `site-prod@f67ee699`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/f67ee69903f8d223f701bf3958780dddc4de88c9) PASS; Netlify calls/deployments from this data update 0.
- Owner reports verified Netlify auto-publishing re-lock by another executor (not independently rechecked here). **`C6_STABILIZATION=OPEN` pending 1–2 further scheduled successes.** No production, workflow, casualty or DST mutations in this documentation update.

## UI-NETLIFY-LOCK-CONFIRMED-2026-11-14

- Owner locked publishing; Netlify read-only deploy confirms `locked=true`, current deploy `6af8b9cd9e5cf4983bbb407e` READY. Git 4-hour workflow `cron: 15 */4 * * *` unchanged; last scheduled [Actions #43625014243](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43625014243) SUCCESS. No changes to data, C2, Neon or casualty. Next UI release requires separate owner unlock.

## UI-CURRENT-PERIOD-COMPLETION-PROD-2026-11-14 — owner GO, served Netlify PASS

- Owner-approved [PR #152](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/152) → `site-prod@c980c3f70ed894d2583fc83ecdedd1f82c04afb1` (base `f67ee699`), **six frontend/test files only**, current Git data unchanged. Opt-in trend estimates completion of today (28-day), current calendar week, month, quarter as measured + hatched remaining time using 28 complete days, source clock and real Kyiv hours cap. No next-period bars; actual KPI unchanged.
- Current-data offline [#43633376211](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43633376211) SUCCESS (12 JS tests, 23/23 index, data parity); production [Actions #43633525080](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43633525080) SUCCESS, artifact #14128579418 SHA-256 `8417981d8cc5c8e0467ba6a923aa12842c8f52f78e1555db53e3ddb027c9b383`, Netlify `6af8b9cd9e5cf4983bbb407e` READY, served JS parity and historical index 23/23. Source C2/Neon/casualty untouched. **Next:** owner re-lock Netlify auto publishing; keep Git 4-hour updates.

## UI-QUARTER-ROLLING-PROD-2026-11-14 — frontend-only release PASS (2026-11-14)

- Owner-approved [PR #148](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/148) merged to `site-prod@c66b977930fbbbbe739efea60d474b04b2b002ea`. [Production Actions #43611233805](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43611233805) SUCCESS, published static Git-only frontend and verified served `app.js` parity, HTTP 200, KPI 23/23. Netlify deploy `6af8808e75d3ca5d1aef8d8e` READY. Deploy artifact #14120062823, SHA-256 `0a328711d187cf2f9483b03a19eb522ac297e28ba419292de7668652dc479511`.
- User-approved quarterly city/comparison/all-cities modes, opt-in rolling 30/90/180 one-day forecast, clean legend/tooltip, and EWMA 0.3 explanation. Exact draft regression [#43611072521](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43611072521) SUCCESS at `2de7326f` (artifact #14120002788). C2, casualty, source and Neon tracks unchanged. `GLOBAL_CUTOVER=NO`.
- **Next:** owner re-lock Netlify automatic publishing in Deploys; 4-hour Git data refresh remains enabled independently. This accepted UI release is not a C6/Neon acceptance.


## C6-POSTMERGE-C2-EXPORT-23-01 — physical same-run export and checkpoints PASS (2026-11-11)

- [Actions #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) scheduled C2 SUCCESS (16:08:40–16:36:22 UTC), after Work A `main@fe4ab1c1` and Work B `site-prod@6de49e3b`. `NEON_SUCCEEDED`: 33,135 canonical episodes (+69), 23-city QA, Git JSON publication `site-prod@cf960d7c` PASS.
- Actual C2 ZIP artifact [#13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895) uploaded (`c2-shadow-inputs-43055353190-1`, 3,669,061 bytes), export ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`. `CAPTURE_NAIVE_TIMESTAMP` absent; 23/23 persistent source checkpoints share GitHub run ID `43055353190`; Sevastopol now updated, historical `25006→25008` remains unresolved.
- **Proof boundary:** successful export/capture does not establish independent Neon readback/parity, source freshness all-city PASS in readback, Netlify deployment, approved DST/rollback or permission for global source switch. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-REPLAY-SEVASTOPOL-MERGED-01 — two scoped fixes staged in production branches (2026-11-11)

- Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) squash-merged to `main@fe4ab1c14bffa03ff58f1f9debc3cc510f1099b0`, exact-head [Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850) **16/16 offline PASS** (UkraineAlarm event timestamp replay only).
- Owner-approved [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) squash-merged to `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20`, exact-head [Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821) **8/8 offline PASS** (Sevastopol checkpoint eligibility only). No synthetic event closure, no cutover.
- First post-merge C2 and exact ZIP/SHA, source receipt continuity across all 23 cities, independent Neon readback and any Netlify deployment **not yet verified**. Prior source checkpoint 22/23; `25006` still unresolved. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
