# H2 full restricted CAS under non-superuser 007 — bounded technical result (2026-10-20)

## Authorization and preflight

This isolated research branch starts from accepted non-superuser research commit `f121686fba92f2028232785ecf154e9de24e771f`. Original coordination `main:PROJECT_STATE.md` and `main:CHANGELOG.md` read first; no accepted newer H2 transition superseded either accepted source. No Neon SQL, Neon API, production, site-prod, operational WIP, historical, backfill, casualty or external polling was executed.

## Full original 31 A/B evidence

Original prior run: [39409226309](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39409226309), tested `72c10b8e13edfc60f74f9a0ecd5c4142cfb1af1d`, A 31/31 PARTIAL, B 31/31 PARTIAL. ZIP originals: A artifact 12259111057 SHA256 `399cc1018ccb9e5235bf94ad5afab7e8204b6dfb0e0c03ae2dd58d033b07b820`, B artifact 12258806396 SHA256 `3fd9d1892a59c37388451134928911bc431dc65239fb7285c6e1fe8c6532c3ce`. Freeze [39433299618](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39433299618) SUCCESS; independent Git-only [39433853650](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39433853650) SUCCESS. Manifest Git blob `31fcf9f59c9e6e369b30bdc61e394db1f86b217d`. 14 deliberate corruptions rejected, original PARTIAL and `raw_residual=["relations"]` unchanged.

## Complete restricted CAS 77 regression using 007

Exact successful tested source: `00563b1eb5cb597fe0d3492ad12ae9c0645b2c6e`; [PG18.6 A/B run 39434358306](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39434358306); jobs A `118667337877`, B `118667338105`, both SUCCESS. Both original reports PASS **144/144**: exact multiset of original 77 CAS assertions (matched against original accepted frozen 77/77 JSON) plus 67 executed topology assertions per environment. Canonical accepted writer, snapshot and monitor main are imported unchanged. Only synthetic fixture provisioning switched from admin 004/005 to actual `001_revision_invariants.sql`, `003_candidate_app_role_v3_atomic.sql`, and `007_non_super_user_guard_transfer.sql` (the actual repository basename is `007_non_superuser_guard_transfer.sql`), under `h2_migrator_test` with no SUPERUSER/CREATEROLE/BYPASSRLS. Initial schema ownership and temporary guard membership/CREATE were pre-provisioned by a synthetic admin, then revoked. SECURITY DEFINER guard owner, path and restricted app DML bans verified. Real writer, same-tip concurrency and stale-rejection, independent COMMIT/readback, caller-owned transaction, error rollback, and monitor.main integration (synthetic external inputs) passed.

Superseded runs [39433657061](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39433657061), [39433976013](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39433976013) and [39434130213](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39434130213) failed for missing pre-existing verifier, missing synthetic writer DSN and over-strict uniqueness of assertion identifiers; preserved, not relabeled PASS.

Original successful A/B ZIP freeze [39434719721](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39434719721) SUCCESS; independent original Git-only verifier [39434946620](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39434946620) SUCCESS. ZIP A artifact 12268903364 SHA256 `5852fef340d2da9af7b09c3607ff6f73cd6a920a68e846aacb718e61136e56d7`; B 12269851414 SHA256 `e33cab4ac64d58ce82a3c7f063d46756ea84b34f9cb4fa27b27af9073987341c`; manifest Git blob `05b9ceaca2fd0f045f0acae0c61472a4955ad5c1`; 16 deliberate corruptions rejected. Source blobs pinned and unchanged.

## Expanded ACL and rollback matrix

Exact tested source commit `884ae6bfe91f271dfcb355ee8c5b25cdd0dfb18f`, [A/B run 39435605595](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39435605595), A job 118671676646, B job 118671676273, both CI SUCCESS with **20/20** executed checks and **3/3** cases. **Both original reports explicitly PARTIAL** because physical `pg_class.relacl` retains a raw relation representation residual. The expanded matrix compared eight principals, table privileges, column-level privileges, schema privileges, function privileges, grant options, PUBLIC, default ACL, role membership and inheritance, and future GRANT/REVOKE operations before and after clean downgrade. Effective privileges and the exercised future GRANT/REVOKE sequence remained equivalent in the tested fixture, while raw catalog did NOT. Negative controls for PUBLIC CREATE and mismatched guard function owner were executed; this was not the entire requested sixteen-case adversarial matrix. The initial run [39435456267](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39435456267) failed from a psycopg LIKE placeholder escaping bug; retained without claiming database security failure.

