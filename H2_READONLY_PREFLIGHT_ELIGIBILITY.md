# H2 narrowly scoped Neon read-only preflight — eligibility, not authorization

**2026-10-21 · Offline / Git-only coordinator decision proposal.** This document supplies a safety case and a proposed inspection contract. It does **not** authorize or execute Neon access, alter a secret/role/workflow, accept ACL Option B, run a disposable database, or change production/WIP. Review alongside [H2_REMAINING_BLOCKERS.md](H2_REMAINING_BLOCKERS.md) and [H2_BLOCKER_MATRIX.json](H2_BLOCKER_MATRIX.json).

## 1. Decision now

**Eligibility-review recommendation: GO to offline coordinator review only. Actual Neon read-only access: NO-GO until separately, explicitly authorized after the below narrow safety conditions are accepted.** Current *formal* gate stays `H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO`.

The essential distinction: a non-mutating, bounded catalog inspection does **not** first require successful database modification, full historical parity, 25 historical parent dispositions, user acceptance of a seven-relacl rollback exception, R6 WIP activation, production writer routing or cutover. Carrying those late-stage conditions backward would create unnecessary circularity. It **does** require a precisely pinned target, a limited authority/read-only execution mechanism, a vetted query/output plan, a way to stop on violations, and a fresh, separate owner authorization.

### Five stage partitions (normative for this proposal)

| Stage | Required now versus deferred |
|---|---|
| **Must resolve offline before read-only Neon access** | Current coordination/evidence pin; exact selected project/branch/database and approved access route, inspect-only principal or expressly accepted equivalent control; nonsecret provenance and human responsible operator; precise SQL/catalog allowlist, limits/logging and rollback plan; separate explicit authorization. `OFF-01/02/03`. |
| **Can be verified only through separately authorized read-only Neon access** | Live role/ownership/ACL and `pg_class.relacl` reality, precise view/function/search_path details, live inspector privileges and server-enforced session settings, current 213 contract catalog drift, optionally historical parity under its *own* read-only scope. `READ-01/02/03` and original `183,190,206,210,211,212,213` (catalog portions only). |
| **Must resolve before disposable Neon write testing** | Actual *writer* login/reference binding and role/member/owner guard topology, disposable branch/cleanup/fencing and precise permitted write tests, safe 007/008 physical ACL evidence treatment; proposed DB hardening plan. `ROLE-01/02`, `TEST-01`, `ACL-01`; no experimental SQL now. |
| **Must resolve before production cutover** | `193/196/197` DB guarantees or explicitly accepted proven alternative, full eligible write/commit/race/rollback proof, C2–C7 and C9, exact 25 UNBOUND dispositions as part of C4, C5 final-authority separation, R6 effective old-job per-sink fencing *if* operational WIP paths are touched. |
| **Independent track / not a blocker to strictly read-only inspection** | R6 private-receiver/running-token work, WIP activation, production/casualty/static publication continuity, historical frozen expected projections assembled offline, future postcutover C8/C10. These have their own gates and must not be absorbed into an H2 inspection command. |

## 2. Already accepted scope and why it is insufficient for a write

Current `main` is [coordination SHA `2c09baf1`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2c09baf1e186b8a5af0fd0a227827e3e87b979ad) (verified from GitHub, no newer main checkpoint when this branch was created). Current observed other refs: `site-prod@7c9b81e35325b24f5201018e85b2989728876abd`; operational `multicity-wip-2026-09-16@bc87b712b2861621e943f0c05bf6e92afcfe374f`. These refs may move independently; recheck on later actual authorization.

