# C6-UA-KYIV-01 — independently verified live feasibility report
2026-10-29 20:01 UTC (22:01 Europe/Kyiv)

## Verdict
`C6_UA_KYIV_01=PASS_BOUNDED` is a bounded **research completion**, not a pass for unified production ingestion. **Recommended C**, keep municipal JSON for authoritative Kyiv history and Kyiv Digital for the fresh completed tail. `UNIFIED_SOURCE_FEASIBILITY=NO` for replacing those sources with UkraineAlarm while preserving exact seconds, episode cardinality, detailed threat reasons and historical reason changes. Current-state UkraineAlarm can be an independent supplementary source, conditional on separate product decision. No Neon writes or production updates.

## Pinned capture
- main coordination source reread; capture exact research commit `dc1c1408cdd6398afeb1eb713e57401883c3ee3c`.
- `site-prod@e08cc7da8cf29fc8603f199c85f0964610a850a7`, operational WIP `92011e2cd6a0ce515cd048a4c298c0f0a7bfdf98`.
- Protected GitHub Actions [run 40944518015](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40944518015), job `123696227601`, SUCCESS; [artifact 12929106409](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40944518015/artifacts/12929106409), GitHub and independently recomputed full ZIP SHA-256 `71f37f6fd86bf071337304567f67e4ce8f1d565cba0f8905f7346216a383602b`. Five stored evidence-file byte counts and SHA-256 hashes independently matched manifest **5/5**.
- Four actual GET responses HTTP 200. No 401, 429 or network errors. Production request policy pinned Git blob `6fe5429a0abf93dbfb3bae009a9f0de4ef4f86b4`; policy file exact SHA-256 `cf3a7678d6e3a2fbd5e9c4a150cd5007ce2f0a6feac0be06e72cb5cac022df99`. Client imposed 70-second same-token minimum request gap, bounded retries and 429 cooldown. Research workflow used exact `update-netlify-site` production concurrency group and `cancel-in-progress: false`, 12-minute cron proximity stop. No concurrent production Actions jobs observed.
- Pinned source Kyiv JSON SHA-256 `23bc29df7681024871bcab68b4f2198f0ca0da1073de1e8853fc1b0c57752179`. Capture code SHA-256 `f3546dc93d083fcdd441053dd90d9336e7786a0e0eea116abc5943256fa53b5a`.
- Raw bodies were returned by API and retained only as controlled, downloadable Actions artifact (14-day retention); they are not in `site-prod`, main, WIP or Neon. Raw bodies contain no Authorization request headers. They include region tree, city current, city history and general active state. The sanitized receipts and hashes are durable in this research report.

## Live requests and raw SHA-256
| Request | UTC response | Bytes | Raw SHA-256 |
|---|---|---:|---|
| `GET /api/v3/regions` | 19:57:31 | 203940 | `0826d64de506bc0037add23df1108477ca99ee589937984ee006b2254cb6c75d` |
| `GET /api/v3/alerts/31` | 19:58:41 | 152 | `0211ad22ce0458e75afe7feda4e9eb106db479829691d035e439da20c212b099` |
| `GET /api/v3/alerts/regionHistory?regionId=31` | 19:59:52 | 3955 | `095b5c14aa2a3edef6e3231b93a31805b484c8d185be6cf517b18ecf85114d5f` |
| `GET /api/v3/alerts` | 20:01:02 | 24457 | `06ff127d916b1def860b59b7df157beca25f07feff09a3f448d4a4c68594e103` |

## Geography and active state
- Full official `/regions` response had 1606 region nodes. **`regionId=31` is uniquely `м. Київ`, `regionType=State`, top-level / no parent**; `regionId=14` is separately `Київська область`, also `State` / top-level. `regionId=147` is **Бердянський район, Запорізька область**, `regionType=District`. The live city status and history both return `regionId=31`, `м. Київ`; all 16 frozen city intervals have positive temporal overlap with this source. Thus `KYIV_CITY_SCOPE=PASS` for geographical identification, **not** for second-exact episode equivalence.
- `/alerts/31` had `activeAlerts=[]` at 19:58:41Z; `lastUpdate=2026-10-29T19:14:05.443763Z`. Last recorded completed AIR ended at 19:13:29.431448Z. There was no active Kyiv AIR reason to inspect in the city-specific snapshot.

