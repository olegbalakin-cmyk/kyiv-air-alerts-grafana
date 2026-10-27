# C4 — Seven manual Alerts.in.ua CSVs, bounded owner review (no repair)

**Scope:** read-only evaluation of all seven owner-uploaded CSVs, no production, data, classification or Neon writes. New file export timestamp was not encoded in uploaded files; files observed in conversation 2026-10-27. All seven headers exactly: `Оголошено о, Закінчено о, Район/Громада/Місто, Регіон, Країна, Тип, Повідомлення`. Event clocks recorded in seconds, WITHOUT explicit timezone, interpreted as Europe/Kyiv; no invented subsecond times. The original seven files are retained as conversation attachments without changing their bytes; this research commit saves provenance, not raw CSV copies.

## Owner input manifest

| Local day | Rows | Raw SHA-256 |
|---|---:|---|
| 2025-03-05 | 122 | `3113253b860c5678927b40353308ed51b435b07b16a00cb9bcc88529f9417062` |
| 2025-03-06 | 131 | `b5a4c7a8b64f44dec66a0313b346120e98d154b0c78fb2f99ff5ed1815b96349` |
| 2026-09-02 | 561 | `2732b99188dea7e4d1e8402c4571497ab95944a43a7139a2b2bc800a59c13820` |
| 2026-09-13 | 552 | `888b9a8053c88b0920be181ed3f78acd9d2179b7761dc8c2590f7c04cca9e09d` |
| 2026-09-15 | 638 | `655177212ad88e5f0a6c2f33b029944ca729a2d7c700d9b11691591d28a4b663` |
| 2026-09-17 | 777 | `fdf845b0e4ad40d5c5707d797401769bf0821bfca62bc304cfcee3961cb900b2` |
| 2026-09-18 | 605 | `ba0f8f4b4cf695ce3604d58f9968608d10213e3807679371da7db362ac77b1d7` |

## Seven individually distinct source windows

All alert windows below are UTC, **seconds precision** from CSV. A/B are historical source corroborations at minute/second tolerance only, not proof of exact Neon identity at fractional seconds. Every original was located in manual source and every A/B has a corresponding source event; no classification binding has been admitted.

| # | City | Original source AIR UTC | A source UTC | B source UTC | Source scope | Status |
|---|---|---|---|---|---|---|
| 1 | Львів | 2026-09-13 02:32:14–06:11:11 | 2026-09-12 22:00:06–22:14:27 | 2026-09-15 16:44:13–17:09:02 | Archived Sep 7-16; source one interior | SOURCE_COVERED_DEPENDENCY_BLOCKED |
| 2 | Львів | 2026-09-15 16:44:13–17:09:02 | 2026-09-13 02:32:14–06:11:11 | 2026-09-16 23:05:55–23:26:02 | Archived Sep 7-16; source one interior | SOURCE_COVERED_DEPENDENCY_BLOCKED |
| 3 | Львів | 2026-09-12 22:00:06–22:14:27 | 2026-09-01 21:49:49–21:57:16 | 2026-09-13 02:32:14–06:11:11 | Missing Sep 3-6; archive Sep 7-16 and Sep 2 CSV not sufficient for completeness | SOURCE_INCOMPLETE |
| 4 | Суми | 2026-09-17 17:12:24–20:56:00 | 2026-09-17 14:51:31–16:33:00 | 2026-09-17 22:42:45–2026-09-18 01:19:20 | One interior, source second precision; production raion+oblast union may change true proxy | SOURCE_COVERED_DEPENDENCY_BLOCKED |
| 5 | Запоріжжя | 2026-09-17 19:33:49–21:54:45 | 2026-09-17 17:10:01–18:47:54 | 2026-09-17 22:26:55–2026-09-18 15:46:20 | One exact-city source episode; positive classification and active attack_event | SOURCE_COVERED_DEPENDENCY_BLOCKED |
| 6 | Харків | 2025-03-05 19:08:24–2025-03-06 03:03:45 | 2025-03-05 18:06:45–18:31:04 | 2025-03-06 09:12:46–09:34:35 | CSV agrees historical end, Vadimkin/Neon end 2025-03-05 19:47:55; active attack_event | SOURCE_CONFLICT |
| 7 | Харків | 2026-09-17 17:41:38–20:55:54 | 2026-09-17 14:26:34–16:15:04 | 2026-09-18 03:15:12–04:31:13 | One exact-city source episode; original still UNBOUND | SOURCE_COVERED_DEPENDENCY_BLOCKED |

