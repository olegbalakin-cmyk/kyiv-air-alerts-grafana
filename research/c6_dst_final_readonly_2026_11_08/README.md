# C6 DST final four-case read-only preflight — BLOCKED (2026-11-08)

## Decision

**BLOCKED; GLOBAL_CUTOVER=NO.** The single owner-authorized read-only SQL transaction, explicitly routed to **`c6_shared_reader_v2`** on **`br-bold-mode-b5rub8pq`** via **read-only compute `ep-calm-rice-b5073ypp`**, failed with PostgreSQL **SQLSTATE 42501, `permission denied for table alert_state_snapshots`**. The batch requested `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY` and bounded SELECT/catalog queries only. A complete transaction result was not delivered; do **not** treat earlier SELECTs in this failed batch as independently verified, or claim a saved consistent snapshot or before-images. This was one attempt; **no retry or owner/privileged fallback**. No DML, DDL, grants, HTTP, C2 writer, production or release operation.

Neon control-plane metadata: project `green-cake-44216048`, branch ready; named role exists with password login; target compute type `read_only`. Metadata do not establish SQL privileges. The precise blocker is a denied required dependency read, not absent Neon infrastructure.

## Case verdicts (fresh physical confirmation)

| City | Accepted prior fault | Expected old physical UUID | 2026-11-08 verdict |
| --- | --- | --- | --- |
| Kharkiv | One false merge → two correct rows | `bb7d4952-52a3-45f8-a1db-13153c8f6ca3` | **BLOCKED** — current row and links not reconciled |
| Poltava | One false merge → two correct rows | `74ba1017-63af-4137-a5ba-246795613615` | **BLOCKED** — current row and links not reconciled |
| Zhytomyr | One false merge → two correct rows | `b40c570e-f9db-4c7d-b7e4-3f7769e12a95` | **BLOCKED** — current row and links not reconciled |
| Cherkasy | One missing interval, preserve the earlier correct `ff046d6c-fc7e-4cd2-9470-3e5433c3d582` | None | **BLOCKED** — no fresh presence/readback |

These UUIDs and the seven candidate UTC intervals come from **prior accepted** `C6-DST-UTC-01` evidence, not the failed 2026-11-08 transaction. Pinned inputs on the verified DST research branch:

- `fixtures/historical_correction_candidates.json` blob `2caa8d5d4fd3a8934b7a3428b26b67642a4efcb3`
- `proof/offline_machine_diff.json` blob `8d698e5f1b843918cb4c42de45f7fc70f9547025`
- Accepted checkpoint `7265e40af6d012267ada515e9cac415f3e1e24b7`, prior access evidence `04b0938d72ecfde675dc665a0a1268ee4d86f11d`
- New physical JSON proof [Actions 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) success with artifact `13619973574` — **not** a four-case dependency proof; PR #45 `3e08daf4` still draft.

## Expected arithmetic — not a fresh database assertion

Based on the pinned independent offline witness only: 3 incorrect merged rows superseded by 6 correct rows; 1 missing Cherkasy row added; **+4 counted episodes**, cumulative duration **−9,059,359,958 microseconds (−2 h 30 min 59.359958 s)**. Exact seven candidate legacy IDs, UTC endpoints and the expected protected Cherkasy before-image are in the pinned fixture/diff; none were recreated or reverified in Neon here. The 2026-10-30 physical readback reported zero links from the three wrong UIDs in only four tables. That **does not** establish absence of present-day source/provenance, non-FK, downstream or external dependencies.

## Manual-only next step

Use [`manual_only_readback.sql`](manual_only_readback.sql) **only after** read-only permissions are corrected through a separate authorized process. This file is a bounded `psql` script, not a workflow. Connect explicitly using `c6_shared_reader_v2` to **`ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech`** and database `neondb`. Supply its password through the interactive prompt only; no saved secrets. For example, in an approved, trusted environment:

```sh
PGSSLMODE=require psql -X -W -v ON_ERROR_STOP=1 \
  -h ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech \
  -U c6_shared_reader_v2 -d neondb \
  -f research/c6_dst_final_readonly_2026_11_08/manual_only_readback.sql
```

The script must run as **one** `REPEATABLE READ READ ONLY` transaction, first fail-closed on identity/replica and SELECT ACL checks, then capture exact full alert-row before-images, protected Cherkasy, seven candidate ID/UTC rows, bounded source observations and run provenance, classification/events/state references and catalog FKs/constraints/triggers/indexes/RLS/views/related columns. Store the output with restricted permissions as a protected before-image; do not commit source payloads with private metadata or passwords. Stop if permissions or identity are wrong; do not switch to `neondb_owner`, modify grants, create branches, or repeat queries in this scope.

A successful script is **necessary but not sufficient** for write approval. An operator must review the full catalog for other non-FK/JSON/external consumers; no finite SQL read can establish absence of unregistered external readers.

## Repair / rollback design (NOT executable or approved)

Only after a fresh consistent readback proves all current rows, candidate absence, complete source observation lineage, incoming/outgoing relationships, triggers/constraints and permitted alias strategy:

1. Secure complete before-images for all three bad rows, existing valid Cherkasy, their source/run/classification/event/state dependencies, referenced rows and exact relevant catalog definitions; pin a corpus/input SHA and current migration schema.
2. Prove no drift on old UUID+legacy+UTC quadruples and no seven candidate IDs or city/time duplicate rows. Fail if source evidence is missing or any other dependency is discovered.
3. In a **separately approved**, serializable/guarded write transaction, create seven new canonical identities with genuine provenance, *retain* the three existing UUIDs and legacy IDs in an auditable supersession/alias lineage, and exclude only the three superseded parents from counted current results. Never delete or rewrite historical UUIDs in place. If schema cannot represent supersession without DDL / consumer change, return **BLOCKED**, not a fabricated SQL COMMIT.
4. Pre-COMMIT checks: exact 3→7 identity mapping, `+4` active-counted episode delta, `−9059359958` µs time delta, valid Cherkasy unchanged, no invalid overlaps, no unrelated row change, all existing source/classification references accounted for. Abort on any mismatch.
5. Distinct rollback gate: keep all old rows and a versioned mapping of *new* UUIDs; on separate authorization, deactivate new seven, reverse exactly those three supersession records, restore audited downstream projections from preserved before-images; verify hashes and counts. Do not cascade-delete dependents. If reverse linkage is incomplete, stop rollback and preserve audit trail.

No unconditional DML SQL is safe to emit with the current `42501` gap. The UTC recurrence prevention patch (not applied) in `site-prod` `apply_ukrainealarm_bridge.py:union_alerts()` is narrowly:

```diff
-    for alert in sorted(alerts, key=lambda item: item.start):
-        if not merged or alert.start > merged[-1][1]:
+    for alert in sorted(alerts, key=lambda item: item.start.astimezone(timezone.utc)):
+        if not merged or alert.start.astimezone(timezone.utc) > merged[-1][1].astimezone(timezone.utc):
             merged.append([alert.start, alert.end])
-        elif alert.end > merged[-1][1]:
+        elif alert.end.astimezone(timezone.utc) > merged[-1][1].astimezone(timezone.utc):
             merged[-1][1] = alert.end
```

This is a **proposal**, not production code or a tested promotion. The pinned accepted source-only replay already checked the DST mechanism; don't repeat parity/browser/CSV/C2 export/physical JSON proof. No production or site-prod changes in this branch.

**Next gate:** separately authorize a way to restore **read-only SELECT on `public.alert_state_snapshots` for the existing reader** (or provide an equivalent already-authorized complete dependency readback), then reauthorize one fresh manual-only four-case transaction. Until then **BLOCKED; GLOBAL_CUTOVER=NO**.