Original expanded A/B ZIP freeze [39436826709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39436826709) SUCCESS; independent Git-only [39436986079](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39436986079) SUCCESS. ZIP A artifact 12273360123 SHA256 `be1b773f0c65f471f2754fe6f4776d403901a371fadff4e356daac9c252eb24c`; B artifact 12272300948 SHA256 `b3547c3cfdca910481f14c8b678ab5f81657c016215f225454295e9a769e3750`; manifest Git blob `aa039f4fa192f254315be70bc34a58b0af7747e5`, 16 corruption controls rejected. ORIGINAL verdict PARTIAL retained.

## Bounded gate verdicts

| Gate | Status and scope |
| --- | --- |
| H2_NON_SUPERUSER_31_AB_ORIGINAL_EVIDENCE_FREEZE | PASS / two byte-exact artifacts |
| H2_NON_SUPERUSER_31_GIT_ONLY_VERIFICATION | PASS / 14 corruptions |
| H2_NON_SUPERUSER_GUARD_OWNERSHIP_TRANSFER | PASS / synthetic preprovisioned migrator (007) |
| H2_NON_SUPERUSER_GUARD_OWNERSHIP_RESTORATION | PASS BOUNDED / accepted 008 predecessor, expanded clean downgrade |
| H2_FULL_RESTRICTED_CAS_77_REGRESSION_NEW_OWNERSHIP | PASS / exact 77 plus 67 topology assertions in A/B |
| H2_CONCURRENT_STALE_REJECTION_NEW_TOPOLOGY | PASS / same-tip race under new ownership |
| H2_REAL_MONITOR_CALLER_NEW_TOPOLOGY | PASS / actual main with synthetic external inputs |
| H2_INDEPENDENT_COMMIT_READBACK_NEW_TOPOLOGY | PASS / independent synthetic DB |
| H2_ACL_RAW_CATALOG_EQUIVALENCE | PARTIAL / physical relacl residual persists |
| H2_ACL_EFFECTIVE_PRIVILEGE_EQUIVALENCE | PASS BOUNDED / exercised eight-role expanded matrix; not exhaustive |
| H2_ACL_FUTURE_GRANT_REVOKE_BEHAVIOR | PASS BOUNDED / tested GRANT, REVOKE, grant-option and revocation sequence; not exhaustive |
| H2_ACL_REPRESENTATION_RESIDUAL | PARTIAL / explicit relation ACL vs initial NULL |
| H2_ROLLBACK_FAIL_CLOSED | PARTIAL / selected accepted and new controls; adversarial 16-case list incomplete |
| H2_SECURITY_DEFINER_NEGATIVE_CONTROLS | PARTIAL / selected wrong-owner and direct restricted DDL; shadowing not fully proven |
| H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK | PARTIAL / physical catalog not restored and incomplete adversarial matrix |
| H2_PG18_INDEPENDENT_A_B | PASS / both full CAS and expanded ACL suites executed in separate synthetic 18.6 environments |
| H2_NEW_AB_ORIGINAL_EVIDENCE_FREEZE | PASS / original CAS and expanded ACL ZIPs in Git |
| H2_INDEPENDENT_GIT_ONLY_VERIFICATION | PASS / separate original byte, provenance, source checks |
| H2_READONLY_NEON_PREFLIGHT_READINESS | BLOCKED / NO-GO — runtime and migration authority assumptions not verified |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED / NO-GO |

## Remaining requirements and disposition

- Do not approve semantic-only ACL rollback equality merely because measured effective privileges match. Explicit `relacl` representations remain different, and new authority is required for any alternate acceptance criterion.
- The requested full negative matrix still lacks proofs for concurrent rollback/writer lock timing, missing registry, unsafe inherited grants, rollback/owner corruption under broader role configurations, object shadowing, repeated migrations and rollbacks, and additional historical invalid-state cases. Relevant pre-existing negative cases remain narrower accepted predecessor proofs, not universal closure.
- No actual Neon roles, endpoints, records or runtime DDL privilege topology tested; no read-only Neon preflight authorized. Current configuration includes `203 MATCH / 3 MISMATCH / 7 UNVERIFIED`, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`.
- No production or WIP promotion occurred: `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`.

**A. CAS regression:** YES, the complete accepted restricted CAS test behavior passed under the real `007` non-superuser synthetic install in A and B.

**B. ACL and rollback:** effective equivalence and selected future operation equivalence passed within expanded tested fixture. Physical catalog equivalence remains PARTIAL, and full rollback SECURITY DEFINER adversarial verification is NOT complete. No semantic-only rollback acceptance.

**C. Neon readiness:** NO-GO until residual negative controls, schema/role runtime-contract mismatches and a separate offline acceptance review are closed; any future read-only Neon access requires a new exact authorization.

This report is research-only. It is not an independently accepted coordination checkpoint. Do NOT update `PROJECT_STATE.md` or `CHANGELOG.md` on `main` until independent acceptance.
