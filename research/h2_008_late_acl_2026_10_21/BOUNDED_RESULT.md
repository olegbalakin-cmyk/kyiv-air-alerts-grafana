# H2 actual 008 late ACL rollback and physical ACL residual — bounded report (2026-10-21)

**Result: PASS BOUNDED for actual 008 late-fault atomicity; PARTIAL / NO-GO for exact physical ACL restoration and full H2 closure. Not operationally accepted or promoted.**

## Authority and source

Mandatory preflight checked current `main:PROJECT_STATE.md` and `main:CHANGELOG.md`; accepted integrated H11/R09 checkpoint is `327caba41942346abc630d7f567d8b0ddc814ae8`. Research branch `research-h2-008-late-acl-rollback-2026-10-21-gpt6` originates from that immutable accepted commit, without changing main, operational WIP, production, Neon, secrets, R6 or other tracks.

The **actual accepted** `research/h2_non_superuser_guard_acl_2026-10-20/008_non_superuser_acl_rollback.sql` Git blob is `59eab59235f8aee14837ce7494649edba674e1ce` and is unchanged. Research `008_late_fault_instrumented.sql` is additive only, Git blob `54dbeb7945929a3dd4f808b82d96b01079cd35b0`. It inserts a DO checkpoint between original relation/column REVOKEs and the remaining original schema REVOKEs. The checkpoint independently checks the *absence after REVOKE* of original preexisting SELECT, INSERT and column UPDATE permissions. Its optional `fault=late_acl` raises `H2_008_LATE_AFTER_REAL_ACL_REVOKES`, SQLSTATE `23514`, before original COMMIT. Removing the one additive block reproduces the original accepted 008 byte-for-byte.

## Primary executable PG18.6 evidence

Original successful Actions run [39504096121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39504096121), tested commit `5213a91ae593a3ef80f4936d55c7ec08c4a5737e`; A job `118908548277`, B job `118908548485`, both SUCCESS, **15/15 checks per copy** with explicitly **PARTIAL overall** because physical ACL drift remains. The instrumented late failure happens after real SQL REVOKEs, with logged `SELECT_PRESENT=f INSERT_PRESENT=f COLUMN_UPDATE_PRESENT=f`; error `23514` and nonzero execution status. Before/after full sampled catalog snapshot and effective table/schema privilege matrix match exactly after transaction abort, including function definitions/owners, column and schema ACL representation, role membership, default privileges, and history MD5. The original 008 completes successfully separately; no-fault instrumented 008 produces the same catalog as the original 008.

Original successful A/B ZIP artifacts: A `12303147740` (6287 bytes; SHA256 `3fa001cca4c277f8e7cb481832f38ad4ee960a12b459b845009154d6ed653f49`), B `12301873679` (6284 bytes; SHA256 `40fbb25ba0e3268c7aca6e00ffe81bb154d4c6a7b6af1508f6b405871120cac4`). Enclosed original JSON: A `h2_008_late_acl_A.json` 88030 bytes SHA256 `62fa8ce21ebc08f07cfbb9ee02793e77598cc8d9235381cffca9ff96e00ae45f`, CRC32 3324285729; B `h2_008_late_acl_B.json` 88030 bytes SHA256 `6d3cec773dd7091c23037a97463bd1e0dcf7fcbd8c13cd47b2ac7341e772cbb5`, CRC32 942302388.

Original Actions ZIP bytes, *not reconstructed ZIPs*, are frozen at `research/h2_008_late_acl_2026_10_21/original_ab/{A.zip,B.zip,manifest.json}`; [freeze run 39504469557](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39504469557), job `118909825041`, SUCCESS; archive commit `126f9fa4ae979e23019a364fffad9b21bad3abde`; manifest Git blob `b77f935effb714f5f2bb63f48a085018ed9914f4`. Source identities match tested commit.

Independent immutable **Git-only** [run 39504652475](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39504652475), job `118910441187`, SUCCESS, source at `85fded1e8ec2ff327c691d3b0fad068375fdd2fd`. Its verifier confirms 2 original ZIP digests/sizes, exact enclosed JSON SHA/size/CRC, 15 PASS checks per copy with preserved overall PARTIAL, correct job→copy→artifact/tested commit/source mapping and **11/11 true negative tamper attempts rejected** (job, artifact, run, tested commit, SQL source Git blob, ZIP digest, size, member CRC/digest, ZIP bit flip, swapped copy ZIP).

