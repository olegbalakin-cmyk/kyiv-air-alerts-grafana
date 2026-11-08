# C6 DST readback after SELECT grant

**Physical readback PASS. Repair readiness BLOCKED. GLOBAL_CUTOVER=NO.**

On 2026-11-08 at 22:12:15.678–22:12:17.374 UTC, one authorized transaction used `c6_shared_reader_v2` on `br-bold-mode-b5rub8pq`, read-only compute `ep-calm-rice-b5073ypp`. SQL verified both current and session roles, database `neondb`, `REPEATABLE READ`, read-only state, replica recovery, and SELECT on all six required tables. Backend PID 716 and snapshot `509961:510976:` matched at the start and end. The previous 42501 blocker is resolved.

| Case | Fresh physical result | Write readiness |
| --- | --- | --- |
| Kharkiv | Wrong merged UUID, legacy ID and microsecond UTC endpoints match accepted evidence; both replacements absent | BLOCKED |
| Poltava | Wrong merged UUID, legacy ID and microsecond UTC endpoints match accepted evidence; both replacements absent | BLOCKED |
| Zhytomyr | Wrong merged UUID, legacy ID and microsecond UTC endpoints match accepted evidence; both replacements absent | BLOCKED |
| Cherkasy | Missing candidate absent; earlier valid UUID/legacy/UTC preserved | BLOCKED |

All seven candidates are absent by both legacy ID and exact city/AIR/UTC interval. Server-side comparisons used the original microsecond literals. Full row JSON retains timestamp precision; the connector's scalar timestamp rendering rounds down to milliseconds and must not replace those literals. The protected Cherkasy full current row is saved; historical byte equality of all metadata is not asserted because the pinned fixture contains identity and UTC endpoints only.

Four inbound episode FKs were catalogued. Searches of source observations, classifications, events and state snapshots found zero links to the three wrong UUIDs; downstream searches also checked legacy IDs in textual/JSON representations. No source observations exist on any of the four protected/target rows or in the bounded city/time window. One original ingestion-run before-image was captured for the three wrong rows. Its existence does not supply missing source-event lineage.

The result includes 165 constraints, 23 indexes, full columns of six required tables, and related-column inventory. No noninternal triggers, RLS policies, dependent episode rules or inheritance links were returned for the inspected scope; the six tables have RLS disabled. All bounded data queries stayed below their limit; the response reported no truncation. Additional non-FK relations, including `attack_event_sources.classification_episode_id`, were identified but not row-read. External or unregistered consumers are not certified absent.

The schema blocks the proposed repair contract. `alert_episodes` has 12 columns, no supersession/alias or counted-exclusion field, `episode_state IN ('open','closed')`, and canonicalization fixed to `alert-canonicalization-v1`. No episode alias/supersession relation appeared in the returned public catalog. Observation `duplicate_alias` and classification supersession have different meanings. Keeping the three old closed rows while inserting seven would leave ten counted candidates unless an independently verified exclusion contract is added. A safe repair and rollback using the current schema/consumer contract is **not established**.

Evidence:

- [Physical checks and catalog summary](after_grant_evidence.json)
- [Current verdict](preflight_verdict.json)
- [Exact statements submitted in the one transaction](after_grant_statements.sql)
- [Conditional repair and rollback gates](conditional_repair_rollback.md)
- Prior blocked attempt: [`c8261baa`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/c8261baa2c62a786df6939959b10a50d98757336).
- Accepted comparison: `C6-DST-UTC-01`, [`7265e40a`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/7265e40af6d012267ada515e9cac415f3e1e24b7); fixture blob `2caa8d5d4fd3a8934b7a3428b26b67642a4efcb3`, offline diff blob `8d698e5f1b843918cb4c42de45f7fc70f9547025`.

Full before-images and unmodified request/response are retained in an owner-private artifact, SHA-256 `d36bbc8c3f724c2726054d583e98bf6e14d82edefc6b2fe8ad1bd6a53c7735a3` (142,396 bytes), linked separately to the owner. Public Git contains no full row/run before-images or credentials.

Stopped after this single successful read transaction and catalog review. No DML, DDL, GRANT, source HTTP, writer, credential, deployment, PR #42/#44/#45 or production operation was performed. No history replay, parity, C2 export, JSON proof or browser QA was repeated. Resolve the specific lineage/exclusion contract in a separate scope before seeking write approval.

