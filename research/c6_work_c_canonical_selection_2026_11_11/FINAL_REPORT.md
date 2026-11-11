# C6 Work C — safe canonical episode selection (research-only)

**Decision:** Exact-run selection implemented and tested. It is NOT a general future-proof canonical-state rule, and is NOT a Neon cutover authorization. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Frozen identity

- Accepted main coordination state: `C6-POSTMERGE-C2-EXPORT-23-01`; Work B proposed checkpoint remains draft [PR #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74), unmerged; Work A separate [PR #70](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/70).
- [C2 #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190), real artifact #13873291895; bundle SHA256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`.
- Manifest corpus SHA256 `4cd2fce445e49ec200ea3a202ed8bf9e1ada9c17d60c23eb7e9c7c65e1526226`; canonical ingestion run `f7da738b-9f8c-4845-bbe9-2a8073477dcb`.
- Database branch `br-bold-mode-b5rub8pq`; exact C2 commit timestamp `2026-11-11T16:34:13.678Z`. Read-only SQL found max AIR row update `2026-11-11T16:34:11.263Z`, with zero AIR rows updated after commit.
- Independent read-only SQL rechecked raw `33,397` closed AIR rows across 23 cities, zero rows mutated after C2 completion and no missing legacy IDs. Exact C2 canonical projection: `33,135`, 23/23 cities matching sorted legacy IDs and seven-field tuple digests (city, type, boundaries, state, canonicalization version, legacy ID). SQL's latest-overlap rule was used **only diagnostically**, never in the new reader.
- Work B CSV has 262 unique stale IDs in 10 cities; read-only SQL confirmed all 262 currently exist in Neon as closed AIR. None is in the immutable C2 canonical payload.

## Root cause and scoped change

The existing generator snapshots every AIR episode and `verify_snapshot()` passes all completed rows to `generate()`. Existing `validated_neon_rows()` checks exact C2 membership but that checked subset was discarded before generation, so 262 stale rows could affect history and projection lineage.

New `scripts/c6_exact_canonical_selection.py` selects **only exact members of the already SHA-verified C2 payload**. The existing `neon_json_shadow.execute()` already verifies corpus SHA, receipt/run identity, all seven field values against Neon and the read-only snapshot; it now additionally selects the same exact C2 ID set for the generator, guarding all seven fields, UUID, complete city coverage, duplicates and the C2 ingest-commit boundary. Unknown historical rows remain in the database and `readback_proof.json` full-table hashes. `canonical_selection.json` is an additional isolated research proof; never a sixth/seventh frontend publication file.

**Important:** this does not treat overlaps as duplicates and does not delete or update Neon. Two distinct overlapping canonical C2 events both survive; any unknown record is excluded solely because it is absent from the exact verified C2 snapshot, not because of its timestamp relationship.

## Regression

- GitHub Actions initial #43100697165: synthetic overlapping-event tests PASS; first ZIP extraction step failed due to wrong assumption about already-unpacked artifact. Workflow-only fix: `f8014472c3783effe43aec16c929bbe6939965d1`.
- GitHub Actions [#43100749008](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43100749008): synthetic regression and full 23-city exact C2 offline replay over original bundle plus Work B inventory. Expected: 33,135 selected/262 excluded, exact IDs, UTC bounds, status/type/version, all 23 cities.
- Offline full replay synthesizes Neon-like row wrappers for the **real C2 payload** and the **real 262 Work B CSV rows**. It does not claim that synthetic UUID wrappers are a fresh physical Neon snapshot. Independent real Neon SQL was checked separately.

## Limits / further narrow action

This is an exact-run answer, not a timeless DB canonical classification. If a new C2 run occurs, a **new immutable corpus and SHA-bound ingestion receipt must be used**. The reader fails closed if any DB row has been updated later than that C2 ingestion commit; no fallback to raw rows, age-order or overlap selection.

For a reusable DB-only canonical query without a new C2 payload, the current schema lacks a reliable `is_current`, `superseded_by`, or effective membership set. Minimal future contract proposal (NOT implemented): persist `canonical_membership(run_id, episode_uid, legacy_episode_id, corpus_sha256)` or a run-scoped association equivalent, populated atomically by the existing C2 writer. Reader requires a successful matching ingestion run, explicit full per-city membership and SHA/field parity; historical rows remain untouched. A bare `superseded_by` inferred from overlap is prohibited. This requires separate design review and migration approval.

Other blockers unchanged: Work A independent physical Neon-to-JSON six-file proof, source completeness/origin, Sevastopol `25006→25008`, DST baseline and C3 publication/rollback. No Neon writes/deletes, source HTTP, production change, merge, deployment, DST activation or cutover.
