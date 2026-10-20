# H2 H11/R09/ACL continuation — bounded original-evidence checkpoint candidate

Date: 2026-10-20. **NOT ACCEPTED AS FULL H2 SECURITY CLOSURE. NOT A NEON GO.**
Research branch `research-h2-h11-r09-acl-provenance-2026-10-20-gpt6`, based on accepted predecessor `c6d2e62796a16964f5ed411f75dea919eded431f`.

## Preflight and invariants
Read latest main `PROJECT_STATE.md` and `CHANGELOG.md`; main `9eb60e2b836d18cb0ae3680f58b6bac59d604818`, site-prod `60c174c6bb4b6e2906522d65ccb43caf1c95ee4f`, WIP `c58818eafda838967981d07b044eb21680806323`, accepted adversarial `c6d2e627...`, integrated CAS `3f7d0d0785c8...`. Checked research push triggers vs protected workflows before writes; no production or WIP path matched the new research branch. No actual Neon access, GitHub secret, real data, production, backfill, casualties or R6 work.

## A. Original adversarial A/B provenance: independent corrected Git-only PASS
Corrected original-swapped job IDs without overwriting prior `frozen_2026-10-20/manifest.json` blob `3755d2b81558631fe0869575ea29b472ed02eaf2`, original JSON or B64 original ZIP bytes. Original PostgreSQL 18.6 source `142bd18757a432fee57f5c3536e2a40a3ccdb072`, original overall verdict PARTIAL. Job A `118710199384` uploaded artifact A `12276507122`, ZIP size 12337, SHA256 `c46a42ef4b579aad9235b4d5080d24abfa387d9de9746312640ca058d68d0203`; B job `118710199075` uploaded artifact B `12275672717`, size 12353, SHA256 `865e577087eea0835a66520b70d21c8762eb2fc41add54a1608ff5401a5d4b60`. Original job logs directly inspected at correction time; only timestamped selected log lines frozen. Corrected manifest v2, correction receipt and separately pinned constants/source log excerpt blobs passed true job-ID swap and eight other genuine tamper negatives. [Run 39471150532](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39471150532), job `118795228868`, SUCCESS, 10/10 intentional corruptions REJECTED. Complete provenance freeze qualifies as BOUNDED SELECTED ORIGINAL JOB-LOG EXCERPTS, not full log envelopes.

## B. H11 read-only complete history consistency: PASS BOUNDED (11 scenarios per copy)
Versioned standalone `h11_head_history_check.sql`: original canonical four-field identity, complete predecessor traversal with cycle guard, roots/tips, duplicates, missing/wrong/orphan heads and nonterminal tips; does not modify classification records. A/B [run 39473109411](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39473109411), jobs A `118802020276`, B `118802020005`, SUCCESS in postgres:18.6. Original nine cases (empty, single, multi, independent, stale, missing, wrong identity, repeat), plus orphan-head and real same-transaction locking with independent restricted writer receiving `55P03`, history unchanged. Snapshot checker returns diagnostic SELECT rows; caller currently interprets rows. **NOT** a fail-closed migration DDL integration; no complete invalid-history matrix (synthetic multiple roots/terminal corruption, cycles), no all-in-one installation preflight under real concurrent writer through commit. This is neither existing database migration authorization nor Neon readiness.

## C. R09 effective privileges: PASS BOUNDED (7 scenarios per copy)
Versioned `r09_effective_role_preflight.sql` runs under non-superuser migrator before hypothetical DDL, returns `00000` for safe topology and `42501` for unsafe role owner inheritance, SET-only membership, direct history UPDATE, guard membership, schema CREATE, indirect owner chain; independently verified unchanged fingerprint. [A/B run 39472805865](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39472805865), jobs A `118800960144`, B `118800960444`, both SUCCESS. Application trust boundary is explicit; synthetic `h2_local` cluster superuser bootstrap is not an application login. Role inspection currently targets selected principal and dangers, does not exhaust all PostgreSQL 18 ADMIN option graph paths, downstream function alteration powers, ALL app principals, future role changes or integrated migration/activation transaction. Thus broader R09 role-topology and restricted writer complete isolation remain PARTIAL.

## D. ACL and rollback: 9 selected cases/copy PASS, overall PARTIAL
Latest [A/B run 39473170811](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39473170811), jobs A `118802223389`, B `118802223072`, postgres:18.6 exact-matched pg_dump client, SUCCESS with JSON summary `PARTIAL`. Verified raw relacl residual on 7 canonical tables, unchanged historical fingerprint, actual `pg_dump --schema-only`, 4 GRANT/REVOKE equivalence steps and three successful ACL modifications followed by explicit SQLSTATE `23514` and unchanged pre-/post-transaction ACL/history snapshot. This tests a **constructed transaction**, NOT an injected late fault in actual accepted `008` rollback SQL, so full rollback atomicity is PARTIAL.
Raw pg_dump hashes differ even across repeated dumps of the SAME fixture due volatile `\\restrict` markers. Removing only `\\restrict`/`\\unrestrict` lines yielded independently matching original/control-repeat/rolled normalized SHA-256 `fbae79c3e61142a5cfbd4fdbdef9b1a7b77e9a95817ee09fa96c6e611148609e` in **both A/B**, with empty normalized diff. This proves bounded normalized `pg_dump` output equivalence, NOT raw catalog equality or ownership / membership / future DDL equivalence. Original `relacl=NULL`→explicit residual persists; no supported exact DDL restoration proven. Separate semantic-equivalence proposal is **NOT ACCEPTED**.

