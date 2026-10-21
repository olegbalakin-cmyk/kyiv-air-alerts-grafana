# H2 catalog-only inspector: single-session fail-closed protocol

**DOCUMENTED PROCEDURE — NEVER EXECUTED IN THIS PACKAGE.** No DSN, hostname, password, token, secret value, Neon API or live SQL is supplied. The only executable code delivered is the **offline** manifest/receipt-shape verifier. This protocol is not permission to connect, provision a role or run queries.

## External owner authorization and route gate (BEFORE opening any connection)

An independent operator and reviewer first sign off the exact current project (`green-cake-44216048`), branch (`br-bold-mode-b5rub8pq`), database (`neondb`), current compute ID and its **actual** FQDN, with trusted control-plane evidence timestamp, immutable digest and provenance. `ep-calm-rice-b5073ypp` is historically documented, **not a current pin**; no FQDN is known here. Never substitute the default `br-wandering-sunset-b5835alw`, writer endpoint, pooled proxy or a guessed `*.neon.tech` host. Confirm the role `h2_catalog_inspector_ro` exists, authenticates without privileged membership/ownership/data rights, and is strictly bound to the inspected target. Independently approve allowed metadata/retention, possible compute wake, client cancellation behavior, and **new explicit user approval**. If any field is UNKNOWN, expired, inconsistent or denied: **NO CONNECT / NO-GO**.

The read-only path should use a single direct PostgreSQL connection to the attested compute with TLS hostname verification (`verify-full`), no pooling/session multiplexing, autocommit disabled and no automatic retry/reconnection. The SQL role must not be `neondb_owner`; `READ ONLY` alone is not least privilege. The client must transmit **one exact pinned SQL statement per request**, with no multi-statement string expansion, parametrized arbitrary object names, dynamic queries, `SET ROLE`, query-planner introspection, user-defined function calls or database exports. Client and transport may emit no DSN/connection URI, environment dump, credentials, or raw connection strings to logs or receipt.

## Server and client bounds

- **Connection**: one; transactions: one; catalog `SELECT` executions: 15 (G01 twice, G02–G14 once); overall SQL statements: **21** including `BEGIN`, four approved `SET LOCAL` commands and `ROLLBACK`. Neither a failed operation nor a reconnect may trigger a second transaction.
- **Server**: `statement_timeout=15s`, `lock_timeout=5s`, `idle_in_transaction_session_timeout=30s`, `transaction_timeout=45s` (PG18 feature). Validate exact server readback: `transaction_read_only=on`, isolation `repeatable read`, timeout values nonzero and **no weaker** than configured. Reject if `SET LOCAL` fails, transaction becomes aborted, or one of the settings is not supported. Do not disable/reconfigure until end.
- **Client**: hard wall deadline 60 seconds, fail-closed cancellation and close; limits at most 180 returned rows and 65,536 sanitized UTF-8 JSON output bytes overall, at most 8,192 bytes/cell. Any row cap hit **is incomplete and STOP** unless the query specifies exact expected cardinality; never silently clip/truncate and call it PASS. Restrict max 1 connection, 0 retries, 0 writes, 0 Neon API calls, 0 application rows, 0 exported datasets.
- **Consistency**: one `REPEATABLE READ` transaction pins the PostgreSQL MVCC snapshot from the first actual query. Record built-in `pg_current_snapshot()` in the first and last G01. A changed token, read-only state, database, effective/session role or guard setting is a **hard STOP**. A stable snapshot does not itself identify the Neon branch; independently signed host→branch mapping is essential.

## Exact wire order

