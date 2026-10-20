# H2 PostgreSQL 18 migration security: partial executable closure

Date: 2026-10-20. **Research only. Not accepted for live Neon.**
No Neon connection, operational WIP edit, production migration, or promotion.

## Verified preflight
- Read main PROJECT_STATE.md and CHANGELOG.md before research.
- At start: main d03d4688796ad38b866bf3596d35de1585b9d35d; site-prod dcec1d0d1d04a8381ab1672964cd9a941ce38a72; WIP c0958add441b42e5a6400c39737fda0b0da6637c.
- Source predecessor research 1b6f922f73f4a253ac529f9ae0ec20ae74892241. Original accepted CAS research 3c1cf86ac0eaee1b1de246022c19acbb58037948.
- New independent research branch research-h2-pg18-security-closure-2026-10-20.
- Reviewed main and predecessor workflows including workflow_run listener; isolated new workflows have branch-specific push/path triggers, no Neon secrets, no production credentials or external polling.

## Original A/B attribution and actual artifact bytes: PASS
- Original PG18 success run 39332325216 tested 6e53ae59115199499910a29916ebd0c501c60ff1; A job 118333286878/artifact 12225295967; B job 118333286498/artifact 12224907771. Both 37/37.
- Original permission defect failure run 39332206445 tested 4ae83d14cae6a33956f991cb5af68e81576c7697; A job 118332894278/artifact 12225136563; B job 118332894783/artifact 12224254157. Both reported 30/30 preceding checks followed by failure SQLSTATE 42501.
- Isolated evidence collector run 39386661546 and independent Git-only verifier 39386749080 SUCCESS.
- Exact four original GitHub Actions ZIP-envelope bytes are encoded in original_artifacts/*.github_original_zip.b64, each paired with its original JSON member. Exact byte digests, ZIP CRC, job identification, test commit, A/B and 11/11 deliberate corruption controls validated.
- Manifest Git blob ef92c138cd408cd396df9561f6e7695596a23d3c. Receipt Git blob e4d75ffd6c22b0c816d7ecd22d1a32c2c5e9fd43. Original incorrect predecessor EXECUTION_REPORT.md retained unchanged in parent Git history.

## Newly discovered v2 atomicity defect and bounded v3 correction: PASS
- v2 003_candidate_app_role_v2.sql tests PUBLIC CREATE only *after* GRANT and REVOKE statements in default psql autocommit; a failing 42501 leaves preceding role grants committed. Concrete counterexample: pre-revoke SELECT on alert_episodes, allow PUBLIC schema CREATE, run v2, observe 42501 and changed ACL.
- New versioned 003_candidate_app_role_v3_atomic.sql begins a transaction, prechecks PUBLIC CREATE before making any ACL changes, performs role DDL/GRANT/REVOKE, and commits only after all succeed.
- PG18.6 A/B run 39387213964, tested commit 3d35d8a08f2800c8fdbe460b76a1b25d7ff59845, jobs A 118509815117 and B 118509814721: **42/42 assertions PASS in each fresh PG18.6 service**, synthetic reconstructed schema.
- Positive non-PUBLIC-CREATE environment v3 role grants succeeded; checked permissions for SELECT/INSERT, event update, protected classification history, protected heads, schema CREATE and guard-owner membership; real SQL negative controls reject INSERT-only writer DDL, direct head updates, historical UPDATE and SET ROLE.
- Negative PUBLIC-CREATE environment rejects v3 with SQLSTATE 42501 and complete pre/post ACL/role snapshot equality. Legacy v2 negative control exhibits persistent ACL side effect despite error.
- Earlier runs 39387009000 and 39387118026 failed for harness placeholder escaping and inadequate ACL-delta baseline respectively; retained as failed provenance, repaired before 39387213964.
- This is an additional bounded proof, not all required Phase B-F scenarios. Original guard function ownership still installed using synthetic superuser fixture.

## Remaining requirements / verdicts
| Gate | Verdict | Reason |
|---|---|---|
| H2_ORIGINAL_MIGRATION_AB_EVIDENCE_FREEZE | PASS | 4 original artifact ZIP+JSON bytes Git-retained, independently verified |
| H2_AB_RECEIPT_ATTRIBUTION | PASS | Corrected in versioned evidence manifest; predecessor historical report preserved |
| H2_MIGRATION_PRECONDITIONS | PARTIAL | Original clean/two-root smoke only; broad separate-db invalid classes not executed |
| H2_NONSUPERUSER_GUARD_OWNER_TRANSFER | BLOCKED | Superuser setup only, realistic Neon-compatible transfer untested |
| H2_APP_ROLE_V2_EFFECTIVE_PRIVILEGES | PARTIAL | Real v2 defective autocommit fail-closed control; versioned v3 bounded PG18 test PASS |
| H2_SECURITY_DEFINER_SEARCH_PATH_SAFETY | PARTIAL | Prior pg_temp setting tested, attack suite incomplete |
| H2_GUARD_OWNER_PRIVILEGE_ISOLATION | PARTIAL | Narrow negative role tests, owner-transfer and broader attacks untested |
| H2_RESTRICTED_WRITER_EXPECTED_TIP_E2E | BLOCKED | No accepted complete CAS writer/main() executed as newly restricted application role |
| H2_CONCURRENT_STALE_WRITE_REJECTION | BLOCKED | Prior separate CAS test used different role; new integrated restricted-role concurrency untested |
| H2_INDEPENDENT_COMMIT_READBACK | BLOCKED | Restricted CAS path with independent COMMIT/readback untested |
| H2_FULL_MIGRATION_AND_ACL_ROLLBACK | BLOCKED | No full ACL+schema rollback run |
| H2_PG18_INDEPENDENT_A_B | PARTIAL | v3/ACL subtest 42/42 A/B; expanded all-gates suite not executed |
| H2_GIT_ONLY_EVIDENCE_VERIFICATION | PASS (original evidence only) | Original four ZIP/JSON + 11 corruption cases; new PG18 v3 outputs remain Actions artifacts |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO | Missing all integrated role, writer, rollback and exact-Neon preflights |

## Global unchanged statuses
203 structural MATCH / 3 MISMATCH / 7 UNVERIFIED.
NEON_AUTHORITY_ACTIVE=NO; PRODUCTION_CUTOVER_EXECUTED=NO; WIP_ACTIVATION=NO-GO;
C4/C5=NOT PROVEN; UNBOUND_UNRESOLVED=25.

## Next task
Complete the missing PG18 synthetic scenarios: comprehensive migration preconditions; actual non-superuser ownership transfer; SECURITY DEFINER bypass suite; accepted CAS writer under v3 restricted credentials; full before/after ACL+owner/default privilege snapshot and complete rollback; original A/B freeze for *new* PG18 test results; independent evidence verification. No read-only Neon authorization recommended yet. Do NOT update coordination main docs as a fully accepted checkpoint based on this partial suite.
