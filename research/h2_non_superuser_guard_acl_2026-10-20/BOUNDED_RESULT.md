# H2 non-superuser ownership and ACL rollback — bounded offline result

2026-10-20. Research only. This is a **candidate execution report, not an independently accepted global checkpoint**, and not permission for Neon access or deployment.

## Provenance

- Started at accepted predecessor `ac6b88bb3533f1f846f52a3771841636402d5e21`.
- Original PG18.6 A/B `39403057471`: restricted CAS **77/77** per copy, rollback controls **17/17** per copy, full rollback PARTIAL. Original source evidence remains unchanged.
- New candidate SQL: `007_non_superuser_guard_transfer.sql`, `008_non_superuser_acl_rollback.sql`. New isolated harness: `test_non_superuser_acl_pg18.py`.
- First new PG18.6 A/B run [39409022269](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39409022269), tested `79d9d0e3fcefe0a3498cf30f36c922ba2607f8b8`, jobs A `118581903153`, B `118581902883`: **23/23 per copy**, 3/3 scenarios, technical CI SUCCESS, reported migration verdict **PARTIAL**.
- Extended PG18.6 A/B run [39409226309](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39409226309), tested `72c10b8e13edfc60f74f9a0ecd5c4142cfb1af1d`, jobs A `118582574943`, B `118582575230`: **31/31 assertions per copy**, 5/5 bounded scenarios, CI SUCCESS; original logs report `raw_residual=["relations"]`, `verdict=PARTIAL`. No skipped assertions counted as PASS.
- Second-run Actions original artifact metadata: A `12259111057`, 4480 bytes, GitHub digest `sha256:399cc1018ccb9e5235bf94ad5afab7e8204b6dfb0e0c03ae2dd58d033b07b820`; B `12258806396`, 4480 bytes, GitHub digest `sha256:3fd9d1892a59c37388451134928911bc431dc65239fb7285c6e1fe8c6532c3ce`. These are GitHub artifact digests, **not independently downloaded/rehashed ZIP evidence**.

## Narrow bounded results

- PG18.6 synthetic non-superuser migration principal `h2_migrator_test` has no SUPERUSER/CREATEROLE/BYPASSRLS. Bootstrap administrator creates fixture and role topology but **the new 001/v3/007/008 SQL migration steps run using the non-superuser login**.
- Guard-owner transfer and reversal succeeded with temporary `SET TRUE, INHERIT TRUE, ADMIN FALSE` role membership and temporary guard-owner schema CREATE; bootstrap removes privileges outside the transactional SQL. Dedicated guard is NOLOGIN. Application writer lacks guard membership and direct head mutations. Original canonical function retains SECURITY DEFINER and secure fixed search_path.
- Restricted application-login classification INSERT exercised the real protected trigger and advanced the head; historical UPDATE denied. Rollback with committed new history refused without changing the readback snapshot.
- Negative checks covered insufficient membership, missing schema CREATE, app-role attempts, injected transfer and rollback ACL/owner errors, missing migration object on repeated rollback, and an additional database dependency preventing DROP ROLE. These are selected scenarios only, **not the complete user-specified fault/concurrency/SECURITY DEFINER matrix**.
- Effective table/schema privilege matrix matches before and after clean rollback **within tested roles and privilege classes**. Physical ACL catalog still differs: `pg_class.relacl = NULL` is not restored for affected relations after revokes; **H2_ACL_RAW_CATALOG_EQUIVALENCE is not PASS**. Column/function/default-privilege and grant-option exhaustive equivalence is not yet independently closed.
- No direct `pg_catalog` changes, table recreation to alter physical ACL, or unrelated role drop were attempted.

## Explicit unresolved gates

The new 31/31 suite does **not** include the previous **77/77 complete restricted CAS regression under the new ownership topology**; this is a regression gap, even though a real restricted-role insertion passed. It does not yet cover all specified negative controls (concurrent writer during rollback, full PUBLIC/grant-option matrix, role changes and future grant/revoke behaviors, complete invalid-history/SECURITY DEFINER bypass suite). Exact raw ACL equality remains PARTIAL; semantic-only acceptance has not been authorized. The new A/B artifact ZIP bytes have **not** been independently Git-frozen or corruption-tested. The independent Git-only gate therefore remains BLOCKED.

A read-only Neon preflight is **NO-GO pending independent acceptance of the remaining security tests and separate authorization**. No disposable Neon test GO. No live Neon SQL, real role changes, production promotion, operational WIP, site-prod, production updater, historical/backfill/casualty changes, or secrets access occurred.

Preserve `203 MATCH / 3 MISMATCH / 7 UNVERIFIED`; `UNBOUND_UNRESOLVED=25`; `C4/C5=NOT PROVEN`; `NEON_AUTHORITY_ACTIVE=NO`; `PRODUCTION_CUTOVER_EXECUTED=NO`; `WIP_ACTIVATION=NO-GO`.

The accepted `main:PROJECT_STATE.md` and `main:CHANGELOG.md` are not changed by this unaccepted research candidate.
