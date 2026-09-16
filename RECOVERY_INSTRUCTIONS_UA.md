# Recovery snapshot: Ukraine air-alert multicity Grafana

Оновлено: 2026-09-16 після розширення production до 21 ряду.

## Canonical repo

- Repo: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana
- Branch: `main`
- Основний workflow: `.github/workflows/update.yml`
- Generated dashboard/data: `kyiv-air-alerts-grafana/grafana/dashboard.json`, `kyiv-air-alerts-grafana/data/dashboard_data.json`.

## Незмінна методологія

Пріоритет географії: `exact city -> eponymous raion proxy -> oblast`.

Для proxy після валідованого `coverage_start`:
`proxy = union(eponymous raion intervals, explicit oblast intervals)`.

Правила:
- не backfill-ити стару історію областю до появи надійного вузького ряду;
- merge overlap до підрахунку duration та alert episodes;
- exact city = gold standard;
- районний proxy завжди явно маркувати районом;
- поточний календарний день виключати;
- перший неповний місяць/тиждень після coverage_start виключати;
- comparison використовує лише спільні повні календарні періоди;
- не робити універсального correction factor із benchmark Харкова/Запоріжжя;
- перевіряти freshness upstream перед трактуванням кінцевих нулів.

У 2026 `official_data_uk.csv` практично не має explicit `level=oblast`, тому `raion ∪ oblast` фактично дорівнює raion. Це НЕ означає, що один район = вся область.

## Поточний production: 21 ряд

### Exact city
- Київ — coverage 2022-02-28; municipal open data + Kyiv Digital fallback.
- Харків — `м. Харків та Харківська територіальна громада`, coverage 2025-02-17.
- Запоріжжя — `м. Запоріжжя та Запорізька територіальна громада`, coverage 2025-03-19.

### Raion proxy — у dashboard назви вже мають формат `Місто (район)`
- Черкаси (Черкаський район) — 2025-01-10.
- Житомир (Житомирський район) — 2025-01-23.
- Дніпро (Дніпровський район) — 2025-05-01.
- Хмельницький (Хмельницький район) — 2025-07-07.
- Полтава (Полтавський район) — 2025-08-01.
- Рівне (Рівненський район) — 2025-08-01.
- Суми (Сумський район) — 2025-08-06.
- Вінниця (Вінницький район) — 2025-08-21.
- Кропивницький (Кропивницький район) — permanent 2025-09-01.
- Львів (Львівський район) — 2025-09-01.
- Чернігів (Чернігівський район) — permanent 2025-09-03.
- Одеса (Одеський район) — 2025-11-04.
- Херсон (Херсонський район) — conservative 2025-12-15.
- Луцьк (Луцький район) — conservative 2025-12-15.
- Ужгород (Ужгородський район) — conservative 2025-12-15.
- Івано-Франківськ (Івано-Франківський район) — conservative 2025-12-15.
- Чернівці (Чернівецький район) — conservative 2025-12-15.
- Тернопіль (Тернопільський район) — conservative 2025-12-15.

15.12.2025 підтверджено Кабміном як загальнонаціональний запуск порайонного оповіщення по всій країні, крім Донецької та Луганської областей:
https://www.kmu.gov.ua/news/yuliia-svyrydenko-zaprovadzhuiemo-novyi-pidkhid-do-oholoshennia-povitrianykh-tryvoh-poraionne-opovishchennia

User explicitly asked to ignore Donetsk and Luhansk for now.

## Production implementation

Created `scripts/extend_remaining_proxies.py`.
It imports the prior builder, adds the six conservative 15.12.2025 proxies, and rewrites ALL proxy labels to `City (Raion)`.

`.github/workflows/update.yml` now runs:
1. update_data.py
2. add_weekly_breakdown.py
3. render_dashboard.py
4. add_weekly_panels.py
5. add_duration_unit_switch.py
6. extend_remaining_proxies.py
7. update_casualties.py
8. finalize_multicity_dashboard.py
9. add_casualty_panel.py
10. commit generated data/dashboard
11. deploy_grafana.py

Production run `35137372694`, job `104932998043`, completed successfully including Grafana deploy.
Current shared comparison window after 21-series expansion:
- monthly: 2026-01-01
- weekly: 2025-12-29

## Proxy bias benchmark

Харків exact vs Харківський район, 2026:
- city 3294.136 h; raion 3898.516 h; overlap 3270.970 h;
- city covered 99.3%; raion matching city 83.9%;
- raion-only 627.545 h; bias +18.35%.

Запоріжжя exact vs Запорізький район, 2026:
- city 2865.036 h; raion 4892.270 h; overlap 2860.787 h;
- city covered 99.85%; raion matching city 58.48%;
- raion-only 2031.483 h; bias +70.76%.

