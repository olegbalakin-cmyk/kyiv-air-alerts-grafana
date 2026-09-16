# Recovery snapshot: Ukraine air-alert multicity Grafana

Дата snapshot: 2026-09-16, ~21:37 EEST.

## Canonical repo

- Repo: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana
- Branch: `main`
- Commit перед цим recovery-файлом: `3138b6bb4dab51c8d4712e0365e0b6640995c2b1` (`Audit Telegram alert sources`).
- Повний code/data живе в repo; цей файл потрібен, щоб новий чат швидко відновив методологію та незавершені рішення.

## Методологія джерел

Пріоритет географії: `exact city -> eponymous raion proxy -> oblast`.

Не backfill-ити стару історію ширшою географією до появи вузького ряду.

Для районного proxy після validated rollout:

`proxy = union(eponymous raion intervals, explicit oblast intervals)`.

Overlap інтервалів зливати ДО підрахунку і duration, і alert episodes.

У 2026 explicit `level=oblast` у Vadimkin dataset практично відсутній, тому union фактично дорівнює raion. Це НЕ означає, що тривога в одному районі = тривога всієї області.

## Поточний production dashboard: 15 рядів

Exact city:
- Київ: coverage_start 2022-02-28.
- Харків: `м. Харків та Харківська територіальна громада`, 2025-02-17.
- Запоріжжя: `м. Запоріжжя та Запорізька територіальна громада`, 2025-03-19.

Raion proxy:
- Черкаси -> Черкаський район, 2025-01-10.
- Житомир -> Житомирський район, 2025-01-23.
- Дніпро -> Дніпровський район, 2025-05-01.
- Хмельницький -> Хмельницький район, 2025-07-07.
- Полтава -> Полтавський район, 2025-08-01.
- Рівне -> Рівненський район, 2025-08-01.
- Суми -> Сумський район, 2025-08-06.
- Вінниця -> Вінницький район, 2025-08-21.
- Кропивницький -> Кропивницький район, 2025-09-01.
- Львів -> Львівський район, 2025-09-01.
- Чернігів -> Чернігівський район, 2025-09-03.
- Одеса -> Одеський район, 2025-11-04.

CRITICAL TODO: user explicitly noted these 12 proxy rows are not cities in pure form. Change visible labels to e.g. `Одеса (Одеський район)`, `Львів (Львівський район)` etc. Exact-city rows remain plain city names. Do not present the mixed set as a pure city ranking without qualification.

## Proxy bias benchmark (2026)

Харків exact city vs Харківський район:
- city 3294.136 h; raion 3898.516 h; overlap 3270.970 h;
- city covered by raion 99.3%; raion matching city 83.9%;
- raion-only 627.545 h; duration bias +18.35%.

Запоріжжя exact city vs Запорізький район:
- city 2865.036 h; raion 4892.270 h; overlap 2860.787 h;
- city covered by raion 99.85%; raion matching city 58.48%;
- raion-only 2031.483 h; duration bias +70.76%.

Conclusion: raion is close to a superset of city alerts but may strongly overcount actual city alert time. No generic correction factor.

File: `kyiv-air-alerts-grafana/data/raion_vs_exact_city_2026.json`.

## Why union with oblast is needed in transition 2025

Key post-rollout additions beyond raion-only:
- Житомир +596.896 h (+121.07%).
- Львів ~+27.3 h (~+30.4%).
- Черкаси +292.589 h (+16.33%).
- Хмельницький +35.133 h (+14.34%).
- Дніпро +282.853 h (+12.57%).
- Херсон candidate +174.749 h (+11.95%).
- Рівне +25.944 h (+11.60%).
- Вінниця +37.906 h (+10.62%).

For evaluated 2026 periods explicit oblast adds 0 h.

File: `data/proxy_union_evaluation.json`.

## Current shared comparison window

- Monthly: starts 2025-12-01.
- Weekly: starts 2025-11-10.

## Main workflow

`.github/workflows/update.yml` runs twice daily (`15 4,12 * * *`) plus manual/push triggers.

Order:
1. `scripts/update_data.py`
2. `scripts/add_weekly_breakdown.py`
3. `scripts/render_dashboard.py`
4. `scripts/add_weekly_panels.py`
5. `scripts/add_duration_unit_switch.py`
6. `scripts/expand_multicity_production.py`
7. `scripts/update_casualties.py`
8. `scripts/finalize_multicity_dashboard.py`
9. `scripts/add_casualty_panel.py`
10. commit generated data/dashboard
11. `scripts/deploy_grafana.py`

`finalize_multicity_dashboard.py` now reads `production_city_keys` dynamically from `dashboard_data.json`.

`add_casualty_panel.py` finds methodology dynamically, not by fixed id=900.

The full production run after these changes passed all steps including Grafana deploy.

## Freshness warning

Multicity source: `Vadimkin/ukrainian-air-raid-sirens-dataset/datasets/official_data_uk.csv`.