After authorization, execute **only** the following transaction controls plus exact bytes of `G01`–`G14` from `H2_READONLY_QUERY_MANIFEST.json`; verify each SELECT SHA-256 locally before sending. No SQL here is submitted by this deliverable.

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '5s';
SET LOCAL idle_in_transaction_session_timeout = '30s';
SET LOCAL transaction_timeout = '45s';
-- G01 = first guard, must pass before any substantive catalog query
-- G02, G03 = proposed inspector role and direct membership, must pass immediately
-- G04..G14 = pinned catalog-only queries, each with per-query caps and schema
-- G01 = second guard; role, database, snapshot, isolation and limits unchanged
ROLLBACK;
```

The comment lines are explanation **not wire SQL**. Protocol executor uses the exact `session_sql_order` from the JSON. **`ROLLBACK` is required even on a clean run; never `COMMIT`.** On any exception/timeout/unexpected or incomplete result: attempt server cancellation immediately; if still reachable issue bounded `ROLLBACK`; close connection regardless. A connection lost before an acknowledged rollback is **ROLLBACK UNVERIFIED**, not a zero-mutation proof; stop and escalate to independent operator. No retries, alternate roles, writable fallbacks, or expanded query limits.

## Contract-specific result checks (not silently relaxed)

| Query | Required guard/interpretation |
|---|---|
| G01 (twice) | Exactly one row each; database `neondb`, current/session role exactly `h2_catalog_inspector_ro`, both read-only `on`, both isolation `repeatable read`, PG major 18, timeouts as approved, same snapshot token. These SQL observations are not a branch ID attestation. |
| G02 | Exactly one role row with `rolcanlogin=true`; SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS false; `rolinherit` must be assessed with G03 and approved least privilege. No owner alternative. |
| G03 | **Zero** inspector direct membership edges accepted. Unexpected `INHERIT`, `SET`, `ADMIN`, or role grant edge fails closed. If PG visibility limits prevent proving this, STOP. |
| G04 | Exactly the **eight** named objects, correct namespace, metadata kinds/owners; inspector must not own any. For all eight, preserve **both** physical `relacl IS NULL` and raw text. Seven ACL physical differences must not be masked or treated as Option B permission. Missing or ninth relation → STOP. |
| G05 | Exactly public schema metadata; owner not inspector, raw `nspacl` captured. Unexpected schema privilege requires independent review. |
| G06/G07 | Exactly 18 ordered view columns; one view definition consistent with accepted DISTINCT ON contract. A nineteenth column, missing dependency or ambiguous definition → PARTIAL/STOP, not promoted to success. |
| G08/G09 | Every bounded returned selected index/constraint record retained. At `LIMIT` sentinel (33) STOP; a missing enforcement invariant (193/197) is reported as existing MISMATCH, not waived. |
| G10 | Eight exact objects; all SELECT/INSERT/UPDATE/DELETE effective privileges for inspector must be **false**. Missing rows, unexpected true, or obscured effective role grants → STOP. |
| G11 | Explicit raw default ACL + NULL status for allowed schema/owner; at sentinel cap 13 STOP, unknown default privileges → PARTIAL. |
| G12 | Catalog metadata only for built-ins `pg_advisory_xact_lock`, `hashtextextended`, `gen_random_uuid`; never invoke them. Compare desired signatures, extra overloads retained; at sentinel 9 STOP. Function availability ≠ actual writer invocation proof. |
| G13/G14 | At most catalog entry for `plpgsql`, exactly three named settings. Any missing settings or uncertain extension scope reported PARTIAL; this is **not** a complete all-extension or writer-default census. |

Do not use `LIMIT` to conceal findings: a query reaching its sentinel limit must fail closed. For required exact eight relation checks use set equality and duplicates check, not rowcount alone. If a catalog access is denied, result format/schema differs, result is clipped, physical ACL NULL status lost, or a result column exceeds 8 KiB, stop the session with a **specific incomplete/error code**; never raise limits interactively. One incomplete contract makes I4 PARTIAL; safety/identity violations make overall NO-GO.

## I1–I7 and evidence receipt

This package's offline tests validate **specification shape** only. Actual later inspection must produce an independently reviewable sanitized JSON receipt with: UTC start/finish; approved operator/user decision references (not credentials); fresh nonsecret control-plane mapping evidence plus owner/reviewer and timestamp; pinned Git SHA and 14 query hashes; exact ordered SQL statement IDs, per-query observed column names, raw metadata rows (bounded), rows/UTF-8 bytes, redaction decisions, row/result SHA-256, truncation errors; `current_user`, `session_user`, database, two `transaction_read_only`/isolation/timeouts/snapshot checks; role/membership/effective rights; non-masked raw `relacl` NULL bits+text; explicit ROLLBACK acknowledgment, cancellation attempts, total cost/time, and signed **zero attempted DML/DDL/API/role switch/secret** attestation. Unknown logs are NOT a proof of absence of side effects.

Require a second reviewer to verify route and receipt hashes against the authorized manifest/immutable commit, check all data caps/schemas, compare raw physical ACL evidence without normalization and classify each I1–I7 **PASS / PARTIAL / FAIL / UNVERIFIED**. The overall maximum result is *bounded catalog snapshot accepted for review*; never an H2 migration or production readiness PASS. Publish only sanctioned sanitized catalog rows with an agreed retention policy; no DSN, password, token, user/source/application rows, or function bodies. **No actual receipt exists in this offline package**. `H2_INSPECTOR_NEGATIVE_CONTROLS.json` and `H2_INSPECTOR_INDEPENDENT_REVIEW.json` are synthetic/static proofs, not Neon results.

## Immutable phase boundary

Original contract ledger stays **203 structural MATCH / 3 DB-invariant MISMATCH (193,196,197) / 7 runtime UNVERIFIED (183,190,206,210,211,212,213)**, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`, `H2_ACL_OPTION_B=BLOCKED / PROPOSAL_ONLY`. Any data-level historical parity or writes require new approval. **Actual Neon read-only/disposable both remain BLOCKED/NO-GO.**