# CASUALTY-ZAPORIZHZHIA-CURRENT-LEDGER-2026-11-12 — final independent reconciliation

**Result:** `RECONCILED_DELTA_FOR_REVIEW`, **not publication approval**. Verified 2026-11-12 at [Actions #43185154445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43185154445), exact workflow HEAD `902f004c1abcedfb746ae3546cbb420358e34da5`. The run completed SUCCESS, recorded the hashes below, and uploaded [artifact #13926754957](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43185154445/artifacts/13926754957), ZIP SHA-256 `05fab2a861484cdb3b411b6f8d45fe2873001efa2e034ecec05656da191afca8`.

## Decision table

| Measure | Result |
| --- | --- |
| Published source | Netlify `/app.js` reads `raw.githubusercontent.com/.../site-prod/kyiv-air-alerts-grafana/data/dashboard_data.json`, `casualties_by_city.zaporizhzhia` |
| Frozen `site-prod` SHA | `fc7261660bdee75ee59296ee94cc1189be6b1a22` |
| Frozen WIP SHA (candidates, not ledger) | `c66c242a852d7647b6183425228cb3db2d1d088b` |
| Last published JSON update | 2026-11-12 07:35:30 UTC; `casualties.generated_at=2026-11-12T09:33:36.954794+02:00` |
| Zaporizhzhia validated historic coverage | Through 2026-09-18; city CSV last row `2026-09`; no October 2026 row |
| Official final attack total | 23 deaths, cumulative 18 → 20 → 23 from retained publisher evidence (PR #73) |
| Already credited **in published casualty series** for this attack | **0**, proven by pre-attack series cutoff + zero confirmed Zaporizhzhia revision records, not by missing event ID alone |
| Reliable delta for separate review | **+23** (not applied) |
| Potential duplicate reports | 16 title-pattern WIP candidate records, incl. the target, all `needs_review`; candidate matches are not duplicate confirmed death entries; event-identical subset not automatically certified |
| Conflict between recorded figures | Early articles 18/20 and final 23 are cumulative updates; never additive; some child-count claims differ and are not used for the adult/civilian count |
| Sufficient evidence for publication-ledger reconciliation | **YES** — exact Git files, complete series route, confirmed revisions, served `app.js`, served JSON all checked |
| Decision | **`RECONCILED_DELTA_FOR_REVIEW`** — no write/merge/deploy |

### Critical audit points

- `city_baseline_routes()` routes `zaporizhzhia` through `validated_city`, **not** the Kyiv `baseline_monthly.csv` or the 20-city master. The Zaporizhzhia validated city CSV contains **316** deaths in 56 monthly rows, last `2026-09`; `manifest.validated_through` is `2026-09-18`.
- `apply_city_revision_overlay()` uses only `status=confirmed` records for the target city. `site-prod/revisions.csv` contains exactly **one** confirmed record, for **Sumy** (2026-09-20, +1); **zero** for Zaporizhzhia.
- WIP target `e0fba98b19473874e9a1d8f1` remains `needs_review`. WIP/news headlines for 18, 20, 23, or individuals are not confirmed production ledger entries. No province/death/civilian records were imported from WIP.
- `Netlify /app.js`: HTTP 200, **191,578** bytes, exact SHA-256 match to pinned app.js: `b39f1190ce50e403f24f81414fd0f9defe1269122e5aa4683afeca14e20e0d04`.
- `raw.githubusercontent.com/.../site-prod/.../dashboard_data.json`: HTTP 200, **16,634,378** bytes, exact SHA-256 match to pinned Git blob: `ea01943609fb4e8adc64450181cc1a94d7438507db7898fc78f99ab177d188fe`. Published Zaporizhzhia segment: 56 months ending September 2026, no October row.
- Netlify production deployment record `6adb629bc3ebc570117d82e1` is **ready** (published 2026-10-23). Static app.js was independently compared with immutable Git bytes. This does not rely on assuming the current Git HEAD was itself newly deployed.
- No publisher/news HTTP was performed. The only external HTTP performed by the CI was read-only `/app.js` and public raw `dashboard_data.json`. No stats, WIP, revision, Neon, code, production, merge or deploy writes.

### Exact record links

- [Zaporizhzhia baseline manifest / cutoff](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/data/casualties/cities/zaporizhzhia/manifest.json#L7).
- [Zaporizhzhia monthly baseline — October missing after September](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv#L57).
- [Production revisions — Sumy +1 only](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/data/casualties/revisions.csv#L2).
- [Production dashboard data](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/data/dashboard_data.json).
- [Production frontend data-source constant](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/pages-preview/app.js#L12-L14).
- [City routing and revision overlay](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/fc7261660bdee75ee59296ee94cc1189be6b1a22/kyiv-air-alerts-grafana/scripts/update_casualties.py#L485-L565).
- [WIP original target candidate](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L55833).
- [WIP 20-death candidate](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L39950).
- [WIP 23-death candidate](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L61460).
- [Original cumulative-total research report](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/6bfdf35a15bac0447bdfc3e975a9c5e3b70a15d5/research/casualty_cumulative_update_2026_11_11/FINAL_REPORT.md).
- [Retained original article artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313).
- [Read-only script](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/902f004c1abcedfb746ae3546cbb420358e34da5/research/casualty_zaporizhzhia_ledger_2026_11_12/reconcile.py).

## SHA-256 of verified exact Git-file bytes

| File/label | SHA-256 |
| --- | --- |
| `dashboard_data.json` | `ea01943609fb4e8adc64450181cc1a94d7438507db7898fc78f99ab177d188fe` |
| Zaporizhzhia `manifest.json` | `141e95e95caff7b4a03c41936a465d07bd82fc1741dc17f972cc6a635f0f9da5` |
| Zaporizhzhia monthly CSV | `d8565488423e5ce5a6131743b0d3ecd3796ffda7ea0e9d4df7dbae88a442e63b` |
| Production `revisions.csv` | `9a72050a8510b1ee14e3f0ba22f3ae85e548d6fe721eb3dd547d34f679b57b2a` |
| Master 20-city manifest | `abb211b5013cae24155af7811b73d0561f7015d52b8f0ab3e9051a286ba4a140` |
| Master 20-city monthly CSV | `699d0170ac37af4a89980df80e435292d6235c0e6d717a3b0dd347e68d10252f` |
| Kyiv baseline | `0a940a9bc4c911db7a9d76c14d97fd8ef203bd13ec5abe2bb9540da4b4624fe4` |
| `update_casualties.py` | `346469581ded8c05d87f239af588cdeab16f3bb8ee31f4acbfeabf5b308ca73d` |
| Public app.js | `b39f1190ce50e403f24f81414fd0f9defe1269122e5aa4683afeca14e20e0d04` |
| Production review queue | `e538863ad0fa9ef151514d96f4b352064bb5ded4a3f0fe6f99e90ca7fe9f43f9` |
| WIP multicity review queue | `3d9133d178d229d5356e1939db827411f8b2af21a4b72766c16c214933da0d8d` |

## Reproduce

Run on this research branch: `python research/casualty_zaporizhzhia_ledger_2026_11_12/reconcile.py` after fetching immutable Git SHAs `375e6935`, `fc726166`, `c66c242a`. CI `research-casualty-zap-ledger.yml` does so automatically on push. Outputs `proof/reconciliation.json` and `proof/FINAL_REPORT.md`; a missing/mismatched HTTP comparison fails closed to `BLOCKED_INSUFFICIENT_LEDGER_PROVENANCE`. No production writes permitted.

**Conclusion: the published series has zero credited deaths for the 10 October 2026 Zaporizhzhia KAB attack; 23 are eligible for human review, not automatic application.**
