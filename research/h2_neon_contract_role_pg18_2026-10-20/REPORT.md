# H2 exact frozen Neon contract / role preflight — bounded research artifact

**Date:** 2026-10-20. **Repository:** `olegbalakin-cmyk/kyiv-air-alerts-grafana`.

## Authority and preflight

Read current main `PROJECT_STATE.md` (blob `523599aac4dcaff4f866908346b1e909f87227db`) and `CHANGELOG.md`. Ref snapshot before research branch creation: main `1798ef138c89e09eefaa9732b40e155cdb1cb0e7`, site-prod `4c8dafab15d26f0220eb911c67844d522974081d`, operational WIP `08f7225ed1b895c003f9fb426daa12641d372471`, expected-tip research `3c1cf86ac0eaee1b1de246022c19acbb58037948`.

GitHub Actions metadata was inspected for catalog verification run 39273063710 (SUCCESS; tested 3de322b8…), expected-tip A/B run 39326315620 (SUCCESS; tested d6019f2…), final independent Git-only 39326753309 (SUCCESS; exact research final 3c1cf86…). These are prior accepted proof, **not new tests**. Workflow preflight: present main research documentation paths are not push trigger paths; only this new isolated research branch is edited. All production, data, operational, Neon and site-prod paths remain unaffected.

## Frozen evidence identity

| Object | Git blob |
|---|---|
| Old live Neon catalog, 185 columns / 221 constraints / 30 indexes / 7 tables | `60246ffa7a436eef830592c7999c9e7dc3941123` |
| New 19-result catalog, 60,689 bytes | `e550b35578283b2af4e0e8fba956e98c4bcc0f03` |
| SQL-to-result statement map | `ec81acf8ee50ccb7236c15330abd53e619cffc3f` |
| 213-contract matrix | `6f1269c7d3134f2c3bfce2373a01641c26f10fa6` |
| View reconstruction (18 fields, environment-qualification adaptation) | `d44eda04f20034b28125bf3e94d5881ab340db5a` |
| Partial schema fixture | `09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3` |
| 001 hardening candidate | `339b9b44a90f8b5e8ba216576f63daac393a5eb3` |
| 002 original synthetic grants | `b4c1be395b0cfdc16086729ad903ef10e00b1fb0` |
| Accepted operational WIP writer original | `0118ca9e5f1308173e657257f1b49fe91cc19fe1` |
| Expected-tip research writer | `41bf81e6853572234e4951df04387eeb950c1b33` |

Frozen raw catalog SHA-256, as stated in accepted source manifest: `60d829053bb7d7e9a734c12c154b6db5552cdc558b60105babbecdbec0d3e624`. This document **does not independently rehash those 60,689 bytes**.

## Exact reconstruction ceiling and object matrix

| Object/property | Source coverage | Evidence class |
|---|---|---|
| Seven table identities, 185 columns, type/default/nullability, 221 constraints, 30 indexes | Older raw catalog; fixture can be compared | EXACT_FROZEN_CATALOG_MATCH for definitions only, not runtime parity |
| View current_ingestion_checkpoints | pg_get_viewdef + 18 columns + dependency readback; stored reconstructed SQL | PARTIAL_RECONSTRUCTION; search_path qualification adapted and grants absent |
| Functions pg_advisory_xact_lock, hashtextextended, gen_random_uuid | new catalog pg_proc readback | EXACT_FROZEN_CATALOG_MATCH for binding; UNVERIFIED writer runtime |
| Role neondb_owner owner, membership, bypassrls and effective ACL | new catalog | EXACT_FROZEN_CATALOG_MATCH for inspected owner, NOT application identity |
| Dedicated application writer, its real DSN authentication | no authoritative runtime proof | UNVERIFIED |
| Existing persisted classification rows, identity/root/tip cleanliness | frozen metadata is insufficient | UNVERIFIED |
| 001 successor index, one-root index, head registry and CAS trigger | candidate-only SQL | MISMATCH with baseline live catalog (not applied) |
| SECURITY DEFINER owner and search_path for new function | candidate DDL, no live object | PARTIAL_RECONSTRUCTION |
| After-migration catalog/fingerprint/actual grants | no PG18 execution in this turn | UNVERIFIED |

## Migration compatibility risks

Original `001` preflight rejects duplicate successors, cross-identity parents, multiple roots/tips, orphan/cyclic chains. Existing population of the live database was not inspected in this authorization. `001` is not idempotent: running a second time collides with indexes/table/function/trigger. Its head registry is a mutable materialized tip pointer; correctness requires trigger effectiveness and a nonowner runtime principal. `002` covers only synthetic role and does not establish a secure Neon owner: an owner may bypass history immutability.

Migration order **only after separate approval and database data preflight**: exact read-only catalog/data-aggregate evidence → explicit schema/ACL backup → exclusive writer pause → validate all legacy chains, FK/identity and roots/tips → 001 transactional SQL → isolated 003 application role DDL/GRANT/REVOKE → isolated 004 nonlogin SECURITY DEFINER function owner transfer (privilege capability must be verified) → owner/role/ACL fingerprint + denied-mutation tests → committed writer readback. Rollback on disposable fixture: stop writers and verify invariant → run `rollback_revision_only.sql` to remove new objects, then restore ACL from pinned snapshot; legacy original historical rows remain unchanged. Any role removal is a separate dependency-checked action. A migration rollback never undoes writes already committed by an application; those require explicit reconciliation.

