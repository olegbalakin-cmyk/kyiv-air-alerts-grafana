# H2 isolated PG18 migration / guard-owner executable probe

Date: 2026-10-20. Research only; no real Neon contact, role changes, monitoring or deployment.

## Source and head provenance

- Base contract research: cd7e8ce0a2ca11899cc0f2a59067f07c8ca6c861.
- Accepted prior expected-tip snapshot branch: 3c1cf86ac0eaee1b1de246022c19acbb58037948.
- Original candidate 001/003/004/rollback remain unchanged.
- Tested candidate commit: 6e53ae59115199499910a29916ebd0c501c60ff1.
- PostgreSQL 18.6 A/B: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39332325216
- Jobs: A 118333286498, B 118333286878. Both SUCCESS.
- Executed checks: A 37/37 PASS, B 37/37 PASS. This is a **bounded smoke suite**, not the full 15-scenario acceptance suite.
- Actions retained JSON artifacts: A 12225295967 (GitHub-declared artifact digest sha256:a989a88ef545777264a71165bb10434047f8123e9d2b56e24313fa1802a6d1e6), B 12224907771 (sha256:31f591f34eaab758611d4b6e17d9356a08cb096fd46b77a10088b6197015c672).
- These are GitHub artifact-envelope digests, NOT the unverified raw JSON SHA-256. Raw reports have **NOT** been independently Git-frozen.
- Initial run 39332080645 failed due fixture path typo, corrected. Run 39332206445 reached 30/30 recorded checks per job and found a genuine function-owner permissions defect.

## Identified and corrected defect

Original 004 grants h2_head_guard_test INSERT/UPDATE on h2_classification_heads but no SELECT. The SECURITY DEFINER UPDATE ... WHERE tip_classification_uid=... requires SELECT for predicate columns, resulting in SQLSTATE 42501 from an actual restricted-role revision INSERT in BOTH PostgreSQL 18.6 jobs. Versioned supplemental 005 grants SELECT and sets search_path to pg_catalog,pg_temp (pg_temp explicitly last). The earlier 004 is preserved byte-identically. Corrected A/B run executes the same writer insert successfully.

## Executed bounded coverage

- Source schema: observed-partial reconstructed synthetic schema plus separately reconstructed 18-column checkpoint view. NOT a byte-identical Neon instance.
- Clean legacy two-revision chain: 001 installed candidate indexes, table, trigger and function, preserving historical classification rows and backfilling the tip.
- Repeat 001: rejected, preexisting revision objects remained present.
- Invalid two-root history: 001 rejected; classification rows unchanged; no revision objects installed.
- Original 003 and 004 executed by h2_local PostgreSQL superuser.
- Dedicated login: NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS.
- No-login guard isolated as function owner; function search_path includes pg_temp explicitly after pg_catalog.
- Restricted login reads classifications and reconstructed checkpoint view; rejects historical UPDATE/DELETE/TRUNCATE, direct head UPDATE, DDL, SET ROLE guard, schema CREATE.
- Restricted login inserts legitimate linked classification revision and indirectly advances head.
- Revised rollback rejects a synthetic stale head, then removes revision objects with repaired head while preserving historical classifications.
- Role ACL deliberately remains after revision-only rollback; explicit full rollback of privileges / PostgreSQL role objects NOT PROVEN.

## Gaps and strict decisions

| Gate | Verdict | Bound |
|---|---|---|
| H2_PG18_CLEAN_MIGRATION | PASS BOUNDED | PG18.6, observed-partial schema, clean chain |
| H2_EXISTING_DATA_PRECONDITION_CONTROLS | PARTIAL | Two roots only; 7+ adverse scenarios untested |
| H2_ROLE_003_EXECUTION | PARTIAL | Original executed; subset of effective privilege checks |
| H2_GUARD_OWNER_004_EXECUTION | PARTIAL | Original broken under restricted insert; 005 correction executed |
| H2_NONSUPERUSER_OWNERSHIP_TRANSFER | BLOCKED | Superuser-only path executed; non-superuser not tested |
| H2_SECURITY_DEFINER_HARDENING | PARTIAL | pg_temp path and role subset; shadowing tests missing |
| H2_RESTRICTED_WRITER_CAS_INTEGRATION | PARTIAL | Direct revision INSERT/trigger only; accepted monitor/writer E2E not retested as new restricted login |
| H2_MIGRATION_ROLLBACK | PARTIAL | Revision objects and rows, not ACL restoration |
| H2_PG18_INDEPENDENT_A_B | PASS BOUNDED | Two fresh independent PG18.6 jobs, 37/37 each |
| H2_GIT_EVIDENCE_FREEZE | BLOCKED | JSON artifacts remain in Actions; independent Git-only archive/readback missing |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO | Not fully verified |

Global effects of candidate 003's REVOKE CREATE ON SCHEMA public FROM PUBLIC were not independently assessed. Candidate 003 v2 is a **draft** fail-closed alternative preserving preexisting PUBLIC ACL, unexecuted. Separate permission-preserving 003 deployment required before any Neon proposal.

Retain 203 MATCH / 3 MISMATCH / 7 UNVERIFIED; NEON_AUTHORITY_ACTIVE=NO; PRODUCTION_CUTOVER_EXECUTED=NO; WIP_ACTIVATION=NO-GO; C4/C5=NOT PROVEN; UNBOUND_UNRESOLVED=25.

No standalone acceptance of this as a complete checkpoint. Do NOT update main PROJECT_STATE.md or CHANGELOG.md or claim a Neon GO.

## Next smallest offline closure

1. Execute remaining precondition fixtures and distinguish SQLSTATE with exact row/object snapshots.
2. Test non-superuser function owner transfer, effective inherited ACL and pg_temp shadowing attacks.
3. Execute **accepted expected-tip writer** with this restricted login (not the old h2_app_writer_test account) including competing COMMIT, fault rollback and independent readback.
4. Test and restore ACL snapshot in a complete role/permission rollback.
5. Persist exact A/B raw reports and independent Git-only integrity/corruption receipt.
6. Only after independently accepting these results, separately authorize read-only Neon catalog, role-membership and aggregate data-cleanliness checks. Live access remains prohibited by the present authorization.
