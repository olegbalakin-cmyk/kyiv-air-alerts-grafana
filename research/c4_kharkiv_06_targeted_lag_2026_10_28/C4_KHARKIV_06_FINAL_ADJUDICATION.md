# C4-KH-06 — targeted final adjudication (research only)
Date: 2026-10-28. **Decision: UNRESOLVED.** This is an evidence-limited determination, not an accepted repair checkpoint.

## Preflight and provenance
Read current `main:PROJECT_STATE.md` and `main:CHANGELOG.md`; pinned `main@539f75d4dbb8c8043ae460432133c7b55ca6f69d`. Earlier accepted decision `2a11a637a76ab3f9c862e9a62177848ff0dfafa0` and contemporaneous addendum `a60121cf3acbc3874d0dbc85098f22649e8365ec`. Reused C4-E1 structured read-only record from `48e25ad158317728639c9305171ccbf251bec523`. Research addition only; no fresh Neon query and no database or production writes.

Owner Alerts.in.ua original March 5 and 6 raw CSVs and `messages.html` Telegram export are **not accessible as raw bytes in this execution** (no mounted conversation files or retrievable matching Project/Library file). The reported March 5/6 CSV SHA-256 hashes are `3113253b860c5678927b40353308ed51b435b07b16a00cb9bcc88529f9417062` (122 rows) and `b5a4c7a8b64f44dec66a0313b346120e98d154b0c78fb2f99ff5ed1815b96349` (131 rows), **not rehashed here**. Original Vadimkin CSV was not byte-verified here. Telegram evidence markdown/CSV stated in the task were not found in repository path listing or available file surfaces. Thus no independent archive-wide extraction, paired event-lag distribution, exact Telegram message IDs, or automation attribution can be certified.

## The narrow hypothesis and evidence
- Hypothesis: continuous city-hromada AIR from **2025-03-05 21:08:24** to **2025-03-06 05:03:45** Europe/Kyiv, 7:55:21; equivalent UTC `2025-03-05T19:08:24Z`–`2025-03-06T03:03:45Z`.
- Contradictory Vadimkin/current canonical `a556ee0d-4a90-40b4-adf1-db55646cd05b`: UTC `2025-03-05T19:08:24Z`–`2025-03-05T19:47:55Z` (21:47:55 Kyiv), 0:39:31; difference in end **7:15:50**.
- Owner CSV & historical classifier: long end `2025-03-06T03:03:45Z` (as previously reported, not independently read here).
- Contemporary [ZN.UA](https://zn.ua/ukr/war/shakhed-vluchiv-u-kharkivsku-bahatopoverkhivku-terekhoa.html) reported city alert **21:08–05:03** (minute-resolution; appended/updated after initial article). Supports the long version *to minute*, but its alert upstream independence from Alerts.in.ua is unproven. This source must not be treated as signed municipal transition.
- [Kharkiv OVA](https://kharkivoda.gov.ua/news/130659) describes differentiated city versus oblast signaling from February 2025. Production `kyiv-air-alerts-grafana/scripts/audit_city_sources.py` sets Kharkiv `preferred_source_type=exact_city`, `hromada=м. Харків та Харківська територіальна громада` and known coverage from `2025-02-17`.
- User-supplied Telegram timestamp claim: city AIR ON published 2025-03-05 21:08:32, city AIR OFF published 2025-03-06 05:28:53. **Not independently authenticated or matched to message ID** in this execution. Conditional (ONLY if same chronology) onset lag = **8 seconds** and ending gap after Alerts.in.ua OFF = **25 min 8 sec**. The latter is a candidate lag, NOT established as publication delay.
- General public Telegram search showed other dated pages and templates, but did NOT retrieve a verified **March 2025** same-hromada channel message ID or an independent ON/OFF archive. Do not infer 2025 event clocks from 2026 pages.

## Hypothesis falsification gates
A. At 21:47:55: **no independently verified same-hromada OFF**; absence in accessible secondary sources cannot rule out an actual OFF or geography change. Need original Vadimkin line-level row *plus* upstream signal identifier/state provenance.
B. Telegram publication lag: **sample size 0 independently authenticated matched pairs** for March 5–6 relevant week; ON/OFF medians, quantiles, maximum, dispersion, outliers and 25-min plausibility all **NOT ESTIMABLE**. Template-like phrasing can indicate automation, manual copy/paste or hybrid: automation mechanism **UNDETERMINED**.
C. Primary city OFF at ~05:03 or ~05:28: **not recovered**. The Telegram publication clock is not an upstream event clock. Do not force seconds from ZN.UA's minute-only reporting.
D. Geographic switches: current producer selects exact city; archived owner CSV geographic cells and Vadimkin upstream keys need an exact same-territory crosswalk, so differential signal capture remains a viable rival hypothesis.

## Data dependency preservation
- Canonical parent `a556ee0d-4a90-40b4-adf1-db55646cd05b`: end differs; **DO NOT RETIMESTAMP**.
- Historical classification `8c01721e-b4e8-4b63-b789-9801efbd63f8`: `STRICT_EVENT_POSITIVE`, `UNBOUND`, `alert_episode_uid=NULL`; do not change classification, evidence, or force BOUND.
- ACTIVE attack event `dc3a63ec-d9f8-412c-b0a1-09dd9398b27b`: remains associated with classification, event source preserved under previously accepted read-only evidence; no fresh DB confirmation and no alteration.
- Other 24 UNBOUND cases remain separate and do not depend on KH #6. No C3, C2, H1/H2, production, Neon, WIP, casualty or migration status change.

## Owner-facing conclusion
**UNRESOLVED**, with strong *minute-level* support for a long city alert but insufficient authentication to certify one continuous seconds-precision interval or a 25-minute publication lag. Shortest conclusive test is one official immutable **same-hromada AIR state transition journal** (2025-03-05 19:08:24Z to 2025-03-06 03:03:45Z) containing geometry/state/source IDs and authoritative clocks, or restored complete `messages.html` + original CSVs for provisional latency crosswalk, then validate mechanism against primary journal. Require an explicit OFF 21:47:55 plus subsequent same-hromada ON to declare SPLIT_SUPPORTED, or an authenticated uninterrupted primary sequence / independently corroborated OFF to declare LONG_INTERVAL_SUPPORTED.

No correction proposal is authored because the evidentiary threshold is unmet. Neither `main:PROJECT_STATE.md` nor `main:CHANGELOG.md` is changed: this is a new unaccepted research artifact, not an owner-accepted transition.
