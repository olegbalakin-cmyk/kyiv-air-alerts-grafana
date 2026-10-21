# H2 seven-relacl decision dossier — isolated PostgreSQL 18.6 A/B (2026-10-21)

**Research outcome: PASS BOUNDED semantic matrix, physical restoration NOT ESTABLISHED; Option B PROPOSED ONLY; Neon readiness NO-GO.**

## Preflight and immutable baseline

Current coordination `main` observed `d545840db95774c243add30e5c687de76e2a8072`; read current `PROJECT_STATE.md` and `CHANGELOG.md` before research. No superseding accepted H2 checkpoint. Research branch `research-h2-acl-physical-semantic-dossier-2026-10-21-gpt6` was created **from** accepted `6084ec1dfc6e885ca35e32bec34c1dcfe67d6ad4`. Original `007` and `008` SQL Git blobs `8dc20d11f28db2d8c2b6244b5c43e8bd23548abd`, `59eab59235f8aee14837ce7494649edba674e1ce` unchanged. Prior accepted H11/R09 integrated checkpoint `327caba41942346abc630d7f567d8b0ddc814ae8`; original actual 008 run `39504096121`, A/B original ZIP freeze and independent Git-only proof `39504652475`, retained intact. Full original source/evidence IDs remain pinned in the accepted 008 bounded report and main state.

## Executed isolated experiment

Primary final [run 39565210464](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39565210464), exact source SHA `0d156bcea786d015a307f7d0f4c8b49c5a3b5e63`:

| Copy | Job | Status | Checks | Actual overall research verdict | Artifact |
|---|---|---|---|---|---|
| A | `119105725015` | SUCCESS | 42/42 | PARTIAL_NO_EXACT_RESTORATION_PROVEN | `12330015114` SHA256 `84ab5cd39497bf43a43121a2b7a5cfaccb1fee73489693b5f3e7a123ad810b7f`, ZIP 4,052 bytes |
| B | `119105724906` | SUCCESS | 42/42 | PARTIAL_NO_EXACT_RESTORATION_PROVEN | `12328299979` SHA256 `10765402c4ef39d8552c3346e0aa702e26a401b9c6ec8d1de3bffeb960721ca1`, ZIP 4,058 bytes |

Execution: independent GitHub Actions PostgreSQL `postgres:18.6` service databases A and B, synthetic roles and data, no Neon secrets or access, ephemeral per-copy databases; `pg_dump` via matching `postgres:18.6` image. Baseline control includes three rows of canonical classification history (one two-revision chain, one independent root) before migration; `001` backfills two current heads; unmodified `007` then `008` leaves history identical and removes the heads registry as designed. Reapplying original schema/migration after rollback rebuilds exactly two corresponding heads. Canonical relation OIDs unchanged across control/rollback and later DDL; the only raw before/after successful `008` catalog discrepancies were precisely seven `relacl` fields.

Both A and B executed **43/43 successful transactional probes** of supported ACL/owner/DDL operations, without `relacl` becoming NULL: owner GRANT ALL, PUBLIC REVOKE, unrelated GRANT/REVOKE, owner REVOKE/GRANT, owner changes roundtrip, schema moves roundtrip, and `CREATE OR REPLACE VIEW` as applicable. **These probes explicitly end in transaction ROLLBACK, so they are discovery tests, not a committed restoration procedure.** No direct system catalog writes, no relation recreation, no OID change. This failure to find a method is **not** a proof of impossibility in PostgreSQL 18.6.

Direct, inherited, SET-only, PUBLIC, owner, GRANT OPTION and independent grantor tests compared the ACL item expansion, rights/with-grant-option matrix for 14 principals, relevant column/function/schema rights, role membership, default ACLs and future table/function creation and grants. Future owner transfer, column change, ACL grant/revoke, membership removal/restoration, lock-timeout DDL and normalized schema-only `pg_dump --no-owner` matched **within each copy**. Normalized dump A SHA256 `b8c6dd605f68a9dbe9fa6a5b367eac8dba08de7cd0fc1bba63253c38063a1fa1`; B SHA256 `7dc34681f0ea4d69f8121bde75dcbf7f27e0fa1c521dbe601759504e99eb9d10` (A/B independent fixture role names differ, so do **not** compare cross-copy hashes). A/B control-vs-rollback hashes equal. Post-future-DDL raw `relacl` drift was deliberately retained in observation instead of being masked as a physical PASS.

