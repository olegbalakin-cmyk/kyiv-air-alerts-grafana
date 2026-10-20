# H2 ACL raw-catalog residual — separate decision proposal, NOT ACCEPTED

Date: 2026-10-20. Status: **PROPOSAL ONLY; operational migration remains NO-GO**.

## Physical delta identified
The earlier accepted PG18.6 rollback checks and the new bounded A/B probes show `pg_class.relacl` changing from an implicit NULL ACL representation to an explicit ACL on seven canonical relations: `alert_episodes`, `ingestion_runs`, `ingestion_checkpoints`, `current_ingestion_checkpoints`, `attack_event_classifications`, `attack_event_sources`, and `attack_events`. This is a **physical catalog difference**, not proved harmless by a permission spot check. No direct `pg_catalog` update, OID-changing recreation or production alteration is proposed.

## Positive but limited observed probes
The independent offline [A/B run 39472336913](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39472336913) ran actual PostgreSQL 18.6 `pg_dump --schema-only`, four future GRANT/REVOKE checks and a three-ACL-change transaction with controlled SQLSTATE 23514 after changes, then verified the complete sampled catalog snapshot was unchanged after rollback. The observed **raw dump hashes differ**, even for two equivalent snapshots; an additional run 39472597497 showed consecutive unmodified dumps have different raw hashes, owing to volatile restrict/unrestrict markers, and normalized same-fixture dumps match. These tests do NOT establish complete dump-semantic or future-DDL equivalence. New normalized cross-fixture diff must be reviewed separately.

## Narrow acceptance policy requiring explicit user authorization
Only the exact NULL vs explicit `pg_class.relacl` difference on an enumerated immutable set of canonical relations could be considered, and only after passing a complete effective privilege and grant-option matrix across direct/inherited/SET/ADMIN/PUBLIC/default, column/function/schema rights, negative hostile role controls, role membership and ownership changes, future object creation, second application of migration, and normalized `pg_dump` semantics. Require independent A/B execution and byte-accurate frozen original artifacts. If any raw catalog delta outside that enumerated set, any privilege or grant-option change, newly capable app principal, unauthorized object creation/function replacement, dump semantic difference, history mismatch, lock race or unclosed failure appears: **reject**. This is not implicit consent to alter the existing exact-equality gate.

## Residual risk
Migration/rollback operations may affect catalog-sensitive drift detectors, future grantor-sensitive behavior and tooling that inspects ACL representations; a one-time proof does not guard later grants, role inheritance changes or ownership transfers. The dedicated synthetic role administrator remains an external trust assumption. A non-superuser migration-safe integration has not yet been proved with this acceptance policy.

**Decision at this checkpoint:** physical restoration UNPROVEN, semantic-only equivalence NOT ACCEPTED, `H2_ACL_RAW_CATALOG_EQUIVALENCE=PARTIAL`, `H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK=PARTIAL`. No Neon preflight or cutover authorization.