## Evidence limitations and explicit gate decisions
All newly executed H11/R09/ACL original A/B Actions artifacts exist, but **byte-accurate original ZIP/JSON Git freeze and fresh independent Git-only verifier for these three NEW suites have NOT been completed**. Git-only provenance correction PASS is a separate archival family and not evidence of SQL correctness. Preserve predecessor CAS 144/144 A/B as previously accepted; these added read-only/new checker candidates did not modify original CAS, guard ownership or operational writer.

| Required gate | Decision; exact boundary |
|---|---|
| H2_ADVERSARIAL_AB_JOB_ATTRIBUTION | PASS; independently observed logs and v2 corrected IDs |
| H2_ADVERSARIAL_COMPLETE_PROVENANCE_FREEZE | PASS BOUNDED; selected original job log excerpts, exact original ZIP/JSON |
| H2_ADVERSARIAL_CORRECTED_GIT_ONLY_VERIFICATION | PASS; 10/10 genuine adversarial mutations |
| H2_EXISTING_MIGRATION_HEAD_HISTORY_CONSISTENCY | PARTIAL; checker detects stale head on already-migrated DB, not integrated authoritative migration precheck |
| H2_HEAD_HISTORY_CONCURRENT_PREFLIGHT_SAFETY | PARTIAL; SHARE ROW EXCLUSIVE controlled barrier `55P03`, no actual DDL migration COMMIT protected |
| H2_MIGRATION_INVALID_HISTORY_MATRIX | PARTIAL; not all corruption/ambiguous history cases exercised |
| H2_ROLE_INHERITANCE_AND_EFFECTIVE_OWNER_PREFLIGHT | PASS BOUNDED; selected 7 actual PG18 A/B cases |
| H2_ROLE_TOPOLOGY_FAIL_CLOSED | PARTIAL; selected 6 hostile cases reject `42501`, comprehensive role topology incomplete |
| H2_RESTRICTED_WRITER_PRIVILEGE_ISOLATION | PARTIAL; selected synthetic writer contract only, unknown external privileged paths |
| H2_ACL_EFFECTIVE_PRIVILEGE_EQUIVALENCE | PASS BOUNDED; 4 new future privilege commands, predecessor broader sampled matrix separate |
| H2_ACL_FUTURE_OPERATION_EQUIVALENCE | PARTIAL; future ownership, membership, function, default and DDL under-tested |
| H2_ACL_PGDUMP_SCHEMA_BEHAVIOR | PASS BOUNDED; normalized emitted dump equal in tested pair, raw hash differs due volatile marker |
| H2_ROLLBACK_ACL_FAULT_ATOMICITY | PARTIAL; synthetic late fault after 3 ACL GRANTs, NOT actual `008` late fault |
| H2_ACL_RAW_CATALOG_EQUIVALENCE | PARTIAL; seven relacl discrepancies |
| H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK | PARTIAL; unclosed catalog/future authority |
| H2_RESTRICTED_CAS_REGRESSION_IF_REQUIRED | PASS PREVIOUS ACCEPTED BASELINE ONLY; original CAS source unchanged, not rerun on integrated new migration configuration |
| H2_PG18_INDEPENDENT_A_B | PASS BOUNDED; H11, R09, ACL actual separate PostgreSQL 18.6 jobs |
| H2_NEW_ORIGINAL_AB_EVIDENCE_FREEZE | BLOCKED/INCOMPLETE; only existing adversarial provenance corrected, new family originals not Git-frozen |
| H2_INDEPENDENT_GIT_ONLY_VERIFICATION | PARTIAL; corrected old provenance PASS, new SQL families not Git-only-frozen |
| H2_READONLY_NEON_PREFLIGHT_READINESS | BLOCKED / NO-GO |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO |

Full security closure and Neon preflight approval remain NOT GRANTED. No acceptance of semantic-only ACL drift; no operational promotion. Keep `203 structural MATCH / 3 DB-invariant MISMATCH / 7 runtime UNVERIFIED`, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`, `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`.

Next exact task: finish H11 fail-closed migration-transaction integration and all invalid-history/concurrency negative cases, exhaust R09 role graph and activation guard, extend D1/D3 using **actual rollback SQL** and future ownership/DDL/pg_dump changes, then freeze original ZIP/JSON for ALL NEW PG18 A/B suites and run independent tamper/readback. Request a separate user approval for any semantic-only ACL acceptance and strictly read-only Neon preflight, never automatically.
