# C6-R3 owner review — partial research proof, NO production reader switch

## Scope and verified state
Preflight `main:PROJECT_STATE.md`, `CHANGELOG.md`; main `86e842310a6f202126aec5ea0e8037d8bee7523f`; site-prod `552de9cfc8ee7fff7e169caf0a928f4e17ca9cb2`; operational WIP `d834aad2a175c71217da9cab102ffd54bda3b3bc`. R1 `3b30d625`, R2 `b308b398`.

Existing physical Neon replica `ep-calm-rice-b5073ypp` has read_only compute; SQL returned transaction_read_only=on, pg_is_in_recovery=true. A single MCP SQL transaction explicitly set `REPEATABLE READ READ ONLY`; snapshot `429056:429056:`, WAL replay LSN `0/117CE058`. A read-only query exported all 184 October candidate pairs, all linked classification metadata, nine A5 alias rows and UNBOUND counts under this one snapshot. This **does not** constitute executing the new Python reader against Neon.

## Lineage decision
184/184 distinct minute/precise pairs, one-to-one by minute floor; 184 `TEMPORAL_MATCH_ONLY`, 0 `IDENTITY_SUPPORTED_BY_INDEPENDENT_LINEAGE`. Source bytes/hashes and independent source episode lineage are not established. In the selected snapshot, none of the 184 pairs shares `created_by_run_id` or `legacy_episode_id`; therefore lineage equivalence cannot be inferred merely from timestamps or matching canonicalization versions. No October production mapping is authorized.

## Relationship preservation
Linked classification records: 28 minute-side and 27 precise-side (55 total). Nine September A5 BOUND classifications present. Historical 25 UNBOUND/NULL, 14 source memberships, 2 ACTIVE events present. All SQL was read-only, with no persisted FK or event mutation. Runtime downstream end-to-end preservation and canonical classification tip equivalence are NOT CERTIFIED.

## Reader implementation status
Research Python wrapper committed as code proposal: uses one read-only repeatable-read transaction with early explicit exception for unknown October candidates; never calls a consumer until after relationships pass. This code has **not** run against live Neon or disposable PG16 in this interaction. Its isolated synthetic test suite and workflow definition are present but are **not** executed proof. The wrapper does not yet independently validate the complete manifest from Git or compute identity; see README. October hard-fail is an implemented candidate behavior, **not PROVEN by execution**. Code only is not a green release gate.

## Release decision
`C6_R3_PARTIAL`. `C6_PRODUCTION_READER_SWITCH_AUTHORIZED=NO`. `NEON_AUTHORITY_ACTIVE=NO`. `PRODUCTION_CUTOVER_EXECUTED=NO`.

Before C6-R3 can become FAIL_CLOSED_PROVEN_MAPPING_PENDING: run disposable PostgreSQL 16 fault matrix (all required scenarios, not a subset), execute the wrapper live against one authenticated Neon read-only transaction with 190/190 source parity and October hard-fail, verify independent lineage for any accepted mappings, add exact Git input-blob/manifest and compute assertion, finish production consumer inventory, execute exact-SHA Actions and independently validate ZIP/artifact hashes.

No `PROJECT_STATE.md` or `CHANGELOG.md` mutation pending coordinator acceptance.
