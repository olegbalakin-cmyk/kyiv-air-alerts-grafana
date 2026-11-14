# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-SV25006-SOURCE-STAGED-01 — historical Sevastopol all-clear correction (2026-11-14)

- Owner-approved [PR #158](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/158) merged `site-prod@98d4aacd`: source correction for #25006, 2026-11-04 17:14:45Z–17:56Z (secondary-source, minute-precision end). Offline 15/15 PASS. No Neon/production JSON update confirmed; next ordinary C2 must verify 578 pairs, no duplicates, writer and 23/23 Git parity. Schedule/Netlify unchanged. Proof in research PR #157.

### C6-AUTO-GIT-RESTORED-2026-11-14-01 — cutover and scheduled Git-only refresh PASS (2026-11-14)

- Accepted historical cutover `C6-C3-WORKS-NEON-CUTOVER-PASS-01` (PR #78), [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) PASS: `GLOBAL_CUTOVER=YES` for 23-city historical JSON. One-shot [#43588351374](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43588351374) attempt 3 PASS; first restored [scheduled #43625014243](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43625014243) SUCCESS, 21/21 continuity, Neon writer, 23/23 readback, Git-only [`site-prod@f67ee699`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/f67ee69903f8d223f701bf3958780dddc4de88c9), no Netlify deployment. Owner confirms re-lock verified by other executor; stabilization needs 1–2 more scheduled cycles. Historical audit, DST, casualty separate.

### UI-NETLIFY-LOCK-CONFIRMED-2026-11-14

- Owner lock accepted; Netlify read-only API `locked=true`, production deploy `6af8b9cd9e5cf4983bbb407e` READY. Four-hour Git workflow remains scheduled; latest observed data update #43625014243 SUCCESS. Next UI release requires owner unlock. No data/Neon/C2 change.

### UI-CURRENT-PERIOD-COMPLETION-PROD-2026-11-14 — frontend LIVE

- Owner GO [PR #152](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/152) → `site-prod@c980c3f7`; six UI/test files only, current data preserved. Actual + hatched remaining for current day/week/month/quarter with verified source clock and 28d occupancy. Offline [#43633376211](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43633376211) PASS, production [#43633525080](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43633525080) SUCCESS, Netlify `6af8b9cd9e5cf4983bbb407e` READY, served HTTP parity and 23/23. No C2/Neon/casualty changes. Next: re-lock Netlify auto publishing.

### UI-QUARTER-ROLLING-PROD-2026-11-14 — approved frontend LIVE (2026-11-14)

- Owner-approved PR #148 → `site-prod@c66b9779`. Production [Actions #43611233805](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43611233805) SUCCESS; Netlify `6af8808e75d3ca5d1aef8d8e` READY, HTTP asset parity/KPI 23/23. Quarters in three selectors, rolling 30/90/180 next-day prediction, tidy forecast legend/tooltips and EWMA definition. Preview [#43611072521](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43611072521) SUCCESS. Git data source unchanged; Neon OFF. **Next:** owner re-lock Netlify auto-publishing, without disabling 4-hour data updates.


### C6-POSTMERGE-C2-EXPORT-23-01 — real C2 bundle and 23/23 checkpoints PASS (2026-11-11)

- [Scheduled C2 #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED`, 33,135 episodes (+69), 23-city QA/Git JSON PASS (`site-prod@cf960d7c`). Real [artifact #13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895), ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`; checkpoint 23/23 updated, Sevastopol event `25006` still unresolved. Independent exact-run readback/Neon→JSON parity remains OPEN; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-REPLAY-SEVASTOPOL-MERGED-01 — narrow fixes merged, physical proof pending (2026-11-11)

- [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) → `main@fe4ab1c1`, [16/16 offline Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850); [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) → `site-prod@6de49e3b`, [8/8 offline Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821). Next regular C2 must prove real bundle SHA and 23/23 source continuity; independent Neon readback/Netlify deployment not confirmed. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-THREE-RUN-EXPORT-01 — C2 export blocked despite healthy writer (2026-11-11)

- [Manual 42902124611](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42902124611) and [scheduled 42908463331](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42908463331) SUCCESS; [scheduled 42970870607](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42970870607) writer/23-city QA/Git PASS (`site-prod@390e7635`, 33,066 episodes) but overall FAIL on GitHub diagnostic upload. Three exports blocked `CAPTURE_NAIVE_TIMESTAMP`, no bundle SHA. 22/23 refreshed checkpoints; Sevastopol stuck due unresolved recent pair anomaly. Next narrow time-source proof and 23/23 same-run readback. No cutover/DST.

### C6-EXPORT-DIAGNOSTIC-STAGED-01 — C2 export reason staged, still BLOCKED (2026-11-10)

- First enabled [run 42817288652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42817288652) published `site-prod@15a3f15b` and 23/23 bootstrap checkpoints; export `C2_BUNDLE_BLOCKED`, no artifact. Owner-approved [PR #54](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/54) merged `main@ee96fa78` with safe allowlisted reason output; [offline run 42829359694](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42829359694) 4/4 PASS. Await next scheduled run for actual reason and cross-cycle receipts. No manual run/cutover/DST; `GLOBAL_CUTOVER=NO`.

### C6-CAPTURE-EXPORT-OPTINS-ON-01 — owner-approved opt-ins enabled; first capture pending (2026-11-10)

- After [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341) PASS (canonical writer/23-city QA/Git publication; export SKIPPED), owner separately approved two C2 opt-ins. Isolated read-only [Actions 42792678131](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42792678131) SUCCESS at `c12b2eb7`: both repository variables checked as `true`. First regular collector bootstrap/overlap **PENDING**; no manual updater, Neon readback proof, source switching or DST activation. `publication_allowed=false; GLOBAL_CUTOVER=NO`.

### C6-GATED-RECEIPTS-STAGED-01 — hooks staged OFF; offline CI PASS (2026-11-10)

- Owner-approved [PR #47](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/47) squash-merged to `site-prod@cc8bcbe577196e6484d3a5fd83b4addfabfb9456`, followed by [PR #46](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/46) to `main@2fbe9d1970c6508cbc9c1d66db55327120fe857a`. Exact-head [Actions 42686471326](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42686471326) **32/32 offline PASS**; [preflight 42774215008](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774215008) **capture/export OFF**. Main push triggered [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341), outcome to verify. PR #48 research draft, DST OFF, real 23-city full receipts 0/23; no source switching, Neon cutover or flag activation. Next: post-merge updater check, separately owner-approved flags, bootstrap/overlap and read-only same-run proof. `GLOBAL_CUTOVER=NO`.

#<!-- coordination:history:end -->
