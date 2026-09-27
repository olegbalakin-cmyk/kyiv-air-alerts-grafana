# Phase-1 PostgreSQL / Neon contract v1

Date: 2026-09-27  
Scope: architecture contract and schema only

## Repository baseline and isolation

The authoritative preflight and the actual branch-creation state match:

| Branch | Preflight SHA | Actual SHA |
| --- | --- | --- |
| main | 8c9c212c6854bbd83c5a65227e256b13676d4428 | 8c9c212c6854bbd83c5a65227e256b13676d4428 |
| site-prod | 1bacbc46302f44a79bd0c6125816c3451772daa1 | unchanged/read-only |
| multicity-wip-2026-09-16 | 9ffc0510d40c8be760d8b0262959d931a8dcdaf5 | unchanged/read-only |

The implementation branch is **db-phase1-pilot-2026-09-27**, created from the actual main SHA above.

The production updater remains **.github/workflows/update-netlify-site.yml** on main and still checks out site-prod. This Phase-1 branch does not alter that workflow, site-prod, multicity-wip-2026-09-16, historical replay, classifier logic, dashboard code, Netlify configuration, or the active attack-event campaign.

Target topology:

~~~text
sources
  -> PostgreSQL / Neon canonical operational store
  -> export/materialization
  -> dashboard_data.json
  -> Netlify
~~~

The production site remains static. Phase 1 does not make the database production-authoritative.

## Phase-1 scope

Phase 1 defines exactly four main persistent tables:

- alert_episodes
- alert_episode_sources
- ingestion_runs
- ingestion_checkpoints

The schema also defines the read view **current_ingestion_checkpoints**.

Phase 1 does not add attack_events, event_evidence, episode_event_links, QA/review tables, source/city registries, materialization tables, runtime ingestion code, Neon configuration, secrets, data inserts, or data migration logic.

## Canonical episode identity

### Internal DB identity

**episode_uid UUID** is the immutable canonical database primary key. It is independent of timestamps.

### Legacy identity

The current project episode ID remains **legacy_episode_id**. Existing JSON/replay IDs and the current algorithm are unchanged.

~~~text
SHA256(f"{city_key}|{start_utc_z}|{end_utc_z}")[:24]
~~~

The timestamps are the final canonical interval boundaries normalized to UTC-Z according to the existing project contract. legacy_episode_id is unique when present.

Future episode revision and alias history is outside Phase 1.

## alert-canonicalization-v1

The Phase-1 canonicalization contract is frozen as **alert-canonicalization-v1**.

### Stage A: source-record identity

Each semantic upstream source record is represented once according to its versioned source_record_key.

Repeated ingestion of the same source record is idempotent: it updates last-seen persistence/provenance state rather than creating another semantic source observation.

### Stage B: UkraineAlarm / manual Alerts.in.ua reconciliation

Bridge observations are tolerance-equivalent when all of these are true:

- same city_key;
- completed AIR alert;
- abs(start delta) <= 15 seconds;
- abs(end delta) <= 15 seconds.

When one tolerance-equivalent observation is UkraineAlarm API and the other is a manual Alerts.in.ua recovery observation:

- retain both observations in alert_episode_sources;
- the UkraineAlarm observation is the effective canonicalization input for that duplicate pair;
- the manual recovery observation gets canonicalization_role = duplicate_alias;
- duplicate_of_observation_id points to the effective UkraineAlarm observation;
- recovery provenance and start/end deltas are retained;
- the manual observation does not independently expand the Stage-C interval union.

UkraineAlarm timestamp precedence exists only for this Stage-B tolerance-equivalent API/manual-recovery pair. It is not a universal source-precedence rule.

### Stage C: final episode assembly

Effective canonicalization inputs come from:

- historical/base alert source;
- Alerts.in.ua static source;
- reconciled UkraineAlarm bridge.

Sort effective intervals by start and merge whenever:

~~~text
next.start <= current.end
~~~

Overlapping or touching intervals therefore form one canonical episode.

~~~text
start_at = earliest contributing start
end_at   = latest contributing end
~~~

The start and end boundaries may come from different observations.

The source model records this with contributes_start_boundary and contributes_end_boundary. Either flag can be true or false independently, and multiple observations may share the same exact boundary. Phase 1 deliberately has no uniqueness constraint limiting a boundary to one contributing observation.

### Stage D: legacy ID

After final Stage-C boundaries are known:

~~~text
legacy_episode_id = SHA256(city_key|start_utc_z|end_utc_z)[:24]
~~~

## Source observation contract

alert_episode_sources represents semantic upstream source records. It can retain a bound observation, a temporarily ambiguous/unbound observation, a rejected observation, and a duplicate/equivalent observation retained for provenance.

**binding_state** is current state:

- bound
- ambiguous
- rejected

Workflow actions such as created_episode and matched_existing are not binding states; when useful they belong in match_method or provenance.

**canonicalization_role** is one of:

- canonical_input: independently participates in Stage-C interval assembly;
- duplicate_alias: retained for provenance, reconciled to another observation, and ignored as an independent Stage-C input;
- excluded: retained but intentionally omitted from canonical episode construction.

episode_uid is nullable. Ambiguous and rejected records are allowed to remain unbound and are not forced into canonical episodes.

Phase 1 uses canonicalization_role, duplicate_of_observation_id, contributes_start_boundary, and contributes_end_boundary. It does not use a single is_canonical_timing_source boolean.

## source_record_key v1

Every Phase-1 source family uses a deterministic SHA-256 source-record key with an explicit algorithm version.

Common normalization:

- canonical JSON encoded as UTF-8;
- object keys sorted;
- compact separators;
- version identifier included in the preimage;
- timestamps converted to UTC with fixed microsecond precision: YYYY-MM-DDTHH:MM:SS.ffffffZ;
- text identity fields normalized with Unicode NFC;
- leading and trailing whitespace trimmed;
- case preserved unless a field is already a project-controlled canonical key;
- filenames and acquisition paths are provenance, not semantic identity.

Store both source_record_key_version and source_record_key. source_record_key is the 64-character lowercase SHA-256 hex digest.

### UkraineAlarm

Version: **ukrainealarm-region-history-v1**

Preimage fields:

~~~text
version
city_key
region_id
alert_type
start_at
end_at
~~~

For Phase 1, alert_type = AIR.

api_region_name is excluded from identity. No source-native alarm ID is currently available, so source_native_id may be NULL.

### Alerts.in.ua

Version: **alerts-in-ua-v1**

The same identity algorithm applies to static bridge observations and manual CSV recovery observations.

Preimage fields:

~~~text
version
city_key
alert_type
start_at
end_at
~~~

Filename, recovery artifact name, and acquisition path are excluded from identity and retained in provenance instead. The same semantic Alerts.in.ua record found through multiple retained exports remains one source observation with combined provenance.

### Lviv historical source

Logical retained source: **Vadimkin official_data_uk.csv**

Version: **vadimkin-official-data-uk-v1**

Preimage fields:

~~~text
version
level
oblast
raion
hromada
source
start_at
end_at
~~~

Text follows the common v1 rules.

This is a deterministic project key, not a source-native immutable row ID. A genuine upstream timestamp correction creates a different v1 source_record_key because the retained source has no stable native row ID. Revision linkage is outside Phase 1.

## Checkpoint semantics

Phase 1 uses **checked_at** and does not contain verified_through_at.

checked_at means:

> the successful source-poll time whose accepted normalized records and canonicalization effects were durably committed before this checkpoint was appended.

checked_at is not the latest alert end, an event-time watermark, or proof that no later correction/backfill can appear for earlier event time.

UkraineAlarm continuity can additionally store:

- continuity_verified
- continuity_method
- continuity_anchor_at
- observed_oldest_start_at
- observed_latest_end_at
- observed_record_count

For the current continuation contract:

~~~text
continuity_method = history_reaches_previous_poll
observed_oldest_start_at <= previous checked_at
~~~

continuity_anchor_at stores the previous checked_at used by that proof.

observed_latest_end_at is diagnostic response metadata. It is not a coverage watermark and must not be renamed as one.

A successful city poll/checkpoint can advance even when no alerts have occurred for a long period.

## Append-only checkpoint bootstrap

Future DB checkpoints are append-only. Phase 1 does not fabricate historical checkpoint chains that were never persisted.

For each imported live stream, migration/bootstrap creates at most one baseline:

~~~text
checkpoint_seq = 1
previous_checkpoint_id = NULL
checkpoint_kind = bootstrap
~~~

For a current UkraineAlarm region, that row may preserve current-state fields such as existing last_checked_at as checked_at, continuous, continuity_reason, poll_overlap_verified, initial_static_match, oldest_history_start, latest_history_end, and region/source metadata.