## Historical Kyiv AIR and comparison
- Observed actual `regionHistory` group: `regionId=31`, **20 completed AIR rows**, 20/20 `isContinue=false`, no open AIR row, no reason/level/change-history field. From `2026-10-25T19:37:52.112218Z` through `2026-10-29T19:13:29.431448Z`. Start/end have UTC `Z` and microseconds; API SDK documents up to last 25 alerts; this capture observed only 20. NOT a full-city history; other older official rows are `OUT_OF_COVERAGE`.
- Frozen site-prod JSON has 2750 episodes, of which **2734 outside the observed window** and **16 eligible** (2 municipal precise + 14 Kyiv Digital HTML minute-based). **Exact start+end parity 0/16** (municipal 0/2 and Kyiv Digital 0/14). This does **not** imply the 16 alarms are missing: **all 16/16 have positive overlap** with at least one UkraineAlarm AIR record.
- Those 16 expected intersect **18 UkraineAlarm rows**. 13 of the 16 have overlap with one UA row and 3 with several; one UA row overlaps two expected episodes. Two further UA intervals (29 October 18:31–18:48Z and 19:09–19:13Z) follow the frozen Kyiv source snapshot and cannot be judged `extra` or absent until the source view refreshes.
- Two municipal precise cases show systematic but *sample-limited* earlier UkraineAlarm timestamps: `2026-10-25` UA start minus official start **-20.888 seconds**, end **-28.569**; `2026-10-26` start **-30.905**, end **-25.941**. Therefore microsecond formatting in UA **does not mean authoritative municipal-second parity**.
- UA itself contains overlapping adjacent rows on 26 October: `19:41:29.294601Z–20:44:16.631725Z` and `20:43:38.204525Z–21:11:15.691834Z`, an overlap of **38.427 seconds**, both with `isContinue=false`. No automatic row-to-physical-episode 1:1 assumption is warranted, nor should rows be silently unioned without explicit source semantics.
- The frozen 184 October municipal candidate set is **not tested in full** by the UA 20-row response. Existing 113/113 October archived Kyiv Digital API parity is a **separate source** and must never be presented as UA parity. Earlier rows outside current UA window stay `OUT_OF_COVERAGE`.
- Timezone: real UA current/history timestamps use explicit UTC `Z` plus fractional seconds. Frozen municipal and Kyiv Digital rows are normalized to UTC; UTC ordering supports the DST transition on Oct 25 without interpreting naive clocks.

## Reason fields and limits
- `/alerts` general snapshot contains 48 active AIR alerts plus 6 ARTILLERY and 1 URBAN_FIGHTS; across those 55 alerts, 68 `activeAlertLevels`: **39 Red**, **29 Yellow**, including **13 AIR alerts with simultaneous two levels**. Each level has `alertLevel`, `reason`, `createdAt`.
- Actual values in that national current snapshot: `Дронова загроза (жовтий рівень)` (27 levels), `Ракетна загроза (червоний рівень)` (26), empty string (15). **No distinct observed field values for cruise vs ballistic missiles, aircraft or combined attack**. Empty does not mean no threat. This establishes present-day national current-state `Reason`, not a Kyiv-specific active reason (city had no active alert).
- None of the **20 Kyiv history rows** contains `reason`, `activeAlertLevels`, `alertLevel`, or history of reasons; all contain generic `AIR`, start, end, duration and `isContinue`. Historical reason preservation after OFF is **not proven by this endpoint and absent from this observed window**. Multiple contemporaneous `createdAt` levels show simultaneous current reasons, not retrospective intra-episode transition history.
- Compare with current `site-prod:data/kyiv_threat_mix.json`: Kyiv Digital episode-level `causes/last_cause` categories drone/massive-drone/missile/ballistic/mig/combined/unknown; its own metadata correctly says intra-alert reason changes are **not** reconstructed. UA current cannot replace this episode-level historical taxonomy.

## Executed validations
- Exact capture commit `dc1c1408`: synthetic offline workflow run [40944517881](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40944517881) **26/26 PASS**, covering region scope, AIR ON/OFF, repeated ON/OFF, reason changes without new AIR, missing/multiple reasons, DST, history cap, 401/429/network and idempotence. Synthetic reason strings and region IDs are not observed API facts.
- Independently downloaded raw live artifact via GitHub connector, computed ZIP SHA `71f37f6f...` matching provider and independently verified **5/5 internal file SHA-256 and byte counts**. Then ran **20/20 local read-only live-artifact replay tests PASS** on actual four response bodies, including unique Kyiv/oblast/147 mapping, exact/overlap parity, 38.427-second UA overlap and reason values. Replay test source SHA-256 `c543c8f9fd20c182f2353362704f42755f27c6473fbd3877a7fc58e894b6012a`; log SHA-256 `254dcfffa4ca20d6e993fba3e425e781f4a685a69abb27f8a77dabf56f9c74ef`. Local replay is not a separate Actions/CI run.

## Owner choices
- **A — NO as complete replacement:** region and current-state capability exist but 0/16 exact parity and historical reasons missing. Could be independent supplementary current-state source.
- **B — NOT APPROVED:** UA microsecond timestamps are not exact municipal second parity in 2/2 precise comparisons, and UA row splitting/overlap is not resolved. If future adjudication verifies intended timestamp definitions and dedup, UA could serve a bounded secondary operational role while Kyiv Digital retains detailed reasons.
- **C — RECOMMENDED now:** preserve municipal JSON for historical authoritative seconds, Kyiv Digital fresh tail and its reason taxonomy. No production integration, no Neon persistence changes, no classification or mapping rewrites.

## Residual blockers and non-actions
Reason change history after OFF, publisher-side identity, 184 October frozen crosswalks, true scope-equivalence beyond bounded 16 temporal overlaps, exact source-event semantics of overlapping UA rows, and full history beyond the last 20 are unresolved. No production workflow changes, no UkraineAlarm adapter modifications, no new token, no Neon credentials, no Neon writes or cutover. **This report is a candidate research checkpoint; owner/coordinator has not yet promoted it to main coordination docs.**
