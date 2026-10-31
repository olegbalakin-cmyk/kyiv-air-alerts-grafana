# C6 DST four-case — isolated repair preflight (2026-10-31)

**Verdict: PARTIAL; OFFLINE_WITNESS PASS; LIVE REPAIR NOT AUTHORIZED.**
This research branch is independent of `research-neon-shadow-frontend-2026-10-31`.
No edits to site-prod/main, shadow workflow, production writer, Neon parent/child,
or coordination roots. Do not run DML from this checkpoint.

## Immutable evidence and freshness boundary

- Coordination main: `C6-UA-CURRENT-ONEGET-01`, GLOBAL_CUTOVER=NO.
- Accepted prior DST evidence: commit `7265e40af6d012267ada515e9cac415f3e1e24b7` (`C6-DST-UTC-01`).
- Accepted independent replay and seven source witnesses:
  `741f277f73d1dde1325069d25fa00b44a42d6f03`,
  `research/neon_cutover_work_2026_10_30/proof/verification02/dst_source_witnesses.json`.
- Historic read-only replica observation **2026-10-30T11:55:07.977Z**:
  project `green-cake-44216048`, branch `br-bold-mode-b5rub8pq`,
  endpoint `ep-calm-rice-b5073ypp`. It is **not a fresh transaction or
  one consistent repeatable-read snapshot**.
- Pinned source `site-prod@09192a36dae49bd71e1042942481384a5e763086`;
  UkraineAlarm bridge Git blob `6838063613592641a520cb42a0d28079701a7261`;
  original `union_alerts()` blob `8b95c4b508b9a473240889603f593e399cf8815d`.
- Source-only accepted replay: 5,699 input intervals / 21 API city keys;
  5,297 wall-time union vs 5,301 UTC union; +4 alerts,
  -9,059.359958 seconds. Not a 23-city full output replay.

## Findings

Three wrong merged physical parents: Kharkiv
`bb7d4952-52a3-45f8-a1db-13153c8f6ca3`, Poltava
`74ba1017-63af-4137-a5ba-246795613615`, Zhytomyr
`b40c570e-f9db-4c7d-b7e4-3f7769e12a95`.
Each requires one old ID to be audited/superseded and two **new** canonical
episode identities created. Cherkasy requires exactly one missing episode;
**preserve** existing valid UID
`ff046d6c-fc7e-4cd2-9470-3e5433c3d582`.

Mechanism: Europe/Kyiv repeated 03:00 local hour at DST fall-back on
2026-10-25. Python comparison/sort of `datetime` sharing the same
`ZoneInfo` can use wall-time ordering and treat fold=0 and fold=1 as
overlapping. The minimal proposed future writer patch is sorting and both
comparisons in `union_alerts()` by `astimezone(timezone.utc)`. Existing
source, timezone representation and touching-interval policy stay unchanged.

Three incorrect rows had **zero links in the four bounded checked tables**,
but absent external dependencies, provenance, classifications and downstream
consumer references remain unproven. Preserve audit/run linkage and old IDs
through an approved versioned lineage strategy; never silently rewrite UUIDs.

## Offline dry run / machine diff

- Fixture: `fixtures/historical_correction_candidates.json` (historic
  exact readback, 3 wrong physical UIDs, 7 candidate intervals).
- Reusable isolated Python preflight: `python offline_dry_run.py` (stdout
  JSON, fail-closed exceptions, no imports of DB libraries).
- Executed independent JS microsecond-aware fixture comparison and preserved
  `proof/offline_machine_diff.json`: **PASS_OFFLINE_WITNESS**.
  Checks: seven candidate ID uniqueness, seven positive intervals, ordered
  nonoverlapping split pairs, 3→7 identity changes, +4 alerts,
  -9,059,359,958 microseconds, no mutations outside fixture scope, and
  preservation of the valid Cherkasy earlier UID. Python script saved but
  **not executed in this session**. No new Neon SELECT or PG17 run.

## Recommended future repair (requires separate approval)

1. Freeze one **new** repeatable-read Neon snapshot with exact city/UTC
   row+legacy+UUID assertions, source hashes and source observation identity.
   Inspect every FK, trigger, view, cache, external consumer, source-provenance
   edge and classification lineage, not just four known tables.
2. Prove UTC writer fix and consistency of canonical ID derivation in a
   separately approved isolated regression. Do not change the shadow proof's
   pinned payload/hash while its physical proof is underway.
3. Define and approve versioned supersede/alias strategy retaining all three
   former UUIDs and their old IDs in an audit trail. Guarded repair transaction:
   conditional checks for the three exact old rows, absence of all seven new
   legacy IDs, no previously unseen dependency, and expected row counts;
   create six split rows plus one Cherkasy row, mark/supersede three wrong
   rows without losing provenance. **Do not delete and reinsert in place**.
4. Independent post-write readback must prove seven new source-bound
   episodes, three archived superseded identities, valid Cherkasy original
   unchanged, no duplicate city/start/end tuples or legacy IDs, no unrelated
   episode changes, +4 total counted episodes, and expected duration delta.
   Rebuild *only affected* city/date KPI and downstream views; confirm
   historical source priority does not change the final displayed metric.
5. Rollback plan must be versioned and tested separately: retain a signed
   before-image and all newly inserted IDs; reverse supersession and
   temporarily deactivate only these seven new records transactionally if
   dependencies permit; independently compare all old rows, IDs, and
   downstream outputs. Abort rollback rather than cascade-delete dependents.

**Hard stop:** changed source hash or Neon snapshot; source conflicts;
unaccounted relationship or classification; existing new ID; mismatched
UTC/local fold or duration; schema/constraint mismatch; missing transactional
rollback; unapproved writer change; consumer/parity mismatch; any concurrent
writer affecting target rows. The checkpoint is not a release decision.

Impact on parallel C6 shadow physical proof: **none from this research branch**.
A future mutation or writer promotion could change readback hashes and must be
coordinated *after* that isolated proof, with fresh shadow baseline.

**Next owner gate:** approve only a subsequent isolated, fresh,
read-only repeatable-read dependency/lineage preflight for these four
cases. Do not authorize historical DML yet.

`C6/C3=PARTIAL; GLOBAL_CUTOVER=NO`.
