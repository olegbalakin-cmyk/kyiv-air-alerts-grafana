# C6 — Mykolaiv 2022–2025 source-scope research (2026-11-14)

**Verdict:** Keep the five individually verified 2022 **exact-city** Telegram pairs outside the production **Mykolaiv raion-proxy** series; preserve them as research evidence. No backfill or new source merge is justified from these five samples. **The larger issue is source coverage and geography, not loss of five rows from the live updater.** No Neon, site-prod, C2, Netlify, DST or schedule changes.

## Directly verified repository evidence

1. `site-prod:kyiv-air-alerts-grafana/data/mykolaiv_exact_city_audit.json` blob `6e9a8dcf58af3b8c4d446b33b531e8c3d3a2a40f` documents 10 official-channel air-alert notices, five starts and five ends from **2022-06-17, 06-22, 07-13, 07-25, 10-19** (Telegram `air_alert_ua` ids `14631–14639`, `15147–15164`, `17627–17630`, `18866–18867`, `29558–29561`). Totals **5 paired events / 4.803 hours**, no parser anomalies **within that small sample**. Search covered four pages / 22 hashtag matches, **not a certified complete 2022 city history**. Exact target: "м. Миколаїв та Миколаївська територіальна громада".
2. `site-prod:kyiv-air-alerts-grafana/data/city_source_audit.json` blob `9e53ce8b68d50fe56c6b44aa8c478d9406e1ebfe` (September 2026 exploratory inventory) reported **69 source records for the Mykolaiv city hromada** with first at `2022-03-16T00:17:27Z`. **Not the same 5-event search, not a validated full 69-pair series**; do not sum 69 and five. Also lists `1554` raion observations from 2022-03-18 through September 2026 but **largest inter-event gap = 1280.31 days**, thus earliest 2022 observation must not be called a reliable continuous pre-2025 district run. Separate `raion_stable_start_candidates.csv` blob `4bdd33051eb2941bcec4b5f623fa5b76d9ef5d18` identifies stable start `2025-11-05` and flags that earlier coverage start requires validation.
3. `site-prod:kyiv-air-alerts-grafana/data/mykolaiv_mayor_channel_audit.json` blob `0acea5a1a3bda273629478036788a05416fe9d32`, 2025-07-15 to 2026-09-16, 133 channel pages / 1577 posts, 110 starts, **101 mechanically paired events**, 9 repeated-activation anomalies. It is **not publication-ready** as an exact-city replacement: largest "paired" interval `14921→15142` is **2025-11-13T08:17:04Z to 2025-11-30T13:51:39Z** = **413.576 h (17 days)**, with another intervening start `15139`; other >48 h intervals `15382→15426`, `16590→16632`, `16704→16750`. One start `16704` is a **technical siren malfunction / no official alert** message, yet appears classified as a start. The 101 number is raw reconstruction, not validated official completed episodes. This is an **identified historical-reference parser/semantic problem**, not evidence of a public Neon error. No bulk import.
4. Read-only Neon current project `green-cake-44216048` / branch `br-bold-mode-b5rub8pq` / role `c6_shared_reader_v2`:
   - `city_key='mykolaiv'`: **2363 raw episode rows** at query time, earliest `2025-11-05T00:19:54Z`, latest `2026-11-14T15:08:42.059Z`.
   - **0** rows before `2025-11-05T00:00:00Z`; 2022 explicitly **0**. November 2025 **92**, December 2025 **101**, January 2026 **136**, February 2026 **117** rows. Raw DB count is not proof of distinct displayed chart alerts; use approved canonical projection when comparing public KPIs.
   - Mykolaiv stale source checkpoint affecting Nov 12–13 was previously resolved, suspect legacy ID `83013a6187472fb447198a17` exists in Neon. Regular C2 21/21 continuity and 23/23 readback [#43625014243](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43625014243) PASS is **current continuity only**, not original 2022–2025 coverage proof.
5. The archived `alerts.in.ua` CSV bridge `alerts_in_ua_bridge_additional_2026-09-07_16.meta.json` blob `f35f8d1d0e839b4da05ee0469a116096f1a46c5` includes 88 **Mykolaiv raion** completed episodes in September 7–16 2026, demonstrating independent modern overlap, **not** proof of 2022–2025 history.

## External independent source findings (public research only)

- [Suspilne, February 2025 retrospective](https://suspilne.media/mykolaiv/956399-za-tri-roki-velikoi-vijni-povitranu-trivogu-na-mikolaivsini-ogolosuvali-4130-raziv/) based on Air-alarms.in.ua: **4,130** air alerts in **Mykolaiv oblast**, February 24 2022 to February 24 2025; **3,108 oblast-wide** plus **1,022 in individual communities across the oblast**. These totals are **not city of Mykolaiv events** and must not be backfilled into the city.
- [Suspilne 2024](https://suspilne.media/mykolaiv/915753-protagom-2024-roku-trivogu-na-mikolaivsini-ogolosuvali-1228-raziv/) cites **1,228 oblast alerts** in 2024; again **oblast**, not city. The existence of rich oblast history independently rules out an assertion that only five Mykolaiv-related air alerts existed in 2022, but does not assign them to exact city.
- [Air-alarms.in.ua methodology](https://air-alarms.in.ua/region/mykolaiv): source official/OSINT distinction, oblast vs city/community scope and overlap explicitly separated; their regional aggregations cannot substitute for exact city timestamps; pre-15-March-2022 data semi-automated and less certain.
- [Alerts.in.ua API history documentation](https://devs.alerts.in.ua/amcharts): `/v1/regions/{uid}/alerts/{period}.json`, accessible under access and rate restrictions. Future targeted evidence request could seek archived **Mykolaiv city/hromada UID** event CSV, not unrestricted public API scraping. No API token or extensive backfill used here.
- [AERIS city statistics index](https://aeris-app.com/alerts/stats) advertises city/community signal history based on publicly documented prior data, but the similarly titled Google result `UA46100110010094231` resolves to **Mykolaiv city in Lviv oblast** and was **excluded**; do not confuse homonymous cities.

## Decision matrix

| Candidate | Verdict | Impact / action |
|---|---|---|
| Five exact-city 2022 pairs | `HISTORICAL_REFERENCE_ONLY` | Leave outside raion-proxy production; preserve original ID/timestamps/provenance, no deletion |
| Raion 2022 isolated record + 1280-day gap | `EXPLAINED_SOURCE_COVERAGE_DIFFERENCE` | Do not silently extend current 2025-11-05 start back to 2022 |
| 2022–2025 oblast alerts | `WRONG_SCOPE_FOR_CITY_BACKFILL` | Strong evidence of broader historical coverage at oblast scope; separate category |
| Mayor 2025–2026 101 mechanical pairs / 9 anomalies | `CONFIRMED_RESEARCH_DATA_QUALITY_RISK` | Test bounded 17-day and >48-h pair errors, but no automatic import |
| 2025-11-05 onward Neon raion | `CURRENT_CONTINUITY_PASS` | Retain 4-hour normal operations; not proof of 2022–2025 completeness |
| Whole 2022–2025 exact-city history | `INSUFFICIENT_EVIDENCE` | Requires validated city/hromada event-level archive with 2022–2025 coverage and explicit location mapping |

## One shortest next step (if requested)

Do **not** create new parser or broad backfill. Seek/read one already published **city/hromada-specific full historical event export (2022–2025)**, preferably alerts.in.ua by exact geographic identifier or a dated official source with provenance, and compare its start/end intervals with the 69 already observed community records and prior mayor archive. Prove territory/scope, dedup with raion only in overlapping 2025-11-05 window, separate source-break metadata, and use offline QA; stage only validated homogeneous historical segments separately and ask for a new owner GO before adding anything to current Neon/JSON. If unavailable, maintain explicit `coverage_start=2025-11-05` for raion-proxy series with the five samples parked as historical reference.

No changes to current C2/Neon/Git/Netlify. This report adds no new accepted release checkpoint; research draft PR only.
