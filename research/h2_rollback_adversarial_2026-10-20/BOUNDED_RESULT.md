# H2 rollback adversarial PostgreSQL 18.6 — bounded execution report

Date: 2026-10-20. Scope: **OFFLINE SYNTHETIC RESEARCH ONLY**, no Neon, no production, no operational promotion.

## Preflight and accepted predecessor

Current main at preflight: `91e2c9b08380b0d0eed59570fecadd59803d1fd4`; `site-prod` `60c174c6bb4b6e2906522d65ccb43caf1c95ee4f`; operational WIP `c58818eafda838967981d07b044eb21680806323`. Latest accepted H2 research `3f7d0d0785c8ccdea4830c05b35e171d461d4a68`. Main `PROJECT_STATE.md` and `CHANGELOG.md` were read before any branch mutation. Previous accepted run `39434358306` 144/144 ×2 and ACL run `39435605595` 20/20 ×2, original verdict PARTIAL, were verified by current GitHub metadata, jobs, artifacts and source blobs. Accepted SQL sources `001`, `003 v3`, `007`, `008` unchanged.

## Executed test and exact frozen evidence

Research branch: `research-h2-rollback-adversarial-pg18-2026-10-20-gpt6`. Tested SHA `142bd18757a432fee57f5c3536e2a40a3ccdb072`; PostgreSQL service `postgres:18.6` in two independent fresh GitHub Actions jobs. SQL and application roles in a synthetic local fixture only. Original A/B run: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39446642675

- A job `118710199075`; artifact `12276507122`; original ZIP SHA-256 `c46a42ef4b579aad9235b4d5080d24abfa387d9de9746312640ca058d68d0203` (12,337 bytes); original JSON SHA-256 `f14387800f9f119e9c7643bd96ba3705917b92edc4503b586f337682b4aa5dfa`.
- B job `118710199384`; artifact `12275672717`; original ZIP SHA-256 `865e577087eea0835a66520b70d21c8762eb2fc41add54a1608ff5401a5d4b60` (12,353 bytes); original JSON SHA-256 `599de47a12b049ccab7eaa871ce08036db163961bac9af4ae3225f5b6908310d`.
- Each environment: R01–R16 **15 PASS / 1 PARTIAL** (R09); H01–H12 **11 PASS / 1 PARTIAL** (H11); SECURITY DEFINER C1–C8 **8 PASS** (bounded executable cases); ACL D01–D04 **4 PARTIAL**. All reported complete-suite verdicts **PARTIAL**, with no test assertion errors in the final A/B execution. Earlier failing candidate runs `39446122008` and `39446362919` remain as historical failures; they revealed harness issues, not independently demonstrated SQL defects.
- Original ZIP/JSON retention: freeze run https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39447338585 succeeded; archive commit `d58af72b232bba859aa9dcc3f7efea07ffa65d95`; immutable versioned manifest `research/h2_rollback_adversarial_2026-10-20/frozen_2026-10-20/manifest.json` Git blob `3755d2b81558631fe0869575ea29b472ed02eaf2`.
- Independent Git-only verification: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39447488802 succeeded: two original ZIP CRC/SHA/JSON checked, executable Git blobs equal tested commit, all **10/10** deliberate ZIP/JSON/attribution/verdict corruptions rejected. Git-only integrity is not proof of unexecuted SQL behavior.

## R03 concurrent rollback timeline (real `pg_locks`, both copies)

**Writer-first:** separate restricted writer session holds `RowExclusiveLock` on `public.attack_event_classifications` and `public.h2_classification_heads` while the rollback session is witnessed waiting for `AccessExclusiveLock`. Writer commits a classification; rollback's post-lock history check refuses SQLSTATE `23514` (`H2_ROLLBACK_RACING_WRITE`), psql exit 3; committed classification and correct head persist.

**Rollback-first:** a short-lived independent fixture connection holds `RowShareLock` on classifications; the actual rollback is witnessed waiting for `AccessExclusiveLock`, then a separate restricted writer is witnessed waiting for `RowExclusiveLock`. The holder releases; rollback COMMITs SQLSTATE `00000`; waiting writer receives `42501`; history count remains zero and head registry is removed. No orphan/partial downgrade observed. This tests an initially *empty* history in the rollback-first ordering, not all possible production history cardinalities. These are controlled SQL lock witnesses, not time-delay inferences.

## Bounded gate dispositions

