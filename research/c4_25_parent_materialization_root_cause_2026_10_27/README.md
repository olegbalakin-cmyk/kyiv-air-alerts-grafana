# C4 — canonical-parent writer materialization root cause (Git-only)

**Scope:** exactly the accepted 25 historically UNBOUND classification identities. This extends the accepted immutable 25-record registry (commit `d1c0e55830f0cdf89bb38140321567f997405719`), not the source-episode proof or separate 79-link investigation. No Neon SQL, classifier replay, data changes, backfill or production deployment.

## Findings and bounded statuses

| Finding | Cases | Interpretation |
| --- | ---: | --- |
| Historical identity/writer nonmatch mechanism established | 21 | 18 Kyiv exact Oct-1 writer-input intervals differ; 3 Lviv rows physically existed under original IDs, then their IDs and boundaries were superseded |
| Historically materialized physical parent UUID proven | 3 | Lviv original exact rows read back, same UUID retained after canonical boundary repair; **not currently eligible** for original historical ID |
| Specific mechanism still NOT_PROVEN | 4 | Sumy 1, Zaporizhzhia 1, Kharkiv 2: no individual exact writer input/readback proof |
| Currently eligible canonical parent UID established for the original 25 historical identities | 0 | This is a separate stronger admission requirement |
| C4 parent admissions unresolved | 25 | No binding or permanent exception approved; **C4 = NOT_PROVEN** |

The original H1/H2 historical source alerts were already independently proven and are **not revalidated as this investigation's deliverable**. The new case registry preserves the original 25 classification keys and source witnesses and pins each relevant code/proof artifact by commit/path/Git blob SHA.

## Writer timeline and identity

* **Phase-1 Lviv:** Original bounded historical coverage begins 2025-09-01 local time, with the historical end exclusive 2026-09-18 local time, Lviv only. The first production shadow Action run was `36470761961`, which found 126 existing episodes; this does not imply any other city was included.
* **Multicity:** October 1 permanent shadow bootstrap `36918355446`, 23 cities, 27,966 closed AIR canonical parent episodes, 27,840 new, 126 existing. Enabled workflow push `36918554947` used a new 27,981-episode canonical corpus and inserted 15; the first natural scheduled run `36922008009` processed 27,985 episodes. These are positive per-run accounting witnesses, not unconditional individual proof of every historical episode's presence.
* **Identity:** The writer uses `sha256(city|UTC-start-Z|UTC-end-Z)[:24]`, after final canonical union boundaries, and persists `legacy_episode_id`. The DB `episode_uid` is `gen_random_uuid()`; it cannot be inferred from SHA24 or a municipal episode ID. Candidate eligibility is city in current 23-city set, closed AIR, `alert-canonicalization-v1`, end after start, timezone-aware full-precision boundaries, conflict-free identity.
* **18 Kyiv:** Original historical municipal IDs `kyiv-...` map to deterministic historical SHA24 through exact source intervals. Comparison with the pinned Oct-1 actual Kyiv production output proves none of the 18 exact *historical* intervals was present in that writer input. Similar-minute starts/ends are diagnostics **only**, never eligibility or a parent binding. It does not prove that no earlier/later independent parent exists or that an approximate interval should be linked.
* **3 Lviv:** Early Phase-1 source rows match old SHA24/precise intervals; the initial DB readback includes their physical UUIDs. A later permanent branch repair updated the *same* physical UUIDs to different final canonical boundaries and SHA24 IDs. The original IDs therefore lost exact present-day eligibility. One Lviv repair report shortens the third old ID; the independently pinned pre-repair readback and original registry retain the complete ID. No repair report typo is propagated into the historical identity.

The four remaining non-Kyiv/non-Lviv cases require original full-precision producer-input matches or per-episode writer execution evidence. Their presence inside the writer's broad calendar or city scope is not an exact admission receipt.

## Minimum separately authorized read-only Neon investigation

Run only on the independently approved **specific** permanent-shadow Neon branch, with scoped RO credentials and no DDL/DML. Use an ephemeral parameterized values relation for the 25 `(ordinal, city_key, canonical_sha24, UTC start_at, UTC end_at)` tuples from `registry.json`, rather than a free-form fuzzy search.

1. Return every exact `public.alert_episodes` match on `(city_key, legacy_episode_id, start_at, end_at)`, including `episode_uid`, `alert_type`, `episode_state`, `canonicalization_version`, `created_by_run_id`, `updated_by_run_id`, `created_at`, `updated_at`.
2. Return separately any row matching the same `city_key` and ID but a different interval, or the same exact interval with a different legacy ID. No overlap-based binding.
3. For the three Lviv historical UUIDs, return their **current** exact row identities and `created_by_run_id`/`updated_by_run_id`. These are historical identity-crosswalk diagnostics, not authorization to reparent.
4. For each matched writer run ID, return `ingestion_runs.run_kind`, `status`, `ingest_committed_at`, `github_run_id`, `workflow_sha`, `input_ref`, `input_sha`, and recorded parameters/stats; compare against the pinned producer Git SHA and full-precision intervals.
5. Return per-city aggregated `created_by_run_id` and oldest/newest interval boundaries only if exact episode investigation leaves a specific coverage ambiguity. Do not claim a record was absent from historic DB state merely because a current SELECT found zero rows.

A database read today cannot by itself establish that a 2026-10-01 transaction once omitted or rolled back a particular candidate. That requires an original writer-input manifest, per-record receipt, transaction log, or historical exact snapshot artifact.

**No data repair or historical contract change approved**. If all exact historic input and physical-parent avenues fail for a case, ask the coordinator to evaluate an individually justified exception, not automatic acceptance of UNBOUND.

## Independent offline validation

`python3 research/c4_25_parent_materialization_root_cause_2026_10_27/verify_independent.py`

The verifier reopens pinned Git objects, checks the immutable 25 identities and canonical hash derivation, reads the old Lviv exact physical rows and permanent repair crosswalk, checks the exact Kyiv producer-input mismatch, confirms bounded writer-run counts, and rejects 10 negative mutations (including fabricated parent UID, unauthorized binding, unsupported cause promotion and wrong writer proof). No PostgreSQL connection. CI: [run 40493060618](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40493060618), **SUCCESS** on `94b823270e07947e91f6c8dc2174cb4f4573e930`, with 25 rows, 21 bounded causes, 3 historical physical UUIDs, 4 unknown causes, 25 outstanding parent admissions, 10/10 negatives.

No `main` or `site-prod` edits. Update coordinator documents **only after coordinator acceptance**.
