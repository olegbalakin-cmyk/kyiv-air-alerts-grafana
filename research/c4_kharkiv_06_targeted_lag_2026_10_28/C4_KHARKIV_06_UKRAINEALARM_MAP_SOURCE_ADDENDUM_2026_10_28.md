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

**Owner correction of image dating (2026-10-28): screenshot A was taken with 06.03.2025 selected.** Although the cropped image does not display its date selector, the owner explicitly confirms **March 6**. The initial research commit `f29a4a3f162f23962a76d7308b149b113be3d27e` incorrectly assigned this cropped view to March 5; that interpretation is **RETRACTED**.

Screenshot A shows the same named Kharkiv oblast and raion rows with tooltip `Червоний рівень небезпеки; 00:00 – 05:28; Тривалість: 5 год 29 хв` on **06.03.2025**. These are local day-chart **minute-level rounded/clipped display times**, not evidence of an official state transition at exact seconds. Taken with screenshot B (05.03.2025 21:13–00:00), the images provide **two adjacent daily segments consistent with an overnight oblast/raion red-level alarm spanning midnight** and displayed through roughly **05:28 on March 6**. They do not alone prove an uninterrupted **same event ID** or a city-hromada ON/OFF state: the date-clipped midnight boundary must not be interpreted as OFF+ON.

The exact map screenshot covers **raion and oblast rows**, NOT `м. Харків та Харківська територіальна громада`. The simultaneous identical red segments across raions are consistent with oblast-wide propagation, which the map methodology explicitly includes. No unique city territory identifier, event ID, raw producer timestamp or upstream API trace is shown.

## Contrast with C4-KH-06 source conflict
- current canonical/Vadimkin city-derived boundary: 2025-03-05 21:08:24–21:47:55 Europe/Kyiv;
- prior owner Alerts.in.ua historical city candidate: March 5 21:08:24 – March 6 05:03:45;
- contemporaneous ZN.UA report: March 5 21:08 to March 6 05:03 **at minute precision**;
- new official-map screenshots: **raion/oblast** red segments on **March 5 21:13–00:00** and **March 6 00:00–05:28**, each clipped to its selected day. The latter is a newly date-corrected corroboration of a **night-long oblast/raion** red-level interval; this is not a direct city-hromada witness or authenticated source event ID. City 21:08 vs raion/oblast 21:13 are distinct source clock/geography observations; **do not infer 4–5 minutes API publication lag**.

Together, the dated images **demonstrate red-level intervals for the oblast and raions across the night into March 6** (at least to the map's 05:28 displayed end). An interpretation claiming the *entire Kharkiv oblast/raion scope* was all-clear after 21:47 would conflict with the map. But a separate **city-hromada OFF** at 21:47 remains geographically possible (differentiation was in force), and city AIR continuity to 05:03/05:28 is still unverified.

**Material new temporal crosscheck:** the independently displayed oblast/raion end at **05:28** is approximately coincident with the previously reported `Суспільне Харків` **05:28:46 oblast OFF** publication and **05:28:53 city OFF** publication (IDs `message55096` / `message55097`, archival extraction not independently re-opened in this run). The 05:28 map end makes a **real near-05:28 oblast/raion transition** plausible, and weakens any assumption that the 05:28 Telegram timestamp must be a **25m08s delayed publication** of an Alerts.in.ua 05:03:45 event. It does **not** establish exact seconds or prove whether the two Telegram messages represent an official city OFF, an oblast OFF, a state change upstream, or an editing/publishing lag. The previously extracted content that the **city was still active at 05:28:46** is especially important to reauthenticate before assigning 05:03 to a city-level end.

**Three unresolved time hypotheses remain separate:** dataset 21:47:55 early city OFF; Alerts.in.ua/ZN.UA 05:03/05:03:45 city end; UkraineAlarm oblast/raion ~05:28 and Suspilne publication ~05:28, with city event-time and geographic identity still open. No basis for `LONG_INTERVAL_SUPPORTED` or `SPLIT_SUPPORTED` for the specified city parent. **UNRESOLVED** remains the exact case decision.

## Minimal next evidence / follow-up
1. **Completed at screenshot-evidence level:** user confirms the cropped 00:00–05:28 Kharkiv oblast/raion view is from **06.03.2025**; do not request that same screenshot again. For machine-auditable certainty, retrieve authenticated official-map historical raw record/event ID and the geographic code for the displayed 05:28 end; distinguish city from oblast/raion.
2. More decisive: open the official map's **separate Kharkiv-city/community** historical row or retrieve the authenticated official API/dispatch log with `territory_id`, signal type AIR, true ON/OFF event times in UTC, event/source IDs covering 05 Mar 21:08 through 06 Mar 05:29 Kyiv. Specifically test 21:47:55 city OFF, any later city ON, 05:03 vs 05:28 city OFF.
3. Validate whether oblast-wide events are projected onto raions for the March 2025 historical daily chart, and whether dates use Europe/Kyiv. Never equate the end of a day-clipped segment to an actual OFF.

No Neon DML/DDL, canonical retimestamping, classification verdict/binding edits, event associations, main/site-prod/operational WIP, production workflows, or cutover; no PROJECT_STATE/CHANGELOG edit until accepted checkpoint.