| Gate | Verdict | Executed proof or limitation |
|---|---|---|
| H2_ROLLBACK_CLEAN_DOWNGRADE | PASS BOUNDED | R01 real 008; canonical records unchanged, revision objects removed; ACL residual separately PARTIAL |
| H2_ROLLBACK_COMMITTED_HISTORY_FAIL_CLOSED | PASS BOUNDED | R02 committed revision, actual 008 refuses `23514`; unchanged readback |
| H2_ROLLBACK_CONCURRENT_WRITER_SERIALIZATION | PASS BOUNDED | R03 both lock interleavings, `23514` and `42501` after actual committed outcomes |
| H2_ROLLBACK_MISSING_OBJECT_GUARDS | PASS BOUNDED | R04 missing registry and R05 missing function/trigger; `23514` |
| H2_ROLLBACK_OWNERSHIP_AND_MEMBERSHIP_GUARDS | PASS BOUNDED | R06 unexpected owner, R07 no membership, R08 missing destination CREATE |
| H2_ROLLBACK_ACL_FAULT_ATOMICITY | PARTIAL | R11 injected SQL exception and pre/post fingerprint equality; no proof of failure after multiple ACL changes already executed |
| H2_ROLLBACK_OWNER_FAULT_ATOMICITY | PASS BOUNDED | R12 injected failure after ownership transfer and equal post-abort fingerprint |
| H2_ROLLBACK_CROSS_DATABASE_ROLE_SAFETY | PASS BOUNDED | R13 `DROP ROLE` fails `2BP01`, unrelated dependency and role retained |
| H2_REPEATED_MIGRATION_ROLLBACK | PASS BOUNDED | R16 real 007/008 repeated, re-application, partial setup and unexpected object |
| H2_MIGRATION_INVALID_HISTORY_MATRIX | PARTIAL | H01–H10/H12 pass; H11 demonstrates a synthetically corrupted existing registry that replay fails without validating head consistency |
| H2_SECURITY_DEFINER_ADVERSARIAL_CLOSURE | PASS BOUNDED | C1–C8 current tested constructs; no implication that unreachable function/operator shadow constructs prove every potential future function body |
| H2_RESTRICTED_WRITER_PRIVILEGE_ISOLATION | PARTIAL | R14/C5/C6 reject direct restricted writer DDL and history writes; R09 deliberately demonstrates unsafe **inherited owner-role** authority in external role hierarchy |
| H2_ACL_EFFECTIVE_PRIVILEGE_EQUIVALENCE | PASS BOUNDED | Previously independently accepted 20/20 ×2 eight-role privilege matrix; new D02 selected GRANT/REVOKE controls |
| H2_ACL_RAW_CATALOG_EQUIVALENCE | PARTIAL | D01 confirms `pg_class.relacl` physical drift NULL→explicit |
| H2_ACL_FUTURE_OPERATION_EQUIVALENCE | PARTIAL | D02 GRANT/REVOKE works on selected fixture; no complete ownership-transfer, membership-change, `pg_dump` equivalence |
| H2_ACL_REPRESENTATION_RESIDUAL | PARTIAL | D01 physical diff recorded; D03 safe DDL exact restoration not demonstrated |
| H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK | PARTIAL | Physical ACL difference unresolved |
| H2_PG18_INDEPENDENT_A_B | PASS BOUNDED | Run 39446642675, separate PG18.6 jobs |
| H2_NEW_ORIGINAL_A_B_EVIDENCE_FREEZE | PASS | Original ZIP CRC/SHA and pinned JSON Git archive + manifest |
| H2_INDEPENDENT_GIT_ONLY_VERIFICATION | PASS | Run 39447488802, source blob consistency, 10 deliberate corruptions rejected |
| H2_READONLY_NEON_PREFLIGHT_READINESS | BLOCKED / NO-GO | Migration/ACL gates and explicit authority unresolved |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO | No real Neon privileges or contract equivalence verified |

The `C` tests exercise trusted `public.` relation names, `search_path=pg_catalog, pg_temp`, hostile temporary relation resolution and injected untrusted functions/operators, with actual application inserts and independent head checks. Tests of an unreachable hostile function name cannot establish an exploit being actively blocked; the tested installed guard is the scope limit.

## ACL semantic-alternative proposal, NOT ACCEPTED

Only if separately authorized: narrowly permit an enumerated `pg_class.relacl = NULL` to exact explicit ACL representation change after complete effective schema/table/column/function/PUBLIC/owner/inheritance/grant-option checks and corresponding forward-operation checks. Must enumerate affected relation names and owner snapshots, require future GRANT/REVOKE/ownership/role-membership/default-privilege and `pg_dump --schema-only` controls, reject unexpected CREATE/EXECUTE/ownership, confirm historical head integrity and external role hygiene. Residual drift may appear in raw-catalog/schema-diff audit and future tooling. No direct `pg_catalog` mutation or canonical OID/table replacement authorized. No semantic criterion has been approved or made active.

## Source changes and operational boundary

New versioned harness and workflow files reside **only** under `research/h2_rollback_adversarial_2026-10-20/` and `.github/workflows/h2-rollback-adversarial-*.yml`, `h2-adversarial-freeze.yml`, `h2-adversarial-git-only.yml`. No accepted `001`, `003`, `007`, `008` SQL was edited; no corrective SQL migration candidate was justified by these results. Other security and rollback tests may require expansion beyond these newly executed selected cases. Existing `PROJECT_STATE.md` and `CHANGELOG.md` remain unchanged, pending independent user acceptance.

Preserve coordination ceilings: `203 structural MATCH / 3 DB-invariant MISMATCH / 7 runtime UNVERIFIED`; `UNBOUND_UNRESOLVED=25`; `C4/C5=NOT PROVEN`; `NEON_AUTHORITY_ACTIVE=NO`; `PRODUCTION_CUTOVER_EXECUTED=NO`; `WIP_ACTIVATION=NO-GO`. No real Neon access, GitHub Secrets, production data, live updates, casualty, historical/backfill or R6 work was performed.

**Decision:** rollback and installed SECURITY DEFINER controls materially advance in offline synthetic verification; H11 and inherited owner authority plus physical ACL rollback and unexecuted future DDL/privilege operations remain unresolved. **NO-GO for requesting live read-only Neon preflight at this checkpoint** until the remaining conditions and separate acceptance of any semantic ACL proposal have been adjudicated.
