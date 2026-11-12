# C6/C3 — reversible six-JSON site preview and final QA (2026-11-12)

**Verdict: BLOCKED — one narrow frontend compatibility condition.** This is NOT permission for production cutover. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Provenance and safety boundary

- Root `main:PROJECT_STATE.md` and `main:CHANGELOG.md` read first. Their latest accepted checkpoint is still `C6-POSTMERGE-C2-EXPORT-23-01`. Coordination draft PR #78 contains the newer proposed `C6-PHYSICAL-SIX-JSON-READBACK-PASS-01`; this report does not promote that PR into `main`.
- Physical read-only Neon artifact: Actions [#43187464328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328), ZIP [#13929117121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328/artifacts/13929117121), ZIP SHA-256 `76baea90252c6aa0e02cc7eeb668db60c4bf228fbbfc16ce13fe5790d0e7ce3f`. All 18/18 manifest file SHA-256 verified; all six candidate JSON are available, 23/23 cities.
- Same-run Git C2 comparison source: Actions [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190), artifact #13873291895, inner `c2-shadow-inputs.zip` manifest checked in isolated CI. 33,135 canonical episodes in snapshot; 262 older +75 later rows explicitly excluded, without deletion.
- Reused historic fixed preview [#41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902), artifact #13018841540. Pages-preview frontend already matches present `site-prod` for `app.js`, `index.html`, `styles.css`, `chart-share.js`, `kpi-range.js`, and `features.json` by Git blob SHA; the research package has only its existing preview routing patch. No new deployment pipeline, frontend redesign, current-source claims, DST correction, database writes, C2 writer, Neon proof or source HTTP.

## Independent offline parity

Comparison uses the **same frozen C2 output and overlapping completed dates**, not arbitrary later Git `site-prod` output. Candidate generated through November 11; Git package through November 10.

| Check | Matched | Unexplained divergences |
| --- | ---: | ---: |
| Monthly main series (alerts started, duration, averages) | 397 common completed city-months | 0 |
| Rolling weekly series (alerts, duration-derived averages) | 12,468 common city-windows | 0 |
| Daily28 main series (counts, duration and averages) | 621 overlapping city-days | 0 |
| Historical per-day starts | 12,629 days | 0 |
| Historical per-day union-of-intervals seconds | 12,629 days | 0 |
| Historical per-day start-duration seconds | 12,629 days | 0 |
| Exact complete monthly historical seconds | 392 months | 0 |
| Kyiv `alerts_combined.json` start/end/source | 2,852/2,852 records | 0 |
| `kyiv_threat_mix.json`, `sevastopol_events.json` | same-run auxiliary values | 0 |
| `casualties_by_city` | 23/23 structurally exact | 0 |

`alerts_combined.json` differs in serialization by design: Neon excludes redundant `duration_minutes`, but start/end/source match for 2,852/2,852 and reconstructed duration differs from legacy rounded duration by <=0.001 minutes for all rows. Physical manifest recorded 33,135 canonical, 262 historical superseded, 75 later inserts excluded. No independent evidence that these historical materials certify live current alerts.

## Physical browser & CSV QA

Isolated [GitHub Actions #43199909155](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43199909155), [artifact #13935215690](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43199909155/artifacts/13935215690), ZIP SHA-256 `bcfff615b25f7c2d6d96a48ed0b2326a95e8081cad6e7cbc66ad64407e3ef293`.

The actual hosted Chrome/Chromium browser accessed a runner-loopback HTTP preview with original frontend and original six candidate JSON:
- 23/23 cities × eight city time modes = **184/184** with both chart datasets rendered.
- 23/23 monthly city-intensity CSV downloads validated and SHA-256 recorded in the proof.
- 23/23 Git rollback monthly views checked; historic index returns to `site-prod`.
- Zero uncaught JS errors, zero HTTP >=400 responses, zero external requests; original feature flag keeps WIP attacks disabled.
- Config-only `Git → Neon → Git`, **28/28 unchanged research package files** restored to original digests; no production rollback.
- No false claim of active-alert freshness: candidate `current_source_verified` is false for every city.
- Actual screenshots and `browser_result.json` are in the artifact. The frontend's live feature paths were not all exhaustively interaction-tested, and only monthly CSV for every city is covered here (historical frozen proof covers more CSV configurations).

## Specific blocking defect — historical KPI index

`pages-preview/app.js` near `init()` accepts an index only if `index.meta.source_ref === "site-prod"`. Both embedded and standalone Neon `historical-daily-kpi.json` correctly report `source_ref = "neon:br-bold-mode-b5rub8pq"`, with `expected_cities=23`, `verified_count=23` and matching `source_dashboard_generated_at` timestamps.

The unchanged browser loads the dashboard but sets `state.historicalDaily = null`. Historical KPI calculations requiring the index are therefore degraded despite correct JSON. This is a **site-consumer defect**, not a physical Neon generator failure.

An **isolated temporary one-expression compatibility change** accepting the exact vetted `neon:br-bold-mode-b5rub8pq` `source_ref` restored `state.historicalDaily`, with no changes to any JSON. The proof then restored the original `app.js` and config bytes before exit. No production frontend was modified. This proves the cause and narrowness of the fix, but not a production cutover.

## One minimal next action

Accept a research-only, source-aware `validIndex()` guard in the existing C3 preview consumer that allows *only the pinned, vetted Neon source-ref in Neon preview mode*, without relaxing validation of `schema`, `expected_cities`, `verified_count` or `source_dashboard_generated_at`. Re-run this same browser QA and receive an all-green six-file PASS **before** any additional site-preview publication decision. Do not rewrite frontend, alter the six JSON, repeat Neon proof, deploy Netlify, merge, or enable DST.

**No public preview approval needed for this runner-local proof.** Any public preview requires separate owner approval. All production and independent casualty/backfill tracks remain unchanged.