- [H11/R09 integrated PG18.6 A/B](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/327caba41942346abc630d7f567d8b0ddc814ae8/research/h2_integrated_failclosed_checkpoint_2026-10-21.md), [original run 39499796916](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39499796916), [independent evidence 39500629652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39500629652): synthetic 20/20 + 144/144 A/B fail-closed tests accepted. Real Neon app/owner/guard membership and DDL authority **remain unknown**.
- [Actual late-fault `008`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/6084ec1dfc6e885ca35e32bec34c1dcfe67d6ad4/research/h2_008_late_acl_2026_10_21/BOUNDED_RESULT.md), [run 39504096121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39504096121), [independent 39504652475](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39504652475): atomic sampled rollback accepted, **overall PARTIAL** due physical ACL representation.
- [Seven-relacl decision](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8b16053e031fe84f0b303ad531956b0f319ffbc5/research/h2_acl_physical_dossier_2026_10_21/DECISION_DOSSIER.md) and [independent freeze/catalog consumer audit](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/566e827dead199210d33f5bc99c5d7f66bbaef80/research/h2_acl_evidence_consumers_2026_10_21/REVISED_DECISION_DOSSIER.md), [run 39565210464](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39565210464), [Git-only verification 39580004681](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39580004681), [source audit 39579882913](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39579882913): semantic samples PASS BOUNDED; exact physical restoration not established; no generalized equality, no permission to mask the seven physical deltas. Option B is **BLOCKED / PROPOSAL_ONLY**, remains subject to separate future user decision.
- [Original 213-contract v5](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/198a4dac76ddb1604a813dc286cb28ec1f6d83e7/research/h2_neon_schema_contract_matrix_v5_runtime_2026-10-18.json): **203 structural MATCH / 3 observed database-invariant MISMATCH `193/196/197` / 7 runtime UNVERIFIED `183/190/206/210/211/212/213`**. Those labels do not change because of this offline audit.
- Prior [read-only Neon catalog freeze](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/380e16f4d8e861a30ba899921a7dbc33d5077bd5/research/h2_live_neon_catalog_readonly_verification_2026-10-19.json) with [Git-only run 39273063710](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39273063710) established selected U1–U7 catalog facts on PostgreSQL 18.6, **not live writer role or COMMIT**. It must be treated as an old read-only snapshot; no Neon access in this task.
- Historical [parity](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/3d10cb3c3509c6945f9c9f3cdf02d8cfae46d143/research/neon_frozen_h1_h2_semantic_unbound_reconciliation_2026-10-11.json) was `PARTIAL`: C4/C5 `NOT PROVEN`; 25 `UNBOUND` require individual dispositions. No historical repair/backfill should be coupled to preflight.

## 3. Target definition and two different principals

The independently accepted [Neon authority **design only**](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/eabdd380694abe045bf2cd15b7b83d7d1bb0d965/research/neon_production_authority_contract_2026-10-10.json) names:

| Parameter | Proposed read-only catalog inspection target, not active authority |
|---|---|
| Project ID | `green-cake-44216048` |
| Branch ID | `br-bold-mode-b5rub8pq` (permanent populated shadow) |
| Database | `neondb` |
| Alternative default/primary | `br-wandering-sunset-b5835alw` named `production`, **not interchangeable**; historical audit showed different/missing attack-event schema |
| Prior inspected read-only compute | `ep-calm-rice-b5073ypp` (historically attested, must not assume current availability, privileges or endpoint identity) |
| Prior write compute label | `ep-still-violet-b5bg6mhp` (historical metadata only; **not** an inspection target by inference) |
| Intended future writer binding | main `.github/workflows/explosion-monitor-wip.yml`: `ATTACK_EVENT_DATABASE_URL ← secrets.PHASE1_PROD_SHADOW_DATABASE_URL`; normal `update-netlify-site.yml` parent/other paths also use this secret name. The secret reference is evidence, **not** a read-only permission or login attestation. |

**Inspector principal** and **future writer principal** have different proof obligations. The inspector should be a dedicated or existing independently attested least-privilege **read-only** SQL identity without role/ownership/DDL escalation. An alternative relying on a stronger existing identity requires a *specific, separately accepted compensating enforcement design*; simply promising to issue SELECTs is insufficient. If providing a dedicated role would require a new Neon role or secret, it is a **separate future write/control-plane task**, not permitted within this audit and not automatically authorized by this report.

