# H2 integrated H11/R09 transaction preflight — coordinator review checkpoint (2026-10-21)

**Verdict: PASS BOUNDED — synthetic PostgreSQL 18.6; H2 remains PARTIAL, Neon NO-GO.**
**Disposition: submitted for independent coordinator review; not an accepted operational migration.**

## Source authority and scope

The latest `main:PROJECT_STATE.md` and `main:CHANGELOG.md` were read before implementation and rechecked before this report. Latest coordination main observed `ee4eb821e38a5e37e7dace71637f984b98b4f7f1` includes an independently accepted R6 GitLab checkpoint, **not** a superseding H2 checkpoint. Last accepted H2 predecessor remains the original H11/R09/ACL six-ZIP freeze `21a343c5feb1d17eba5707aa3794f4eb66b2e156`. Other observed refs: `site-prod=1a9e2c1e032d09e4e54405d04cd379a03ccdf2f9`, operational WIP `multicity-wip-2026-09-16=926e039a76acb0e75dfb59619442e9368d8a6f91`. Neither modified.

Isolated research branch `research-h2-integrated-failclosed-preflight-2026-10-21-gpt6` descends directly from accepted H2 source `21a343c5`. SQL builder `research/h2_integrated_preflight_2026-10-21/build_gate.py` verifies exact accepted Git blobs of original H11 SQL (`da0eec8a55e832f159f368af94a79c21953a3901`), original R09 SQL (`1e8e78683cefd147034946ecb191539e2c184a92`) and original 007 migration (`8dc20d11f28db2d8c2b6244b5c43e8bd23548abd`), and composes the accepted migration DDL statements unchanged into one protected transaction. It adds locked H11 diagnostic-to-raise conversion and expanded R09 effective authority checks **before** migration-side GRANT, REVOKE, function ownership or guard modifications. The actual original 007 transfer executes when needed, with a repeatable no-op after successful transfer. SQLSTATE `23514` for historical/transaction invariant faults, `42501` for rejected role authority, `55P03` for timed out competing relation locks. Only synthetic PG18.6 data and provisioned disposable roles; no Neon credentials or endpoints.

## Exact executed PostgreSQL 18.6 verification

**Primary successful workflow run [39499796916](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39499796916)** tested immutable executable commit `780348a2a5a2ae294871bf10bf60c5e394f4afb6`. Two separately provisioned PostgreSQL 18.6 job containers:

| Environment | Original job | Integrated transaction | Original CAS 007 regression | Git-only baseline ZIP verifier |
| --- | ---: | --- | --- | --- |
| A | `118894090566` | `20/20 PASS_BOUNDED` | `144/144 PASS` | 6/6 original H11/R09/ACL ZIP + 8/8 tamper |
| B | `118894090309` | `20/20 PASS_BOUNDED` | `144/144 PASS` | 6/6 original H11/R09/ACL ZIP + 8/8 tamper |

The **20 per-copy integrated cases** include first-time migration on empty and nonempty valid history, repeat after COMMIT with no further changes, missing/stale/orphaned/wrong-identity current heads, duplicate successors/roots, incorrect predecessor identity, cyclic history, real late `007` owner-stage fault after preceding ACL/function modifications, inherited and SET-only owner authority, guard SET-only authority, direct immutable-history UPDATE, application schema CREATE, actual migration-first writer lock contention, writer-first commit/readback, restricted writer timeout and migration lock timeout. Each rejected migration produced the expected SQLSTATE, nonzero psql status, and unchanged persistent history/head/schema/ACL fingerprint in its disposable database. Valid migrations COMMIT and independently read back. Original CAS suite re-executed **the unchanged 77 accepted cases plus 67 real non-superuser 007 topology checks** per A and B.

**Boundary:** The test covers these 20 executed cases, not a certified exhaustive global PostgreSQL role graph. External Neon ownership, potential unrelated application principals and future role/DDL changes remain unknown; permissions checked here are initial preconditions, not permanent enforcement outside the migration transaction. Complete H2 closure not claimed.

## New original A/B evidence freeze

