# C4-E3 — owner review: incomplete exact-field certification

**Verdict: C4_PARTIAL.** This is **not** a C4 pass candidate or an accepted exception. The requested exhaustive Git→Neon and Neon→Git row-by-row comparison **was not executed**. No global discrepancy count has been certified.

## Verified preflight
- `main@539f75d4dbb8c8043ae460432133c7b55ca6f69d`; read `PROJECT_STATE.md` and `CHANGELOG.md`; C4 from immutable `4cc20029:research/neon_migration_closure_audit_2026-10-10.json`.
- C4-E2 `cfacf717096aa91a82d4146b0e45b8324e8dde53`: report blob `46128edba6dfb4603afb12da9c4ee3b5c61c6697`, residual JSON blob `5004e3e1c2dd300f713fc07826e443fe96c81169`.
- Frozen H1 authority Git blob `13d7f6916984940d544e53a3a14c3def91682d43` read; contains 6,863 classification authorities, 2,340 source authorities and 119 modeled relationships, but the artifact itself says full source/event field authority is NOT PROVEN.
- Frozen H2 authority Git blob `2abd72d10bdac896d3c4ed10c582c38aafb162af` read; offline producer truth is not persisted parity. Prior H2 79-case audit `7ed2e426` differentiates 76 replay-only memberships from errors.
- C4-E1 `48e25ad1` registry Git blob `e8715c3f8bcc620f73735c9ba4148162d65ce787` read. Exactly 25 original UNBOUND cases remain pending owner disposition; 18 Kyiv dual-ID cases, two ACTIVE events, 14 source links.
- Neon read-only physical compute `ep-calm-rice-b5073ypp`: `current_database=neondb`, `transaction_read_only=on`, `pg_is_in_recovery=true`; observed 2026-10-28 19:41:55Z, replay LSN `0/1173D520`.
- Actual `information_schema.columns` was read for three tables. This is a schema observation, not complete row parity.

## Required-field contract and normalization
The companion verifier specifies explicit classification/source/event required-field lists. It only normalizes offset-aware timestamps to UTC at microsecond precision, canonicalizes JSON object key order, and treats two explicitly set-valued arrays as unordered. All other lists and values remain exact. No truncation, rounding, arbitrary ID remap, naive timestamp timezone assumption or fuzzy matching is accepted. The Kyiv 18 dual-ID transform must be supplied by independent frozen Git expectations before comparison, never inferred from Neon.

`_frozen_git_blob` is mandatory for each expected row. H2 replay-only memberships require individual frozen provenance classification; the 76 are NOT auto-errors. Fields with no independent frozen authority are `NOT_PROVABLE`, never taken from Neon.

## Specific missing evidence
1. Independently constructed full per-row frozen expected JSONL for H1/H2 classifications, sources and events, with row-level Git blob pointers and accepted repair overlays.
2. Three matching Neon table projections, including resolved `classification_key` in source links and `current_classification_key` in modeled events; all six must originate in **one repeatable-read, read-only transaction**. Individual connector SELECTs do not certify one database snapshot.
3. Git-frozen exact 25 UID registry and required original source membership/event-tip comparisons. All 25 remain in the denominators; optional parent must not be inner-joined away.
4. For H2's 76 replay-only source memberships, original per-link evidence proving source-specific timezone/episode membership, if full historical source semantics is required. This absence alone is NOT a Neon mismatch.
5. Execution proof from a complete input set, resulting exact per-field CSV with directional missing/extra/duplicate counts.

## Snapshot limitation
The MCP SELECT interface executed individual transactions. The sample LSN is **not** a transaction snapshot shared across calls. Do not certify global parity until an identical snapshot is used for all Neon exports, or explicitly record a weaker claim.

## Next minimal owner decision
Do **not** approve C4, its 25 exceptions, historical rewrites or Neon cutover. Authorize one **read-only** reproducible export from the existing physical RO endpoint within one `REPEATABLE READ READ ONLY` transaction and an independent Git-frozen row projection, then execute `verify_c4_e3.py` on those two sources. Reuse accepted H1 verdict/QA and H2 offline key proofs; no classifier rerun or backfill.

No main/site-prod/operational WIP, Neon DML/DDL, replay, A5 or cutover changes were made.
