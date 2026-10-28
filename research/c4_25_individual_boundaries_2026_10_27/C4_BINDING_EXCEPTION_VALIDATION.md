# C4-E1 — binding-only exception validation

**Verdict: PARTIAL. Owner decision proposed: accept exactly 24 non-conflict classifications as individually named exclusions from exact canonical-parent binding parity; keep Kharkiv #6 blocked.** This is not C4 PASS and not permission for a Neon reader cutover.

## Evidence and scope

Read current main coordination files and reviewed proposal commit `a653f030c791a9cd358e8ba6d1cad27fc3eab1d9`, previous owner review `2a11a637a76ab3f9c862e9a62177848ff0dfafa0`, accepted closure criteria `4cc20029466795f16b0c648d84acbf6d50e75c66`, and frozen binding contract blob `e9dcbdf21551ca086fbf096138f885f453a8c2b0`. Observed `main@26504ef8fbae5e620a1a4bc531751380b745ca5a` and `site-prod@a2d593c51830a62516d8907b6f55aae1b05e8948`. Neon: `green-cake-44216048/br-bold-mode-b5rub8pq/neondb`; physical read-only compute `ep-calm-rice-b5073ypp`; PostgreSQL 18.6, `transaction_read_only=on`, `pg_is_in_recovery=true`.

The frozen contract permits `UNBOUND` classifications with NULL parent; `BOUND` requires exact deterministic city/AIR/closed parent ID, microsecond-precision start/end, and uniqueness. No nearest-time admission is permitted. The proposal is *not* an approved exception yet.

## Independent SQL readback

- 25 unique `classification_uid` rows exist, with all 25 original historical IDs, 25 frozen classification keys, 25 verdicts, and 25 `UNBOUND/NULL` statuses matching proposal and prior evidence.
- Exactly **16 NO_CONFIRMED_EVENT**, **7 NEEDS_REVIEW**, **1 STRICT_EVENT_POSITIVE**, **1 SENSITIVITY_EVENT_POSITIVE**.
- **14 persisted source memberships** across nine classification rows; 25/25 per-case source-link counts agree with the previous review. All 25 must remain in the historical denominator and in classification/verdict/evidence/source/event semantic parity; the only proposed waiver is exact parent-FK admission. Full independent H1/H2 field/hash parity remains unproven.
- Both events remain `ACTIVE`, each attached to the correct historical classification and with `UNBOUND/NULL` parent: Zaporizhzhia #5 `ef34834b-0513-4351-8839-d866a0e76e99`; Kharkiv #6 `dc3a63ec-d9f8-412c-b0a1-09dd9398b27b`. Per-case IDs match 25/25 including the two positive records.

## Reader SQL trap: independently reproduced

For the exact 25 classification UIDs:

| Query shape | Classification rows | ACTIVE events |
|---|---:|---:|
| Direct table read | 25 | 2 |
| `LEFT JOIN alert_episodes` on optional parent UID | 25 | 2 |
| `INNER JOIN alert_episodes` on optional parent UID | **0** | **0** |

Joining the two ACTIVE events to their source memberships produces **7 rows** (6 + 1), although `COUNT(DISTINCT attack_event_uid)=2`. Safe future Neon readers must root events on event UID/classification ID, use optional LEFT JOIN for parent metadata, and preaggregate or distinct source links. This is a demonstrated counterexample to unsafe queries; an actual end-to-end future reader has not been proved.

## Exact comparable JSON–Neon count diff

At the pinned site-prod head, read `data/dashboard_data.json` blob `70c450f37b91da25c8f45b0436fa39a37979e0b5` and literal Kyiv `alerts_combined.json`. Count is monthly local-Europe/Kyiv alert starts in site JSON versus closed canonical episode start-month in Neon:

| City / start month | site-prod JSON | Neon | Difference |
|---|---:|---:|---:|
| Kyiv 2025-03 | 35 | 35 | 0 |
| Kyiv 2026-09 | 190 | 199 | **+9** |
| Kharkiv 2025-03 | 147 | 147 | 0 |
| Kharkiv 2026-09 | 257 | 257 | 0 |
| Lviv 2026-09 | 6 | 6 | 0 |
| Sumy 2026-09 | 236 | 236 | 0 |
| Zaporizhzhia 2026-09 | 152 | 152 | 0 |

For Kyiv September, **all 190 JSON exact start/end pairs exist in Neon**, plus nine extra minute-rounded parent rows from September 29–30; none belongs to the 18 candidate parent UIDs proposed for this exception set, and 18/18 proposed Kyiv candidate intervals appear literally in JSON. Therefore a naive Neon parent-based metric gives a different count even if the 25 proposed historical exception records are untouched. This separate projection parity defect must be resolved before reader cutover, without inferring a reason beyond observed rows.

The dashboard JSON does **not** expose the 25 historical classification verdicts, source memberships, or these two historical ACTIVE attack events as comparable metrics: each of those comparisons is **NOT_EXPOSED**, not zero or equality. Matching monthly counts for other cities do not prove whole-series semantic parity.

## Replay and remaining blockers

Existing uniqueness constraints on classification keys, source-link keys and attack event city+historical ID guard ordinary duplicate persisted keys, and inspected live writer code requires exact parent matching. But no naturally scheduled post-proposal ingestion or future consumer rerun was carried out; long-term `UNBOUND/NULL` stability and no duplicate reader output are **PARTIAL / NOT PROVEN**, not asserted PASS. The parent-only normal C2 producer does not itself rewrite historical classifications. No DML, DDL or workflows were invoked.

**Kharkiv #6 source conflict remains open**: Alerts.in.ua end `2025-03-06T03:03:45Z` versus current canonical/Vadimkin end `2025-03-05T19:47:55Z`, a **7h15m50s** discrepancy. Keep the classification and its positive event; do not use a parent parity waiver to declare time-source equivalence.

## One owner decision

**Approve only the 24 explicit non-conflict UUIDs in the accompanying JSON as exceptions to exact parent-binding parity, not as exemptions from semantic history. Block #6 until separate historical source adjudication.** This permits the rest of C4 parity evaluation to continue without creating a new lineage platform or rewriting the 25 current parents. Future Neon reader/aggregation, September Kyiv deduplication/parity, replay behavior, other C4 semantic invariants and C1–C3/C5–C10 retain independent gates. **C4 remains NOT_PROVEN; no cutover.**

Read-only Neon SELECTs only. No changes to production JSON, attack events, verdicts, canonical episodes, deployments, or coordination files. Machine-readable per-case results, full 25 UUIDs and nine extra Kyiv UID list are in `c4_binding_exception_validation.json`.