The **original ZIP envelopes** from the successful primary workflow are byte-preserved under `research/h2_integrated_preflight_2026-10-21/original_ab/` and were obtained through the GitHub Actions download endpoint after independent primary run/job/artifact metadata validation. They are **not** reconstructed JSON ZIP wrappers.

| Copy | Original artifact ID | ZIP bytes | ZIP SHA-256 |
| --- | --- | ---: | --- |
| A | `12298879609` | 4774 | `7ca5ccaf557f738261f141b1d0ff7a4f55e89ecfa7a545aefb891cc9820686de` |
| B | `12299242947` | 4778 | `4507eb69b6524aae9412fbbe4f0115c521f0e6476726d1422da8e95fd4349c28` |

Original ZIP freeze branch commit: `da0cebc665c2b9d7c6e40af688fee8e1f7752776`, original manifest Git blob `d920ab99c25176445f9d9efd995d591be8cd3c29`. Successful original freeze Actions [39500372440](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39500372440). Original manifest records run, exact tested SHA, job↔copy↔artifact, ZIP SHA and byte sizes, enclosed CRC, JSON SHA, semantically expected verdict/count. Original A/B ZIP CRC clean; **four original JSONs** pinned.

The independent no-network Git-only [run 39500629652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39500629652), job `118896904904`, SUCCESS, exact verifier-tested research HEAD `0ac67b325af5f7b8021de056aa692c7f59968186`, checked 2/2 original ZIP, 4/4 original JSON, 7/7 executed-to-final relevant source blob identities, **10/10 real negative-control rejection**: wrong job, copy, artifact, tested SHA, ZIP hash, member hash, verdict, size, ZIP bit flip and repacked changed JSON. Previous failed freeze run `39500234563` (Azure signed URL bearer) and failed verifier run `39500552985` (previously missed manifest verdict field) preserved as failed predecessors; not relabelled PASS. No source SQL/migration/harness edits in report-only transition.

## Gate dispositions for coordinator

| Gate | Verdict | Explicit ceiling |
| --- | --- | --- |
| H11 integrated fail-closed historical-head invariants | **PASS BOUNDED** | Tested malformed history cases in disposable PG18, pre-DDL |
| R09 integrated effective-role precondition | **PASS BOUNDED** | Selected inherited/SET/direct/schema/function routes; external role topology unverified |
| Actual concurrent restricted writer vs migration | **PASS BOUNDED** | Real sessions, lock acquisition/timeouts, COMMIT/readback; no global future-role guarantee |
| Atomic rollback/COMMIT/idempotent repeat | **PASS BOUNDED** | Actual `007` owner late-fault; original `008` ACL late-fault still separate |
| CAS regression after migration/guard-rights change | **PASS BOUNDED** | 144/144 each A/B in separate independent PG18.6 containers |
| Original A/B ZIP + independent Git-only attribution | **PASS BOUNDED** | Exact original 2 ZIP, four JSON, 10 tamper rejections |
| Full H2 ACL/role/rollback closure | **PARTIAL / NO-GO** | Actual `008` late ACL fault, physical `relacl` residual (seven objects), future owner/DDL/topology and remaining invariants |
| Neon read-only / disposable test | **BLOCKED / NO-GO** | No Neon access authorized or attempted |

Carry accepted unresolved contract: `203 structural MATCH / 3 DB-invariant MISMATCH / 7 runtime UNVERIFIED`, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`.

**Hard holds retained:** `NEON_AUTHORITY_ACTIVE=NO`; `PRODUCTION_CUTOVER_EXECUTED=NO`; `WIP_ACTIVATION=NO-GO`; `H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO`; `H2_DISPOSABLE_NEON_TEST_READINESS=BLOCKED/NO-GO`.

No Neon SQL/API access, real user or production data, site-prod/production deploy, operational WIP writes, R6/casualty/historical/backfill modifications, GitHub Secrets edits or coordination `main` documentation updates. **Next separately authorized H2 task** after coordinator review: independently demonstrate actual `008` late ACL-stage fault with exact physical catalog/role/function/ownership rollback and resolve seven `relacl` differences; then continue external role-topology and remaining invariants before any new Neon authorization.
