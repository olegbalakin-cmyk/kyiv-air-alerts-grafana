# HANDOFF — explosion metric: 10 cities complete, Zhytomyr next

Date: 2026-09-18

## Current source of truth

Repository: `olegbalakin-cmyk/kyiv-air-alerts-grafana`  
WIP branch: `multicity-wip-2026-09-16`

Do not use the older handoff state that said Uzhhorod was only a checkpoint.

Canonical current files:
- `kyiv-air-alerts-grafana/data/explosion_preview_input.json` — frozen audited city results used by the test UX.
- `kyiv-air-alerts-grafana/data/explosions_test.json` — derived test series/rolling-90 data.
- `kyiv-air-alerts-grafana/data/explosion_metric_handoff/city_explosion_metric_status_2026-09-18.csv` — research status/queue.

Audited input commit: `d03165a5c8510505625a1c794e79899ee7dcde23`  
Derived test-series commit: `ab1d0b4690044d861b73ef6c8f6fa180e8636c79`

The branch now has explosion data for **10 cities**, not only Poltava.

## Completed cities — do not restart

| City | Alerts | Strict | Strict % | Sensitivity | Sensitivity % |
|---|---:|---:|---:|---:|---:|
| Полтава | 1805 | 51 | 2.83% | 53 | 2.94% |
| Ужгород | 92 | 1 | 1.09% | 1 | 1.09% |
| Івано-Франківськ | 103 | 6 | 5.83% | 6 | 5.83% |
| Чернівці | 113 | 2 | 1.77% | 2 | 1.77% |
| Тернопіль | 125 | 5 | 4.00% | 5 | 4.00% |
| Львів | 126 | 12 | 9.52% | 12 | 9.52% |
| Луцьк | 135 | 12 | 8.89% | 12 | 8.89% |
| Рівне | 232 | 13 | 5.60% | 13 | 5.60% |
| Хмельницький | 248 | 11 | 4.44% | 12 | 4.84% |
| Вінниця | 362 | 5 | 1.38% | 7 | 1.93% |

Poltava remains the frozen methodology benchmark. For the other nine cities, the repo's `explosion_preview_input.json` is the frozen audited summary. Detailed intermediate research packages are not all committed to the repo, so do not infer missing detail or re-open those cities merely because the old archive contains only the Uzhhorod checkpoint.

## Next city

**Zhytomyr / Житомир** is next.

Frozen workload snapshot:
- source type: `raion_proxy`
- proxy: `Житомирський район`
- coverage start: `2025-01-23`
- denominator in the frozen research window: **685 completed alert episodes**

Remaining normal-city queue, optimized by denominator:
1. Zhytomyr — 685
2. Kropyvnytskyi — 1161
3. Kherson — 1412
4. Odesa — 1465
5. Cherkasy — 1548
6. Mykolaiv — 1648
7. Chernihiv — 1677
8. Dnipro — 2259
9. Sumy — 2297
10. Zaporizhzhia — 2365
11. Kharkiv — 3565

Kyiv and Sevastopol remain special-source cases and should be handled after normal cities unless explicitly requested.

## Frozen metric rules

Publication wording:

> Під час X% повітряних тривог знайдено підтверджені публічні повідомлення, що в місті було чутно вибухи.

This is a media reconstruction, not a registry of all physical explosions.

Strict numerator requires all of:
- `city_status = exact_city`
- `war_air_context = confirmed`
- `temporal_match = exact_time_in_alert` OR `explicit_during_alert`

Sensitivity can additionally include strong:
- `inferred_same_attack`
- `near_boundary`

Do not use automatic +/-5 or +/-10 minute tolerances.

Match at the **alert-episode level**, not the day level. One alert episode with multiple explosions counts once; multiple separate alerts on the same day may count multiple times.

Publication time is not explosion time. Temporal evidence priority:
1. exact event time in text
2. approximate event time
3. event interval
4. explicit wording that it occurred during an air alert
5. date only

## Workflow for one city only

To reduce chat/context load, process exactly one city per chat:

A. **Denominator**
- reconstruct/retrieve the exact production alert episodes for the frozen coverage window;
- do not replace the production denominator with a public alert counter.

B. **Candidate discovery**
- Telegram first: exact grammatical city forms + auditory phrases;
- use region/district hits only as leads;
- do not treat `Житомирщина`, `Житомирський район`, etc. as exact-city evidence for Zhytomyr.

C. **Verification/matching**
- deduplicate logical events;
- verify exact-city geography and air-war context;
- match to a concrete alert episode.

D. **Gap search**
- local media/web search for misses beyond national Telegram exports.

E. **QA + freeze**
- strict numerator and percentage;
- sensitivity numerator and percentage;
- unmatched/boundary/review cases;
- count how many retained events were found only in the local/web gap search.

Stop after one city. If context is getting large, write a checkpoint package and stop instead of continuing.

## Context-minimization rule

At the start of a new chat, read only:
1. this file;
2. `city_explosion_metric_status_2026-09-18.csv`;
3. `data/explosion_preview_input.json` only to verify completed-city state.

Do **not** load `explosions_test.json` unless the derived 90-day trend is needed. It is not needed for candidate research.

Do **not** unpack/search the large Telegram benchmark package until candidate discovery for the active city.

## Production safety

This research stream is test/WIP only unless the user explicitly says otherwise.

Do not:
- modify `site-prod`;
- merge to `main`;
- deploy Netlify/Grafana;
- mix casualty/deaths work into the explosion metric.