That baseline means imported current state. It does not claim to be the first poll that historically occurred.

Static historical Lviv snapshots need no invented recurring checkpoints. Their pinned Git/blob provenance belongs to the bootstrap ingestion run.

The DDL enforces sequence uniqueness, sequence-1/later previous-pointer shape, and a composite same-source/city/stream self-FK. It does not invent a role/permission model for UPDATE or DELETE. Append-only mutation behavior remains an application/transaction invariant in Phase 1. DB-level permission or trigger enforcement is a Neon deployment decision.

## Ingestion-run provenance

ingestion_runs separates workflow provenance from the actual checked-out application/data state:

~~~text
workflow_repository
workflow_name
workflow_ref
workflow_sha

input_repository
input_ref
input_sha

github_run_id
github_run_attempt

db_branch
~~~

This represents the current production topology correctly: workflow definition/event on main, actual production checkout on site-prod.

GitHub Actions identifiers and Git-specific provenance fields are nullable where required because a bootstrap import can be performed outside GitHub Actions. db_branch is nullable so the schema remains portable PostgreSQL.

A future output/delivery commit SHA is intentionally outside the Phase-1 ingestion transaction. It may later become materialization/deployment provenance.

## Bootstrap run semantics

Historical retained rows have no original DB ingestion run because no database existed. Phase 1 does not invent one.

The pilot import creates an explicit run:

~~~text
run_kind = bootstrap_import
~~~

That run means the retained pre-DB state was first persisted in the new database by the bootstrap operation. It does not claim to be the original historical fetch.

source_retrieved_at is separate from DB persistence timestamps and is nullable. If historical retrieval time is unknown, it stays NULL. Bootstrap time must not be substituted.

Persistence lifecycle is recorded with:

- first_persisted_at
- first_persisted_by_run_id
- last_seen_at
- last_seen_by_run_id

## Table contracts

### alert_episodes

Required semantics:

- episode_uid UUID is immutable internal identity;
- legacy_episode_id is unique when present and validated as 24 lowercase hex characters;
- city_key and alert_type are text identifiers;
- start_at/end_at are timestamptz;
- closed intervals require end_at > start_at;
- exact canonical intervals are unique by at least (city_key, alert_type, start_at, end_at);
- open intervals, if used, cannot duplicate the same city/type/start tuple;
- episode_state uses text plus CHECK constraints;
- canonicalization_version is alert-canonicalization-v1;
- created_by_run_id and updated_by_run_id preserve ingestion provenance;
- local_start_date is not authoritative Phase-1 state and remains derived/export data.

### alert_episode_sources

The DDL additionally enforces:

- a bound observation has episode_uid;
- ambiguous/rejected observations remain unbound;
- duplicate_alias requires duplicate_of_observation_id;
- an observation cannot duplicate itself;
- source record identity is unique by (source_key, source_record_key_version, source_record_key);
- source_record_key and raw_sha256, when present, validate as lowercase 64-hex SHA-256 values;
- a present source_end_at is later than source_start_at;
- duplicate_alias and excluded records cannot claim episode boundary contribution;
- operational FKs use ON DELETE RESTRICT.

### ingestion_runs

Allowed statuses:

- running
- succeeded
- failed
- cancelled

succeeded means the ingestion transaction committed successfully. It does not mean dashboard export, dashboard QA, Git/static delivery, or Netlify deployment succeeded.

### ingestion_checkpoints

checkpoint_seq is unique within (source_key, city_key, stream_key) and must be >= 1.

Sequence 1 has no previous checkpoint. A later sequence requires previous_checkpoint_id.

The composite previous-checkpoint FK includes checkpoint_id, source_key, city_key, and stream_key, so it cannot point across source/city/stream boundaries. A direct self-cycle is also rejected.

The view current_ingestion_checkpoints returns the highest checkpoint_seq for each source/city/stream.

## Foreign-key deletion policy

Operational provenance uses ON DELETE RESTRICT. Phase 1 adds no broad ON DELETE CASCADE behavior.

## Index contract

Phase-1 indexes cover the known access paths:

- episodes by city/start;
- episodes by unique legacy_episode_id;
- exact canonical interval uniqueness;
- source observations by episode;
- source observations by source/city/time;
- unique semantic source-record identity;
- latest checkpoint lookup and unique sequence per source/city/stream;
- ingestion runs by status/recent start.

