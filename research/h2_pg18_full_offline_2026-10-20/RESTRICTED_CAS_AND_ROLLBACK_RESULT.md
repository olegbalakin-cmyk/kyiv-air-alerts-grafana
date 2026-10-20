# H2 restricted CAS and full rollback — isolated PostgreSQL 18.6 research result

Date: 2026-10-20. **CANDIDATE RESEARCH RESULT, NOT OPERATIONAL ACCEPTANCE.** No Neon operations, secrets, production, site-prod, WIP, historical/casualty/backfill or cutover changes.

## Coordination and source

- Preflight read `main:PROJECT_STATE.md` and `main:CHANGELOG.md` at `main=7d5ddca9128c685be2f7bf179be391bd121b4b84`.
- Separate `site-prod=050844ec9b1b57d321012805d0b259298dac25f2`, operational WIP `multicity-wip-2026-09-16=c0958add441b42e5a6400c39737fda0b0da6637c`.
- Source baseline: `research-h2-pg18-full-offline-2026-10-20@3a9abb41dd6c5804742c8c99ab663820cd40d016`.
- Accepted real CAS, snapshot and monitor source pinned to `3c1cf86ac0eaee1b1de246022c19acbb58037948` in a second checkout; source files unchanged.
- Tested new implementation `1a1a63e61eef1e43bb7eefbb5a736bf920e56071`.
- Independent A/B PostgreSQL 18.6 GitHub Actions [run 39403057471](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39403057471), jobs A `118562242581`, B `118562242600`. Each used a fresh separate PostgreSQL 18.6 service, synthetic non-owner login `h2_app_ingest_writer_test`. Setup and migration administration used synthetic superuser `h2_local` but never as the application writer.

## Executed results and evidence ceiling

**Gate A: PASS in reduced synthetic PG18 scope.** Real expected-tip CAS writer and `monitor_explosion_candidates.main()`: **A 77/77 PASS; B 77/77 PASS**. Ten cases: v3 privilege denials/legitimate full write, first write and revision/idempotency, authority rejections, independent conflicting sessions (one committed, one stale), rollback failure stages, caller-owned outer rollback and commit, batch independent readback, CAS bypass negative control and genuine monitor-main synthetic source injection. Positive state uses classification/event/source/head; stale classifications produce no falsely acknowledged checkpoint or completed due work. Network publishers and filesystem outputs are controlled synthetic adapters. Underlying schema is reconstructed partial PostgreSQL fixture, not independently proven identical to Neon.

**Gate B: PARTIAL despite A 17/17 and B 17/17 executable checks.** The guarded versioned rollback executes clean and rejects committed post-migration revisions, missing objects, injected ACL/ownership failures and repeated rollback, with SQLSTATE 23514 and consistent persisted readback. Restores object list, ownership, roles, history and effective table privileges in the observed fixture. However raw `pg_class.relacl` after rollback contains explicit owner-only ACLs rather than original catalog `NULL` values; evidence explicitly records `acl_physical_residual=["relations"]` in each original report. Thus exact physical ACL snapshot restoration is **NOT PROVEN**, and superuser-installed guard-owner/reverted owner does **NOT PROVE** required non-superuser ownership-transfer topology. A source-specific general migration from real Neon schema is NOT authorized or proven.

Original new reports retained byte-identically in Git under `research/h2_pg18_full_offline_2026-10-20/new_original_artifacts/`: A/B ZIPs as Base64, A/B CAS and rollback original JSON bytes, and manifest with source-run, job IDs, byte sizes, and hashes. Original Actions artifact IDs A `12255266791`, B `12255171980`; ZIP SHA-256 A `0a69658981b022cd20e6b9a3161ed5b30038ff01c69993274535b8c9294af887`, B `927ab91176e15385d5ccc72179e9aba15535cc90902ca9b5159ebf6df127fe7c`. Original JSON SHA-256:
- A CAS `d04caad4c127b8bb47f2b5eefb0c9ce891391e26e0cd1d66f5c129f4b203b20f`; A rollback `37360a637ff897b56ad2f39b7a8e282ac2edf0cfb8ef9ef83999213b209ec4d1`.
- B CAS `65cf8ed74cfcb1cae84c6bfa18416c1b3f36eacca8744d4a63e146cffed3553e`; B rollback `d50dd55e5827ea3a192e134e2714ec933805377cfbd5f2e2e1bc114824af30ea`.

Evidence archive [run 39403424188](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39403424188) SUCCESS, new frozen proof Git commit `6640020a7e5cdf46c2589993762337ed3ecabc19`; independent Git-only [run 39403558373](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39403558373) SUCCESS on commit `6e5f93f90ec233592c9b641fffbfd3dfb5dafc0e`: 2 ZIP CRC, 4 exact JSON reports, 8 corruption rejections, verified all three executable candidate files retain tested Git blobs. Original preceding v3 A/B ZIPs also passed their original Git-only verifier in the PostgreSQL jobs.

## Required verdicts (same tested commit and PG18.6 A/B)

| Gate | Verdict |
| --- | --- |
| H2_V3_AB_ORIGINAL_GIT_VERIFICATION | PASS, Git-only original pair |
| H2_RESTRICTED_WRITER_FIRST_WRITE | PASS, synthetic |
| H2_RESTRICTED_WRITER_REVISION_CAS | PASS, synthetic |
| H2_RESTRICTED_WRITER_CONCURRENT_STALE_REJECTION | PASS, synthetic |
| H2_RESTRICTED_WRITER_EVENT_SOURCE_INTEGRITY | PASS, synthetic |
| H2_RESTRICTED_WRITER_COMMIT_READBACK | PASS, synthetic |
| H2_RESTRICTED_WRITER_TRANSACTION_ROLLBACK | PASS, tested stages |
| H2_REAL_MONITOR_CALLER_RESTRICTED_ROLE | PASS, real main / synthetic external adapters |
| H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK | PARTIAL, raw relacl not identical |
| H2_NONSUPERUSER_OWNERSHIP_TRANSFER | BLOCKED, topology not executed |
| H2_PG18_A_B_EXECUTION | PASS execution, Gate B acceptance PARTIAL |
| H2_ORIGINAL_NEW_EVIDENCE_FREEZE | PASS, Git original ZIP/JSON |
| H2_INDEPENDENT_GIT_ONLY_VERIFICATION | PASS, separate CI and readback |
| H2_READONLY_NEON_PREFLIGHT_READINESS | BLOCKED |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED |

The first two broad migration-security gates remain insufficient for live use. Exact production migration precondition matrix, full SECURITY DEFINER adversarial cases, non-superuser deployment/role transfer, physical relacl restoration, independent full Neon schema parity and runtime environment contracts remain unresolved.

Next bounded isolated task: validate minimal non-superuser guard ownership transfer and restoration under a deployment-like role graph; explicitly decide whether effective-privilege equality suffices or redesign the ACL migration/rollback to preserve exact catalog representation, then test cross-database role dependencies and full invalid-history / privilege-precondition matrix. Only after independent acceptance request separately authorized **read-only** Neon preflight. NO disposable Neon write GO.

**Preserve unchanged:** `203 MATCH / 3 MISMATCH / 7 UNVERIFIED`, `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`, `C4/C5=NOT PROVEN`, `UNBOUND_UNRESOLVED=25`.

`PROJECT_STATE.md` and `CHANGELOG.md` were not updated because this is unreviewed new research candidate, not independently accepted migration closure.