The older [one-time secret-metadata verification (run 39309315728)](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39309315728), job `118254518270`, at `main@3810d262`, reported `USERNAME_MATCH=YES` for `neondb_owner` and endpoint-first-label/database checks for the *then-read secret reference*, without printing a DSN. The temporary check workflow is now retired; this **does not** prove the active or future runtime job used this SQL user, currently has matching grants, or connects to the chosen branch. **Do not read, echo, rotate or change secrets** to close this at eligibility-review stage. Later writer principal proof must use non-secret attestations and separately authorized read-only role checks.

## 4. Proposed first permitted inspection — fail-closed catalog-only protocol

This is a **design**, not an instruction to connect or run now. Nothing below grants access.

### A. Offline prerequisites to be separately accepted

1. Freeze the current `main` checkpoint/ref and accepted PG18/ACL/canonical schema proof IDs; publish the exact inspection target **project + branch ID + database + endpoint/compute + named inspector principal**, non-secret role provenance and responsible operator. Any unverified routing to default branch is a stop.
2. Independently approve access mechanism, read-only privileges or a formally accepted equivalent guard, one bounded connection, literal **SELECT/catalog/SHOW-only statement allowlist** and expected results. No inherited/SET ROLE/owner-powered write path is assumed harmless. No secrets in artifacts, logs, prompts or URLs.
3. Preapprove result classes and retention: minimal role flags, object names/owners, `relacl` representations, ACL/grant bits, named required functions, view definition, indexes/constraints and `current_user/session_user`. Avoid fetching whole application tables, source text, personal/sensitive rows or large catalog payloads in the **first** inspection. Data-level C4 requires its **own separately scoped** read-only approval.
4. Confirm a runner/connector can actually enforce **server-side READ ONLY** transaction, target identity, statement-level timeout, query cancellation and explicit rollback; do **not** rely on client “SELECT only” metadata as enforcement. If the access path cannot enforce/read back this state, report **STOP / NO-GO**. A past non-READ-ONLY connector audit is not a substitute.
5. Obtain **explicit user authorization** for that pinned scope and no more. Absence of approval is a hard stop.

### B. Exact permitted behavior after, and only after, that approval

- One pinned connection to the named inspection target with least privilege. Begin a transaction with `REPEATABLE READ READ ONLY`; for the **first identity/guard statements**, independently read the server's `current_user`, `session_user`, `transaction_read_only=on`, `transaction_isolation`, database/branch/endpoint evidence and `search_path`. Abort/rollback before other reads if any field mismatches. Database or role identity that cannot be independently confirmed is **NO-GO**, not a guess.
- Conservative bounded limits, proposed as **`statement_timeout ≤ 15s`**, **`lock_timeout ≤ 5s`**, fixed maximum rows/bytes and a maximum statement count to be specified in an approved query manifest. Prefer exact catalog filters to exploratory full-table scans. Do not obtain locks for migration, call user-defined/security-definer functions, run data-changing CTEs, `EXPLAIN ANALYZE`, `SET ROLE`, `CREATE/ALTER/DROP`, DML, `GRANT/REVOKE`, write-privilege probes or control-plane APIs.
- Query catalog/view/role facts for only eight canonical relations in the [contract matrix](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/198a4dac76ddb1604a813dc286cb28ec1f6d83e7/research/h2_neon_schema_contract_matrix_v5_runtime_2026-10-18.json) and 007/008 affected objects. Include seven relations with **actual raw** `pg_class.relacl` NULL-vs-explicit values without suppressing, normalizing or accepting those differences. Examine `pg_roles`, `pg_auth_members`/permitted membership views, schema/tables/columns/functions/default ACL, guard ownership and relevant schema CREATE/GRANT/SET/inheritance pathways, within inspector visibility.
- If a catalog is inaccessible, a privilege is unexpected, a role could assume unsafe authority, transaction state is writable, or the branch identity is ambiguous, **record incomplete, ROLLBACK and stop**. Do not escalate identity or auto-expand query scope. At end, explicit **ROLLBACK** (not COMMIT), independent zero-attempted-write audit and immutable receipt with metadata, SHA, role/branch assertions, counts, query hashes, UTC timestamps, bounded classifications and unresolved items only. Never publish a DSN/token.
- Do not wake or mutate separate production Neons or any other branch as a fallback; connection effects such as a compute wake must be understood and expressly covered in the later owner-approved access scope if unavoidable.