Earlier own runs `39503823719` (test harness took snapshot outside temporary role membership), `39503929917` (`pg_dump` client 16 vs server 18) and original-freeze attempt `39504365820` (bearer token mistakenly forwarded to signed blob URL, HTTP 401) are historical **FAILED**, not proof. They were corrected prior to passing primary and freeze runs.

## Exact physical relacl discrepancy

All seven relations below have **before** `relacl IS NULL` and **after successful 008 rollback** `{h2_schema_owner_test=arwdDxtm/h2_schema_owner_test}`:

1. `alert_episodes`
2. `ingestion_runs`
3. `ingestion_checkpoints`
4. `current_ingestion_checkpoints`
5. `attack_event_classifications`
6. `attack_event_sources`
7. `attack_events`

The seven physical residuals are **not** eliminated by 008. A tested supported follow-up GRANT/REVOKE sequence on `alert_episodes` kept `relacl` explicit. This is **NOT** proof that every possible supported sequence fails, and there is **no verified safe supported method to restore physical NULL** at this checkpoint. System-catalog updates and OID-changing canonical table recreation were neither attempted nor authorized. Strict physical restoration **NOT PROVEN / BLOCKED**.

The bounded independent follow-up compared effective sampled relation/schema grants for six roles and executed multiple supported GRANT/REVOKE (including GRANT OPTION) and table ownership transfers, future table creation/alteration/owner/grant/drop, and function create/alter owner/grant/revoke/drop on both control and rolled-back databases; observed statement outcomes match. PostgreSQL 18.6 normalized `pg_dump --schema-only --no-owner` control and rolled-back hashes both `fbae79c3e61142a5cfbd4fdbdef9b1a7b77e9a95817ee09fa96c6e611148609e`, no normalized diff. Raw dump bytes/hashes differ due volatile dump restrict/unrestrict markers. Equal normalized dumps are not equal physical catalog representations.

## Explicit scope limitations

This suite used synthetic fixtures with empty initial classifications; it did not exercise a populated current-head registry and independent row-by-row current-head integrity against nonempty histories, nor all external inherited effective role/GRANT OPTION paths. The snapshot includes history MD5 and heads relation, but **not independently enumerated nonempty current-head row records**. Direct column/function/default ACL snapshot comparisons cover the tested fault; complete separate all-principals effective column/function/schema/owner privilege matrix and future default-privilege/new-object combinations remain **UNTESTED/NOT EXHAUSTIVE**. No Neon role topology readback was performed. The accepted earlier CAS 144/144 × A/B remains inherited evidence and **was not rerun** in this task; neither accepted original 008 nor original 007 rights or production guards changed.

## Coordinator decision

- `H2_ACTUAL_008_AFTER_3_REAL_ACL_CHANGES_FAULT=PASS_BOUNDED`
- `H2_ACTUAL_008_LATE_FAULT_TRANSACTION_ATOMICITY=PASS_BOUNDED`
- `H2_008_ORIGINAL_VS_INSTRUMENTED_NOFAULT=PASS_BOUNDED`
- `H2_008_SUPPORTED_FOLLOWUP_DDL_SAMPLE=PASS_BOUNDED`
- `H2_008_NORMALIZED_PGDUMP_SAMPLE=PASS_BOUNDED`
- `H2_008_ORIGINAL_AB_GIT_FREEZE=PASS_BOUNDED`
- `H2_008_INDEPENDENT_GIT_ONLY_VERIFIER=PASS_BOUNDED`
- `H2_ACL_RAW_PHYSICAL_EQUIVALENCE=PARTIAL/BLOCKED`
- `H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK=PARTIAL`
- `H2_FULL_SECURITY_AND_NEON_GATES=NO-GO`

**Recommend accepting only bounded late-fault atomicity + exact archival proof**, not full H2 rollback/security closure. An optional semantic-only exception could be proposed *separately*, restricted to the enumerated exact seven `relacl` NULL→owner-only explicit differences and gated by independent complete effective ACL/grant option/role inheritance/default privilege/future DDL and audit-equivalence tests. Residual risks: physical drift in raw catalog/diff tooling, grantor-specific future behavior, untested external role graphs, and security policy regression. **Proposal NOT ACTIVATED and NOT ACCEPTED**. Preserve `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`, `WIP_ACTIVATION=NO-GO`, `H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO`, `H2_DISPOSABLE_NEON_TEST_READINESS=BLOCKED/NO-GO`. No main coordination docs modified; this report is for separate coordinator acceptance.
