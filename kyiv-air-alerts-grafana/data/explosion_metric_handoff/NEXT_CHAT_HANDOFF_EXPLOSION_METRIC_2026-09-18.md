# HANDOFF — explosion metric: token-saving mode

Date: 2026-09-18

Repository: `olegbalakin-cmyk/kyiv-air-alerts-grafana`  
WIP branch: `multicity-wip-2026-09-16`

## State

- 11 cities are complete.
- Zhytomyr is frozen at **19/685 strict = 2.77%**, **20/685 sensitivity = 2.92%**.
- Next unfinished city: **Kropyvnytskyi / Кропивницький**.
- Frozen full-city denominator: **1161 alert episodes**.
- Source type: `raion_proxy`, proxy = `Кропивницький район`.
- Frozen coverage: **2025-09-01 through 2026-09-17**.
- Work stays on WIP/test. No production deploy.

Canonical completed-city input: `data/explosion_preview_input.json`.  
Research queue: `data/explosion_metric_handoff/city_explosion_metric_status_2026-09-18.csv`.

Do not load `explosions_test.json`, dashboard_data, old city packages, or completed-city evidence during Kropyvnytskyi research.

## Kropyvnytskyi is split into two independent chats

The split is by **alert episode start date in Europe/Kyiv**, chosen to balance the frozen denominator.

| Part | Episode-start dates | Frozen denominator |
|---|---|---:|
| K1 | 2025-09-01 through 2026-04-28 | **582** |
| K2 | 2026-04-29 through 2026-09-17 | **579** |

582 + 579 = **1161**.

An episode that starts on 2026-04-28 and ends on 2026-04-29 belongs to **K1**. Do not split or duplicate a cross-midnight episode.

Use separate chats for K1 and K2. Do not research both halves in one chat.

Task files:
- `KROPYVNYTSKYI_K1.md`
- `KROPYVNYTSKYI_K2.md`
- after both are complete: `KROPYVNYTSKYI_MERGE.md`

## Frozen rules

Count at the **alert-episode level**.

Strict requires:
- exact city: Кропивницький;
- confirmed aerial-war context;
- exact/approximate event time inside the matched alert episode, or explicit wording that the explosion was during the alert.

Sensitivity may additionally include strong `inferred_same_attack` or `near_boundary` cases.

No automatic +/-5 or +/-10 minute tolerance.

`Кіровоградщина`, `Кропивницький район`, oblast/district wording, or consequences elsewhere are leads only. They are not exact-city evidence.

Publication time is not explosion time.

## Token-saving rules

For each K1/K2 chat:

1. Read only its task file. The main handoff is optional.
2. Retrieve only alert episodes whose **start date** falls inside that half.
3. Search the web/local media narrowly for exact-city explosion reports.
4. Use the large Telegram/media archive **only pointwise when needed**:
   - to resolve a specific candidate/date;
   - to recover timing for an otherwise strong exact-city report;
   - to check one suspected miss.
   Do not unpack or scan it broadly by default.
5. Do not print raw alert lists, large JSON/CSV, search result dumps, or rejected-noise lists into chat.
6. Keep only retained strict/sensitivity events, unresolved review cases, and minimal exclusion notes.
7. Stop after that half. Save a compact result file.

If a broad search produces many low-quality hits, narrow by exact city + date/attack. Do not preserve the full negative search log.

## Required K1/K2 result

Return one compact result file containing:
- part and date range;
- frozen denominator;
- `strict_events`;
- `sensitivity_only_events`;
- `review_events`;
- `strict_n`;
- `sensitivity_n`;
- retained events found only through local/web gap search;
- a one-line QA note.

For each retained/review event keep only:
- matched alert episode start date/time if known;
- event date/time if known;
- source URL;
- one short evidence summary;
- decision/basis.

Do not embed all denominator episodes in the result.

## Merge

After K1 and K2 are complete, the merge chat reads only:
1. `K1_result`;
2. `K2_result`;
3. `KROPYVNYTSKYI_MERGE.md`;
4. `data/explosion_preview_input.json` for the final write.

The merge chat must not redo web/Telegram research unless the two result files conflict.

Then freeze Kropyvnytskyi into `explosion_preview_input.json`, update the status/handoff, and let the existing automatic onboarding pipeline add it to the audited baseline/test metric.

## Queue after Kropyvnytskyi

Kherson 1412 -> Odesa 1465 -> Cherkasy 1548 -> Mykolaiv 1648 -> Chernihiv 1677 -> Dnipro 2259 -> Sumy 2297 -> Zaporizhzhia 2365 -> Kharkiv 3565.

Kyiv and Sevastopol remain special-source cases.


## Kyiv and Sevastopol alert-source adapters

These two cities are also auto-onboarded after their historical explosion audit is frozen, but their future alert episodes do **not** come from UkraineAlarm regionHistory:

- `kyiv`: completed exact-city episodes come from the production `alerts_combined.json` store (Kyiv municipal open data + Kyiv Digital fallback).
- `sevastopol`: completed exact-city episodes come from production `sevastopol_events.json`, using only verified complete pairs after the Sevastopol correction logic.

The scheduled explosion monitor fetches these two stores from the same `site-prod` snapshot as the production dashboard. Do not replace them with a district/region proxy.