### C. Concrete preflight acceptance outputs (all must pass for a *bounded read-only catalog finding*)

| Criterion | Pass condition | Fail result |
|---|---|---|
| **I1 route identity** | Project/branch/database and inspected endpoint attested to the pinned allowlist; not an implicit default switch | STOP / no queries beyond guards |
| **I2 identity and effective permissions** | Independently attested observer identity and schema/role read capability within approved least-privilege or compensating-control policy; no unapproved role escalation | STOP; no SET ROLE |
| **I3 server-enforced read-only** | `transaction_read_only=on`, `REPEATABLE READ`, same snapshot as appropriate, statement/lock limits; explicit ROLLBACK | STOP; no equivalence verdict |
| **I4 catalog coverage** | Exact U1–U7/213 rows requested by manifest, name/owner/view/function/grant/DDL facts and seven raw ACL deltas preserved. No blanket promotion of runtime UNVERIFIED based on catalog alone | PARTIAL, with exactly enumerated missing/uncertain objects |
| **I5 resource and privacy scope** | Statement/row/byte/time caps met; zero business-table payload extraction for catalog phase; no secrets; no SQL/API outside manifest | STOP and source-aware incident note |
| **I6 source and readback** | Original query/result manifest, commit and snapshot identity, independent Git-level evidence verifier/readback where viable | `UNVERIFIED`, not accepted PASS |
| **I7 no mutation/authorization inflation** | No Neon DML/DDL or branch changes, no Secrets changes, no WIP/prod/R6 actions; authorization counter limited to explicit read-only scope only | Hard NO-GO / audit failure |

**Interpretation:** success on I1–I7 can certify only a **bounded current catalog/role snapshot**, with dated metadata and its own acceptance review. It cannot certify physical rollback restoration, production writer durability, DB-enforced `193/196/197`, ACL Option B, or production migration. The historic `203/3/7` baseline remains until a separately accepted reconciliation formally updates each affected row.

## 5. Subsequent distinct and minimal tasks

The following ordered tasks are *recommendations*; each step that reads Neon or writes any environment needs its own authorization and current preflight. Do not automatically create jobs/workflows or perform the next step.