No Phase-2 attack-event indexes are added.

## Lviv Phase-1 pilot oracle

Lviv is the real Phase-1 pilot city.

Pinned inputs:

~~~text
frozen_csv_ref  = 58ee75bc20113181b9ddf8029d4cbf3a62d8cd10
frozen_csv_blob = 71d70c0ca54968f530d596cf315616fa858800e1

ukrainealarm_bridge_ref  = e23479ef250396d441cfe68814768be8134c761d
ukrainealarm_bridge_blob = 9b2922b0863ff6f3dba6e84f2348ad0e4b111d41
~~~

Expected canonical oracle:

- 126 episodes;
- 126 unique legacy_episode_id values;
- exact interval parity with lviv-replay_alerts.json.

Known reconstruction summary:

~~~text
historical source episodes = 120
UkraineAlarm bridge intervals = 20
API overlap/refinement = 14
API additions = 6
final canonical episodes = 126
~~~

Known real cross-source continuity match:

~~~text
UkraineAlarm:
2026-09-12T22:00:05.398348Z
2026-09-12T22:14:23.315771Z

Alerts.in.ua:
2026-09-13T01:00:06+03:00
2026-09-13T01:14:27+03:00

start delta = 0.602 s
end delta   = 3.684 s
~~~

These oracle values are frozen.

## Recovery duplicate fixture contract

Lviv alone is insufficient to prove Stage-B UkraineAlarm/manual-recovery precedence.

A later canonicalizer test must freeze one real tolerance-equivalent recovery/API pair from the existing 52 pairs in Kharkiv, Mykolaiv, or Sumy.

The pair is test input only. Fixture extraction must not modify those cities, run replay, repair QA, or change production data.

Expected invariant:

~~~text
2 retained source observations
  -> 1 logical bridge interval
  -> manual row canonicalization_role = duplicate_alias
  -> API row remains effective canonical input
  -> recovery provenance preserved
~~~

Fixture selection/extraction is intentionally deferred to the next implementation task.

## Transaction contract

The ingestion lifecycle is frozen as:

~~~text
read latest checkpoint
  -> fetch source outside DB transaction
  -> parse + normalize response
  -> BEGIN
       acquire per-source/per-city/per-stream transaction lock
       re-read latest checkpoint
       persist/upsert source observations
       reconcile duplicate observations
       construct/update canonical episodes
       bind observations
       append checkpoint
       mark ingestion transaction successful
     COMMIT
  -> materialize/export dashboard JSON
  -> dashboard QA
  -> Git/static delivery
  -> Netlify
~~~

HTTP fetch latency stays outside the long-running DB transaction.

The transaction lock serializes mutation for one source/city/stream. The latest checkpoint is re-read after acquiring the lock so a stale pre-fetch checkpoint cannot be used as the write basis.

If any step after DB COMMIT fails, the committed observations, canonicalization effects, successful ingestion-run state, and appended checkpoint remain durable. Downstream delivery failure does not roll back or falsify a completed ingestion transaction.

## PostgreSQL / Neon boundary

001_phase1_core.sql is ordinary PostgreSQL DDL.

It uses timestamptz, UUID primary keys, text plus CHECK constraints instead of PostgreSQL ENUMs, and JSONB only for variable provenance/state.

It contains no secrets, data inserts, production migration statements, Neon-specific table semantics, source/city registry tables, or Phase-2 tables.

UUID defaults use gen_random_uuid() without adding an extension in this migration. Migration application must target a PostgreSQL version/environment where that function is available, or a later deployment migration must supply UUIDs explicitly. No extension is created by this architecture commit.

Neon is an environment/orchestration choice. Schema semantics remain normal PostgreSQL, and migration application is outside this commit.

## Next implementation gate

There is no remaining Phase-1 schema blocker before implementing the Lviv bootstrap importer/canonicalizer.

The next implementation must:

1. reproduce the 126/126 Lviv oracle exactly from the pinned inputs;
2. implement the three frozen source_record_key algorithms exactly;
3. preserve bootstrap-vs-retrieval provenance semantics;
4. implement the transaction/checkpoint contract with HTTP fetching outside the DB transaction;
5. extract one frozen real recovery/API duplicate fixture before Stage-B precedence is considered test-complete.

No database becomes production-authoritative until the importer/canonicalizer and its oracle/fixture tests pass.
