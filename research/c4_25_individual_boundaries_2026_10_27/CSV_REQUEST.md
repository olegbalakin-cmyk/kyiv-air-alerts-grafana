# C4 — ONE CONSOLIDATED OWNER CSV REQUEST

All dates are calendar days **Europe/Kyiv**. These are day exports, not API requests. Export **all available alert types/geographies** for the day if selectable; preserve raw CSV untouched. One CSV per date, not one per city. Please include city/hromada and raion/oblast levels if exported.

Public source preflight succeeded (Vadimkin pinned SHA-256 `1f50085481d229f57b624d83b1ce723e884dea409c14afb5b7040c8a2f233e4f`, municipal Kyiv SHA-256 `b6fa2a214c51d11d43d01f521fa12e49145f37a74970d69117eacd373e30d986`). **18 Kyiv cases need no Alerts.in.ua CSV.** Case 6 has historical-end discrepancy despite source-verified adjacent A/B. These 7 dates cover the 6 unresolved source boundary cases and the extra case-6 anomaly, including local midnight crossings and the early Lviv A candidate.

| Дата експорту | Місто / географія | Номери випадків | Що саме потрібно підтвердити | Чому наявних джерел недостатньо |
|---|---|---|---|---|
| 2025-03-05 | Харківська міська громада | 6 | Перевірити довгу тривогу 05–06.03.2025 і момент завершення | Зіставлення довгої історичної тривоги з коротшим міським епізодом |
| 2025-03-06 | Харківська міська громада | 6 | Перевірити довгу тривогу 05–06.03.2025 і момент завершення | Зіставлення довгої історичної тривоги з коротшим міським епізодом |
| 2026-09-02 | Львівський район / Львівська область | 3 | Перевірити всі AIR start/end, реальні сусідні епізоди та географію | Непідтверджені межі або пропуски в міському / районному джерелі |
| 2026-09-13 | Львівський район / Львівська область | 1, 2, 3 | Перевірити всі AIR start/end, реальні сусідні епізоди та географію | Непідтверджені межі або пропуски в міському / районному джерелі |
| 2026-09-15 | Львівський район / Львівська область | 1, 2 | Перевірити всі AIR start/end, реальні сусідні епізоди та географію | Непідтверджені межі або пропуски в міському / районному джерелі |
| 2026-09-17 | Львівський район / Львівська область; Сумський район / Сумська область; Запорізька міська громада; Харківська міська громада | 2, 4, 5, 7 | Перевірити всі AIR start/end, реальні сусідні епізоди та географію | Непідтверджені межі або пропуски в міському / районному джерелі |
| 2026-09-18 | Сумський район / Сумська область; Запорізька міська громада; Харківська міська громада | 4, 5, 7 | Перевірити всі AIR start/end, реальні сусідні епізоди та географію | Непідтверджені межі або пропуски в міському / районному джерелі |

**Note:** If an export for 2026-09-02 does not show Lviv #3's predecessor and the CSV cannot establish completeness beyond the daily window, an additional earlier date may later be justified from the observed CSV itself; do not infer an unobserved gap is empty. Request no extra dates now. Do not convert minute-only values to invented seconds. Local dates include overlaps across UTC midnight.
