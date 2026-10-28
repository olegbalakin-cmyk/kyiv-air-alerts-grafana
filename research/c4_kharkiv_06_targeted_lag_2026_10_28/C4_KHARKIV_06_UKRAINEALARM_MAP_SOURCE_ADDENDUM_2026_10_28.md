# C4-KH-06: UkraineAlarm official-map day timeline source addendum
Date: 2026-10-28. **Adjudication: UNRESOLVED — no city-hromada OFF/ON certified.** Research-only new user-submitted evidence; not an accepted transition and not a production repair.

## Provenance / coordination
Preflight read current `main:PROJECT_STATE.md` and `main:CHANGELOG.md` (latest C3-RC3 and accepted C4-KH-06 full-report state). This addendum is subordinate to the already accepted `C4_KHARKIV_06_FULL_REPORT_2026_10_28.md` at research commit `21c6e0ae666246f0137893e980d342731d549bc2`. The accepted owner decision continues **KEEP CURRENT DATA**, with 24 other UNBOUND cases proceeding independently.

Original screenshots are uploaded in the conversation, **not committed as image bytes to Git**. Their byte hashes were computed against the actual mounted files (not inferred from screenshot filenames):
- screenshot A (cropped Kharkiv rows, tooltip 00:00–05:28): PNG 912x380, SHA-256 `17e0a297530fbb145abbf2f59e3a95d41f5bda73d11b624416251838292c8d50`.
- screenshot B (complete browser view with date, rows, tooltip 21:13–00:00): PNG 1917x852, SHA-256 `e7cfd89437cfe23bcdf86468ace38e74167de27d6c4a342afb957d3f967bd969`.

Website: https://map.ukrainealarm.com ; official map by UkraineAlarm/Stfalcon, separately identified by https://api.ukrainealarm.com . Its public page distinguishes **air raid alert red level** and **yellow level** and the stats text explicitly says `Тривалість для кожного району з урахуванням загальнообласних тривог`, i.e. raion timeline can inherit oblast-wide alerts: https://map.ukrainealarm.com/ . The official OVA (https://kharkivoda.gov.ua/news/130659) and contemporary Suspilne article (https://suspilne.media/kharkiv/954963-u-harkovi-zapracuvala-sistema-okremih-povitranih-trivog/) document **separate Kharkiv-city vs oblast signals from 2025-02-22**; Suspilne notes the official map displays the differentiated city/community separately from the rest of the oblast.

## Exact visually observed claims, no invented seconds
Screenshot B shows `Дата 05.03.2025`, `Тривоги по районах`, the red-level legend, and red spans on **Харківська область** and on **all shown raions**, including **Харківський район**. Tooltip over the evening red area: `Червоний рівень небезпеки; 21:13 – 00:00; Тривалість: 2 год 46 хв`. The span reaches **the right edge of the selected day**, not proof of a real OFF at midnight. It is **evidence of a red oblast/raion alert through late evening March 5**, including the period after 21:47:55 — but not necessarily the distinct Kharkiv city-hromada signal.

Screenshot A shows same Kharkiv oblast/raion rows with tooltip `Червоний рівень небезпеки; 00:00 – 05:28; Тривалість: 5 год 29 хв`. In the context of screenshot B's selected date, this is **the morning of March 5, 2025**, and can belong to an episode crossing from March 4. It **does not establish March 6 05:28**; the coincident minutes with prior Telegram publication time 05:28:53 on March 6 should **not** be conflated.

The exact map screenshot covers **raion and oblast rows**, NOT `м. Харків та Харківська територіальна громада`. The simultaneous identical red segments across raions are consistent with oblast-wide propagation, which the map methodology explicitly includes. No unique city territory identifier, event ID, raw producer timestamp or upstream API trace is shown.

## Contrast with C4-KH-06 source conflict
- current canonical/Vadimkin city-derived boundary: 2025-03-05 21:08:24–21:47:55 Europe/Kyiv;
- prior owner Alerts.in.ua historical city candidate: March 5 21:08:24 – March 6 05:03:45;
- contemporaneous ZN.UA report: March 5 21:08 to March 6 05:03 **at minute precision**;
- new official-map screenshot: a **raion/oblast** red interval on March 5 **21:13–00:00** with exact event end not exposed by the daily clipping. City 21:08 vs raion/oblast 21:13 are different clocks/possible geographies; **do not infer 4-5-minute API publication delay** from the offset.

The new source **strongly demonstrates red alert presence at oblast/raion scope after 21:47**, so an interpretation claiming the *entire Kharkiv oblast* was all-clear by 21:47 would conflict with this image. It does **not** contradict a distinct city OFF at 21:47 (differentiation was in force), nor establish uninterrupted city AIR until 05:03 or 05:28. No basis for `LONG_INTERVAL_SUPPORTED` or `SPLIT_SUPPORTED` for the specified city parent. **UNRESOLVED** remains the exact case decision.

## Minimal next evidence / follow-up
1. Inspect the official map on **06.03.2025** for **00:00–06:00**, with tooltips and the same region/raion; if red from midnight to morning, it adds **oblast/raion** night continuity, not exact city authority.
2. More decisive: open the official map's **separate Kharkiv-city/community** historical row or retrieve the authenticated official API/dispatch log with `territory_id`, signal type AIR, true ON/OFF event times in UTC, event/source IDs covering 05 Mar 21:08 through 06 Mar 05:29 Kyiv. Specifically test 21:47:55 city OFF, any later city ON, 05:03 vs 05:28 city OFF.
3. Validate whether oblast-wide events are projected onto raions for the March 2025 historical daily chart, and whether dates use Europe/Kyiv. Never equate the end of a day-clipped segment to an actual OFF.

No Neon DML/DDL, canonical retimestamping, classification verdict/binding edits, event associations, main/site-prod/operational WIP, production workflows, or cutover; no PROJECT_STATE/CHANGELOG edit until accepted checkpoint.