File: `data/raion_vs_exact_city_2026.json`.

## Transition 2025: why `raion ∪ oblast`

Examples of oblast-only time added after rollout:
- Житомир +596.896 h (+121.07%)
- Черкаси +292.589 h (+16.33%)
- Хмельницький +35.133 h (+14.34%)
- Дніпро +282.853 h (+12.57%)
- Рівне +25.944 h (+11.60%)
- Вінниця +37.906 h (+10.62%)
- Херсон candidate +174.749 h (+11.95%)

File: `data/proxy_union_evaluation.json`.

## Freshness warning

On the 2026-09-16 audit, Vadimkin `official_data_uk.csv` had latest finished alert around 2026-09-07T05:39Z, while Kyiv exact data were fresh through 2026-09-15.
Therefore zeros after Sep 7 for non-Kyiv can be upstream lag.

## Mykolaiv — exact-city work in progress

Do NOT substitute `Миколаївський район` for city if exact-city can be reconstructed.

Vadimkin exact hromada `м. Миколаїв та Миколаївська територіальна громада` is not a modern continuous source: audit found only 5 complete exact-hashtag air-alert episodes in 2022, last 2022-10-19.
File: `data/mykolaiv_exact_city_audit.json`.

Current candidate source: official mayor channel `@senkevichonline`.
Sequential scan from 2025-07-15 (not Telegram search) loaded ~1577 messages through 2026-09-16.
After removing `тривога триває/продовжується` status posts from starts:
- first city alert observed 2025-07-23;
- last current alert 2026-09-16;
- 110 starts, 101 paired episodes;
- still 9 repeated-activation anomalies;
- absurd 417 h in Nov 2025 proves non-standard end/update wording is still missed.

Latest audit script: `tools/reconstruct_mykolaiv_mayor_channel.py`.
Latest revision adds exact context between every anomalous repeated start, so the next output can identify missing end formulations rather than guess.
Workflow: `.github/workflows/audit-mykolaiv-mayor.yml`.

Do not production-wire Mykolaiv until anomalies are resolved. Likely official coverage start should be an externally validated system date (probably 2025-08-01) rather than first observed 2025-07-23; verify before production.

Note: in September 2026 Ukraine introduced yellow/red threat levels. Mykolaiv/oblast alert parsing now needs to treat level changes as updates within an active alert state, not automatically new episodes.

## Sevastopol — exact-city work in progress

There is a real city-level signal from the occupation administration. Provenance must be explicit and non-legitimizing, e.g. `source_provenance: occupation_administration`.

External reporting confirms the dedicated city algorithm was introduced and first used on 2023-09-25.
Examples:
- https://www.interfax.ru/russia/922635
- https://www.rbc.ru/politics/25/09/2023/6511ca6a9a794717ff6f6a22

Quick Telegram-search audit only retrieved Sep 14–16 2026 and therefore is NOT usable as historical coverage evidence.
The current `tools/audit_sevastopol_exact_city.py` was rewritten to sequentially scan `@razvozhaev` back to 2023-09-20 and reconstruct start/all-clear pairs.
Workflow: `.github/workflows/audit-sevastopol-exact.yml`.

Do not production-wire until the full sequential scan confirms continuity and manageable anomalies.

## Simferopol / rest of occupied Crimea

No reproducible stable city-level series established. Leave out for now.

## Kyiv casualty block

Do not break it while editing multicity alerts.
- 2025 audited reconstruction: 166 deaths.
- KMVA annual cumulative: 171.
- five-person difference not attributable to specific public attack records.
- late deaths attributed to attack date.
- ground combat/artillery excluded.

## Key audit files

- `data/city_source_audit.json`
- `data/exact_city_hromada_audit.json`
- `data/raion_stable_start_candidates.json`
- `data/full_oblast_share_2026.json`
- `data/raion_vs_exact_city_2026.json`
- `data/proxy_union_evaluation.json`
- `data/telegram_source_audit.json`
- `data/mykolaiv_exact_city_audit.json`
- `data/mykolaiv_mayor_channel_audit.json`
- `data/sevastopol_exact_city_audit.json`

## Next safe actions

1. Finish latest Mykolaiv anomaly-context run; inspect missing end formulations; refine state machine; re-run until durations are plausible and gaps explained.
2. Finish full Sevastopol sequential scan; validate first start near 2023-09-25 and continuity.
3. If Mykolaiv becomes clean, add it as exact-city with validated coverage start, not as raion proxy.
4. If Sevastopol becomes clean, add it as exact-city with explicit occupation-administration provenance and visible methodological note.
5. Leave Simferopol out until a reproducible city-level source exists.
6. Ignore Donetsk/Luhansk per user instruction.