Historical prior [run 39565044383](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39565044383) **FAILED** due a new test assertion that incorrectly required raw ACL equality after future owner-change DDL; B reached 30/31. The test was corrected to compare owner/function outcomes and preserve raw ACL divergences separately; both new final jobs PASS. Do not relabel predecessor as passed.

## Option A — exact physical restoration

**NOT ESTABLISHED**. PostgreSQL [18 documentation](https://www.postgresql.org/docs/18/ddl-priv.html) explicitly says first GRANT/REVOKE instantiates an implicit ACL; it does not document a supported inverse operation back to NULL. A verified minimal supported exact-restoration procedure keeping canonical object identities **does not exist in this evidence set**. Avoid the unjustified assertion that such a procedure is mathematically impossible.

## Option B — narrow proposed semantic-only exception, NOT ACCEPTED

Only these seven `public.pg_class.relacl` changes may be proposed:

`alert_episodes`, `ingestion_runs`, `ingestion_checkpoints`, `current_ingestion_checkpoints`, `attack_event_classifications`, `attack_event_sources`, `attack_events`.

Each is `NULL` before → `{h2_schema_owner_test=arwdDxtm/h2_schema_owner_test}` after; no other raw catalog exception authorized. Effective ACL and grantor snapshots match on the tested principal matrix. The proposal **does not** assert general identity of all PostgreSQL metadata, nor grant authority for migration, Neon or prod.

**Residual risks:** raw `pg_class` comparisons and audit/data-diff tools that inspect `relacl IS NULL` will see a real difference; consumer SQL that treats NULL specially may behave differently. Future GRANT/REVOKE semantics under external role membership, privileges newly inherited from other external principals, ACL-related extension functions, trigger/runtime guard policy changes and combinations beyond exercised tests remain open. Future object privileges are not implied solely by normalized `pg_dump`. Catalog OIDs, owner, per-column grants, default ACLs, function and schema rights must remain part of the monitored equality contract.

**Mandatory guard/acceptance conditions:** (1) independently preflight all seven exact object identities, kinds, owners and ACL transitions; (2) independently validate external effective-role tree, membership SET/INHERIT and grantor chains against authorized Neon metadata before any test; (3) enforce fail-closed H11/R09 and SQL CAS, with no bypass or privilege expansion; (4) fingerprint history and heads before transaction and verify after commit/rollback; (5) monitor seven raw catalog fields explicitly and reject any additional difference, new PUBLIC or grant-option privilege, owner/role/default/column/function/schema ACL change; (6) rerun CAS/guard and future DDL proof if role graph, migration rights or SQL changes; (7) retain captured and independently verified original ZIP evidence; (8) obtain **separate explicit user acceptance** before classifying these seven differences as exempt.

**Reject the exception** if any privilege/provenance matrix diverges, object identity or owner changes, unaccounted raw catalog differences exist, catalog-sensitive downstream audit logic cannot be adapted without weakening assurance, role graph cannot be read and checked, current-head/history invariants differ, or a future runtime operation behaves differently.

## Next decision

**BOUNDED RESEARCH RESULT: PASS for executed semantic matrix; physical restoration PARTIAL/BLOCKED.**

**Option A:** NO (insufficient proof).
**Option B:** candidate for explicit coordinator consideration, but currently NOT ACCEPTED.
**Next read-only Neon readiness review:** **NO-GO under existing coordination gates**, notwithstanding successful offline experiments. That gate cannot be promoted until an explicit exception/physical-restoration decision **and** independent closure of broader blockers. Keep `203 structural MATCH / 3 DB-invariant MISMATCH / 7 runtime UNVERIFIED`, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`; `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`. No Neon, production/site-prod, operational WIP, R6, Secrets, casualty or historical/backfill modifications.

**Evidence limitation:** new primary A/B Actions artifact ZIP digests/metadata have been checked from GitHub and jobs/logs, but these new ZIPs have **not yet been Git-frozen or independently Git-only verified**. Prior original `39504096121` A/B ZIPs retain their accepted byte-frozen and independently verified status. A new research artifact is not retroactively verified by that prior independent run. Do not promote this dossier to accepted checkpoint on `main` without independent new archive verification if that is required for acceptance.