| Order | Task with minimal acceptance criterion | Depends on | Authorization boundary |
|---|---|---|---|
| **1** | Coordinator reviews this offline eligibility and blocker dossier. Verify `main` and new accepted checkpoints; accept/reject scoped scope, stage model and selected inspector approach. | This branch's three files, verified earlier run/artifacts | **Offline GO-to-review only**, not access |
| **2** | Pin non-secret inspector route and guard-query manifest. Freeze exact one-database connection plan, role/branch assertions, bounded catalog output, error/abort and receipt hashes. | 1 + `OFF-01..03` | Offline; if a new role/connection must be provisioned, separate authorization required |
| **3** | Obtain explicit authorization; run **catalog-only read-only** I1–I7 once. Report each ordinal and real ACL/role, no writes. | 2 + fresh refs/roles; actual preflight readiness separately changed only after owner acceptance | **NEW explicit read-only authorization**, absent here |
| **4** | Offline finish complete historically accepted H1/H2 fields and episode/parent contracts; only after separate approval run exact **read-only** C4 source/parent/canonical comparison on pinned snapshot. Decide every one of 25 UNBOUND individually; no mass repair. | Frozen H1/H2, field-authority proofs, 3 for current data and clear query scope | Separate read-only data-inspection authorization; NO backfill |
| **5** | Prepare DB-only `193/196/197` invariant DDL/role design, physical seven-relacl rollback strategy or explicitly pending Option B user decision, and pinned writer credential **nonsecret** binding. Freeze testing matrix with exact fail-closed negative cases and cleanup. | 3–4 role/topology and schema evidence, integrated H11/R09 + 008; no assumption Option B accepted | Offline proposal, then separate disposable-write approval |
| **6** | In separately authorized disposable Neon only, test real principals, 007/008, DB-only bypass negatives, two-session CAS/COMMIT/idempotent ACK/rollback under full schema; reject any unexpected physical catalog delta. | 5 + isolated branch/fencing and owner-approved writes | New disposable Neon test authorization; not covered by 3/4 |
| **7** | Separate R6-led old-SHA/external-sink containment and live registry proof **if actual WIP/cutover requires stopping or demoting writers**. Preserve protected production updater/casualty side effects. | Independent R6 security controls, private ruleset/server-side denial problem | **R6 operational change authorization**, not covered here |
| **8** | Only after C2/C3/C4/C5/C6/C7/C9, role/DB/ACL closure and 6–7 where applicable, present scoped cutover + recovery plan; later separate production decision. Run C8 after activation and record C10 only following independently accepted proof. | All prerequisite gates and current production refs | **NEW production/cutover authorization**. Currently NO-GO |

Historical C4 input is partially known: H1 **6,863** identities/verdict/QA accepted but source/event/key projection incomplete; H2 **19,542** aggregate counts, 18/18 city source hashes and bounded key recomputation accepted, full historically authorized source/field parity unresolved. An accepted [H2 field authority audit](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c23387942a6b3effafa612195582b1e56afe618f/research/neon_h2_19542_field_authority_containment_revalidation_2026-10-12.json) specifically identified **79 replay-derived-only** source-link inputs (including 63 timezone downgraded) among 1,429; keep frozen truth separate from any Neon result. The 25 parent-admission cases are [individually listed in the machine matrix](H2_BLOCKER_MATRIX.json), **not** the 25 H1 repaired decisions or the 74 source-worker unbound observations.

## 6. Separate GO / NO-GO decisions

| Gate | Recommended finding at this time | Change to accepted gate? |
|---|---|---|
| **Eligibility review (offline, no Neon)** | **GO TO COORDINATOR REVIEW** on this dossier as a **candidate**; possible to decide scope and safely prepare the later authorized request | **No**; research candidate only |
| **Actual read-only Neon access** | **NO-GO NOW**: missing accepted inspector identity/route/query procedure + no separate user authorization; if I1–I7 design is accepted, may become a narrowly scoped request | **None**: `H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO` |
| **Disposable Neon write testing** | **NO-GO**: live intended writer/topology/ACL treatment, isolation plan and DB-enforcement test design need closure + explicit write authorization | **None**: `H2_DISPOSABLE_NEON_TEST_READINESS=BLOCKED/NO-GO` |
| **WIP activation** | **NO-GO**: independent R6 already-running/queued credentials and receiver-side per-sink effects remain uncontained | **None**: `WIP_ACTIVATION=NO-GO` |
| **Production cutover** | **NO-GO**: database safeguards, C2/C3/C4/C5/C6/C7/C9 and operating/recovery plan unsatisfied, Option B not accepted | **None**: `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO` |

The current source of truth remains [main PROJECT_STATE.md](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2c09baf1e186b8a5af0fd0a227827e3e87b979ad/PROJECT_STATE.md) and [CHANGELOG.md](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2c09baf1e186b8a5af0fd0a227827e3e87b979ad/CHANGELOG.md). These research artifacts are returned for **separate coordinator acceptance**. Do not promote a decision, alter main documentation or grant Neon permissions on the strength of this report.
