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


<!-- coordination:history:end -->