## Frozen public-source and Neon observations

- Earlier independently source-verified Kyiv 18/18 cases remain unchanged, with their episodes exactly present in pinned production JSON and canonical Neon. All 25 cases have three present canonical Neon rows (A, middle, B) in bounded query; old classification IDs are *not* exact/current parent IDs and **all 25 original classifications remain UNBOUND**. An existing middle episode is not authorization to create a duplicate or change a classification.
- Manual Alerts.in.ua CSVs independently of Vadimkin corroborate historical originals #1–7. CSV snapshots include open and previous-day entries; we used completed AIR rows at the correct geo, deduplicating repeated rows across exports. Raw file count 7; overall rows 3,386; 2,869 unique closed Ukrainian AIR records across all geographies in uploaded snapshots.
- Source #1 and #2 interval day-gaps were closed with production's existing archived Sep 7–16 Alerts.in.ua bridge. Verification [Actions 40594480647](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40594480647) SUCCESS on source verifier `e294b6b6c5fced54d1849ebefadbf517d8b57ad0`; archive Git blob `1ece234379381b4d7c0d10f851a86aa61aa958f6`, decompressed SHA-256 `ba48bf85bd62e7f127dd1703bfcb9d38b4b960690adf1243175ce59366ec4d5a`. It is the **same Alerts.in.ua provider**, not a second independent source. Archived Lviv stream 3 closed events, 0 incomplete dropped. It does not cover **September 3–6** for #3.
- Historical #6 Kharkiv CSV start/end exactly `2025-03-05 19:08:24Z → 2025-03-06 03:03:45Z`; existing Neon central episode `a556ee0d-4a90-40b4-adf1-db55646cd05b` starts at the same instant but ends **2025-03-05 19:47:55Z**. This is a genuine source-authority conflict; no automatic winner, truncation, or overwrite.
- Exact-current Neon central 7: #1 `c90e7b05-1982-461f-945f-53d8130c627b`; #2 `451c8a2c-248a-41e5-b49e-31af3f44631f`; #3 `575f370c-6e99-4623-8219-f8fbdfd6c978`; #4 `8309abeb-0b67-43f6-b779-9de629cf9f40`; #5 `cb08e0c9-55bf-4419-a153-7cf37eaf3f07`; #6 `a556ee0d-4a90-40b4-adf1-db55646cd05b`; #7 `054dfada-c567-48eb-871b-f1822927025e`. All 7 were already physically present in replica; original historical IDs not equal.
- Original #5 has **six** `attack_event_sources` plus ACTIVE event `ef34834b-0513-4351-8839-d866a0e76e99`; original #6 has one source plus ACTIVE event `dc3a63ec-d9f8-412c-b0a1-09dd9398b27b`. Neither event has a bound episode UID. These are explicit migration dependencies. Other original classifications may have source rows; no nearest-time binding. Lviv #1–3 original prior physical UUIDs remain superseded. Several A/B anchor episodes already have independent `BOUND` classifications and/or episode sources, making naive replacement unsafe.
- Reader audit: approved Neon read-only compute `ep-calm-rice-b5073ypp` on `br-bold-mode-b5rub8pq` showed `transaction_read_only=on`, `pg_is_in_recovery=true`; only bounded SELECT, no mutation. Current readback has no pinned transaction snapshot/LSN. Audit was split into small query shapes due to rejection of one larger query; do not claim a single atomic snapshot.

## Repair disposition

**No INSERT/UPDATE/DELETE approved or proposed for direct execution.** The 25 canonical center episodes are already present, so insert count for the 25 *central* episodes is **zero indicated**, not 25. Other missing/extra episodes remain unproven for Lviv #3. No production JSON change is established for Kyiv 18; non-Kyiv production JSON is mostly aggregate not literal episodes. Exact DB mutation counts remain **NOT CERTIFIED**. No classification/event rebinding without separate proof; ensure producer won't revert any future authorized patch. C4/C5 and cutover still NOT PROVEN.

Next narrowly missing source evidence: only **2026-09-03, 04, 05, 06** for Lviv #3 if complete within-window verification is required and no other complete independent source proves the blank days. No need to reupload 7 received files or 18 Kyiv days. An Alerts.in.ua four-day export must cover correct Lviv raion / oblast geometry, cross-midnight records, and be immutable-hashed. This is not a request to overwrite data or a new research track.