**Concrete risks:** `SECURITY DEFINER` must not be owned by application login or application-inheritable parent; secure fixed `search_path`, fully-qualified table names, explicit EXECUTE revoke; role ownership transfer feasibility not established for Neon. A schema owner remains an unrestricted bypass and does not satisfy absolute append-only guarantees. Dependency locking and object ownership/privilege replay need real PG18 verification.

## Runtime matrix (ordinals maintained)

| # | Exact requirement | Existing evidence | Local evidence | Still open | More Git? | Live catalog? | Disposable write? | Minimum scope |
|---:|---|---|---|---|---|---|---|---|
| 183 | Exact episode identity + overlap exclusion | UQ exact interval and partial open interval frozen | PG18 synthetic parent matching previously passed | General overlap and alternative writers | No | No | Yes | Schema/catalog SELECT; disposable overlapping synthetic INSERT |
| 190 | current_ingestion_checkpoints view contract | View type, 18 columns, pg_get_viewdef, dependency rows frozen | Separate reconstructed view SQL only | Actual Phase1 app-role view access, read correctness | Yes | No for definition | Yes for runtime | SELECT view as authenticated app role; synthetic readback |
| 206 | Runtime effective privileges | Owner metadata and owner ACL effective privileges frozen | Restricted synthetic writer previously passed | Deployment SQL login and grants unknown | Partial | Yes if role absent from catalog | Yes for actual insert | username-only runtime binding; role metadata and app auth |
| 210 | Advisory locking and pg_catalog functions | Functions OIDs/owner EXECUTE frozen | PG18 concurrent lock passed in prior proof | Runtime role and Neon write locking untested | No | No for functions; Yes for runtime grants | Yes | App-role pg_proc privileges; synthetic concurrent writes |
| 211 | Isolation, COMMIT and durability | PG18.6 owner read-only READ COMMITTED and nondeferred constraints | Prior offline commit/readback and restart PASS | Neon writer commit ACK and SQL client transaction unproven | No | No | Yes | Two independent sessions on disposable branch |
| 212 | Extensions and function bindings | plpgsql + builtins + owner search_path frozen | Prior PG18 function binding PASS | App session path and function owner transfer not proven | Partial | Yes for runtime role overrides | Yes for runtime invocation | Role path; pg_proc owner/ACL; controlled synthetic execution |
| 213 | Current-tip index and concurrency | No successor UNIQUE, no direct current-tip arbiter | Previous CAS PG18 48/48 PASS | Migration not applied, owner bypass, live parity absent | No | No for old indexes; Yes for updated objects | Yes | Independent synthetic CAS race + post-COMMIT readback |

## Executability boundary

The current container has PostgreSQL 17 `pg_config` utilities only, **no PostgreSQL 18 server binaries, psql, Docker or reachable package repositories**. Thus this turn performed GitHub read-only source/catalog/run verification and authored offline-only SQL scripts, but **did NOT execute** the local PostgreSQL 18 migration, restricted writer, race, owner transfer, schema fingerprint, rollback or A/B suites. No fresh PG18 run numbers, report digests, or A/B counts exist. The prior accepted tests remain valid within their original scopes only; they must not be attributed to this commit. No independent CI verification has been run on these new SQL candidates.

## Verdict

| Gate | Result | Evidence ceiling |
|---|---|---|
| H2_FROZEN_NEON_CATALOG_COMPLETENESS | PARTIAL | Frozen two read-only catalogs exist; no complete runtime role/objects/data proof |
| H2_EXACT_SCHEMA_RECONSTRUCTION | PARTIAL | Table definitions and view reconstruction, but ownership/grants and exact runtime absent |
| H2_REVISION_MIGRATION_COMPATIBILITY | BLOCKED | 001 requires real baseline-row preflight and PG18 execution |
| H2_LEAST_PRIVILEGE_ROLE_DESIGN | PARTIAL | Candidate 003/004 are unexecuted; dedicated owner privileges unresolved |
| H2_RESTRICTED_WRITER_PG18_EXECUTION | BLOCKED | No new PG18 runtime |
| H2_CANDIDATE_MIGRATION_ROLLBACK | BLOCKED | Only proposed SQL; no rollback test |
| H2_SEVEN_RUNTIME_CONTRACT_RECONCILIATION | PARTIAL | Definitions recovered, runtime evidence still required |
| H2_INDEPENDENT_GIT_EVIDENCE | PARTIAL | Repository source objects can be Git-read-back; no independently executed verifier on new SQL |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO | Need PG18, migration data preflight and role confirmation |

**Persistent controls:** `203 MATCH / 3 MISMATCH (193,196,197) / 7 UNVERIFIED (183,190,206,210,211,212,213)`; `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`, `C4/C5=NOT PROVEN`, `UNBOUND_UNRESOLVED=25`.

## Narrow next authorization

Separately authorize **read-only Neon catalog and constraint-cleanliness aggregate verification** on exactly `green-cake-44216048` / `br-bold-mode-b5rub8pq` / `neondb`, using only SELECT on pg_catalog, information_schema and aggregate COUNT/GROUP BY over classifications (no row identity/payload disclosure). Include current role membership, ownership-transfer feasibility, effective privileges for intended runtime username, dependencies and approved statement list. A read-only connection may wake suspended compute and incur consumption. **No access or wake-up is authorized or performed by this artifact.** First finish PG18 synthetic executable validation; do not use a live test to compensate for missing offline evidence.

No accepted status transition has been established; PROJECT_STATE.md and CHANGELOG.md on main are deliberately unchanged.