Audits on 2026-09-16 saw latest upstream finished alert around `2026-09-07T05:39:33Z`. Thus zero values after Sep 7 for non-Kyiv rows can be source staleness, not true absence of alerts.

Kyiv was fresh to 2026-09-15; current calendar day is excluded.

Always check upstream freshness before interpreting the latest week / 28-day KPIs.

## Remaining oblast centers / next scope

User instruction: ignore Donetsk and Luhansk for now.

Working conservative plan: re-check and cite the official nationwide district rollout of 2025-12-15 (except Donetsk/Luhansk), then add from that date:
- Херсон -> Херсонський район
- Луцьк -> Луцький район
- Ужгород -> Ужгородський район
- Івано-Франківськ -> Івано-Франківський район
- Чернівці -> Чернівецький район
- Тернопіль -> Тернопільський район

Earlier source-observed starts exist, but do not backdate from first event alone.

`data/telegram_source_audit.json` confirms recent district messages for several of these; Telegram web search is limited, so its `first_at` is NOT rollout date.

### Mykolaiv

Do not use `Миколаївський район` if a real exact-city row can be reconstructed.

Important finding: official publications distinguish Mykolaiv city from the rest of the oblast; exact-city start/all-clear messages exist. Vadimkin CSV currently does not expose a stable modern Mykolaiv hromada series. Build and validate a dedicated exact-city adapter (official @air_alert_ua and/or official mayor channel).

The preliminary mayor-channel audit has repeated/orphan events and a bad long pair; do not use naive durations in production.

### Sevastopol

There is a separate city-level air-alert signal published by the occupation administration (`@razvozhaev`), introduced around 2023-09-25 according to external reporting. It can be treated geographically as exact-city, but source must be explicitly labeled as occupation-administration data.

Build a dedicated historical parser; Telegram web-search `first_at` is only a recent-window artifact, not coverage_start.

### Simferopol / rest of occupied Crimea

No reproducible stable city-level series established yet. Do not add until a source can be reconstructed consistently.

## Exact-city discovery

`states.json + official_data_uk.csv` audit found sustained current hromada-level city series in 2025-2026 only for Харків and Запоріжжя. Kyiv comes from municipal sources.

Administrative presence of a hromada in `states.json` does not prove an operational exact-city alert stream.

File: `data/exact_city_hromada_audit.json`.

## 2026 oblast semantics

- alert somewhere in oblast = UNION of all raions;
- entire oblast under alert = simultaneous active coverage across all raions;
- one raion alert does not imply whole oblast.

File: `data/full_oblast_share_2026.json`.

Caveat: Dnipropetrovsk audit had 6/7 raions represented and Zhytomyr 3/4, so strict full-coverage=0 there is not interpretable as real zero.

## Kyiv casualty block

Same dashboard also maintains Kyiv deaths from aerial attacks by month. Snapshot metadata:
- 2025 audited reconstruction: 166 deaths;
- KMVA annual cumulative: 171;
- 5-person difference not reliably attributable to specific attacks;
- late deaths from wounds attributed to attack date;
- ground combat/artillery excluded.

Do not accidentally overwrite casualty logic while editing multicity alerts.

## First files to open in a new chat

1. `RECOVERY_INSTRUCTIONS_UA.md`
2. `kyiv-air-alerts-grafana/data/dashboard_data.json`
3. `kyiv-air-alerts-grafana/scripts/expand_multicity_production.py`
4. `kyiv-air-alerts-grafana/scripts/finalize_multicity_dashboard.py`
5. `.github/workflows/update.yml`
6. `data/raion_vs_exact_city_2026.json`
7. `data/proxy_union_evaluation.json`
8. `data/exact_city_hromada_audit.json`
9. `data/raion_stable_start_candidates.json`
10. `data/telegram_source_audit.json`
11. `data/full_oblast_share_2026.json`

## Recommended next sequence

1. Fix visible labels of the 12 current proxies to `City (Raion)` everywhere, including comparison legends.
2. Re-verify 15.12.2025 nationwide rollout and add the six remaining non-Donetsk/Luhansk centers conservatively.
3. Build exact-city Mykolaiv adapter.
4. Build Sevastopol adapter with explicit occupation-authority source label.
5. Leave Simferopol out pending reproducible data.
6. Recompute shared comparison periods.
7. Run main workflow and verify data commit + Grafana deploy.
8. QA that exact-city and proxy rows are visually distinguishable.

## Non-negotiable rules

- Never use first observed event as rollout date without validation.
- Never backfill old city/raion history using oblast data.
- Exact city is gold standard; raion proxy must be labeled.
- Merge overlapping intervals before counting episodes/duration.
- Exclude current calendar day.
- Exclude first partial month/week after coverage_start.
- Cross-series comparison uses common complete calendar periods.
- Do not infer a universal city correction factor from Kharkiv/Zaporizhzhia.
- Check upstream freshness before interpreting terminal zeros.
