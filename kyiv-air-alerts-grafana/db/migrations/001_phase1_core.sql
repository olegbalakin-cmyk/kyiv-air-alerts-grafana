-- Phase-1 canonical alert storage schema.
-- Schema only: this migration contains no data migration, ingestion, or Neon-specific DDL.

BEGIN;

CREATE TABLE ingestion_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_kind TEXT NOT NULL CHECK (btrim(run_kind) <> ''),

    source_key TEXT,
    city_key TEXT,

    workflow_repository TEXT,
    workflow_name TEXT,
    workflow_ref TEXT,
    workflow_sha TEXT,

    input_repository TEXT,
    input_ref TEXT,
    input_sha TEXT,

    github_run_id BIGINT,
    github_run_attempt INTEGER,

    db_branch TEXT,

    schema_version TEXT NOT NULL CHECK (btrim(schema_version) <> ''),
    canonicalization_version TEXT,

    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),

    started_at TIMESTAMPTZ NOT NULL,
    ingest_committed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,

    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB,

    CONSTRAINT ingestion_runs_github_attempt_check
        CHECK (github_run_attempt IS NULL OR github_run_attempt >= 1),
    CONSTRAINT ingestion_runs_parameters_object_check
        CHECK (jsonb_typeof(parameters) = 'object'),
    CONSTRAINT ingestion_runs_stats_object_check
        CHECK (jsonb_typeof(stats) = 'object'),
    CONSTRAINT ingestion_runs_error_object_check
        CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    CONSTRAINT ingestion_runs_status_time_check
        CHECK (
            (status = 'running' AND finished_at IS NULL)
            OR
            (status <> 'running' AND finished_at IS NOT NULL)
        ),
    CONSTRAINT ingestion_runs_succeeded_commit_check
        CHECK (status <> 'succeeded' OR ingest_committed_at IS NOT NULL),
    CONSTRAINT ingestion_runs_commit_time_check
        CHECK (ingest_committed_at IS NULL OR ingest_committed_at >= started_at),
    CONSTRAINT ingestion_runs_finished_time_check
        CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT ingestion_runs_commit_before_finish_check
        CHECK (
            ingest_committed_at IS NULL
            OR finished_at IS NULL
            OR ingest_committed_at <= finished_at
        )
);

COMMENT ON TABLE ingestion_runs IS
    'One DB ingestion attempt. status=succeeded means the ingestion transaction committed; it does not imply export, Git delivery, or Netlify deployment succeeded.';
COMMENT ON COLUMN ingestion_runs.run_kind IS
    'Operational run class, including bootstrap_import for the first persistence of retained pre-DB state.';
COMMENT ON COLUMN ingestion_runs.workflow_repository IS
    'Repository containing the workflow definition/event context; distinct from the checked-out input repository/ref/SHA.';
COMMENT ON COLUMN ingestion_runs.workflow_ref IS
    'Workflow definition/event ref, e.g. main in the current production topology.';
COMMENT ON COLUMN ingestion_runs.workflow_sha IS
    'Workflow definition/event commit SHA when known.';
COMMENT ON COLUMN ingestion_runs.input_repository IS
    'Repository actually checked out/read for application or data state.';
COMMENT ON COLUMN ingestion_runs.input_ref IS
    'Ref actually checked out/read, e.g. site-prod in the current production topology.';
COMMENT ON COLUMN ingestion_runs.input_sha IS
    'Commit SHA of the actual checked-out application/data state.';
COMMENT ON COLUMN ingestion_runs.db_branch IS
    'Database branch/environment identifier when one exists (for example a Neon branch); nullable for portable PostgreSQL use.';
COMMENT ON COLUMN ingestion_runs.ingest_committed_at IS
    'Time the DB ingestion transaction durably committed. Downstream materialization and delivery occur after this boundary.';

CREATE TABLE alert_episodes (
    episode_uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_episode_id TEXT,
    city_key TEXT NOT NULL CHECK (btrim(city_key) <> ''),
    alert_type TEXT NOT NULL CHECK (btrim(alert_type) <> ''),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ,
    episode_state TEXT NOT NULL CHECK (episode_state IN ('open', 'closed')),
    canonicalization_version TEXT NOT NULL,

    created_by_run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT,
    updated_by_run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT alert_episodes_legacy_id_format_check
        CHECK (legacy_episode_id IS NULL OR legacy_episode_id ~ '^[0-9a-f]{24}$'),
    CONSTRAINT alert_episodes_state_interval_check
        CHECK (
            (episode_state = 'open' AND end_at IS NULL)
            OR
            (episode_state = 'closed' AND end_at IS NOT NULL AND end_at > start_at)
        ),
    CONSTRAINT alert_episodes_open_legacy_id_check
        CHECK (episode_state <> 'open' OR legacy_episode_id IS NULL),
    CONSTRAINT alert_episodes_canonicalization_version_check
        CHECK (canonicalization_version = 'alert-canonicalization-v1'),
    CONSTRAINT alert_episodes_updated_time_check
        CHECK (updated_at >= created_at),
    CONSTRAINT alert_episodes_legacy_episode_id_key UNIQUE (legacy_episode_id),
    CONSTRAINT alert_episodes_exact_interval_key UNIQUE (city_key, alert_type, start_at, end_at)
);

-- PostgreSQL UNIQUE treats NULL values as distinct, so protect open-episode identity separately.
CREATE UNIQUE INDEX alert_episodes_open_interval_uidx
    ON alert_episodes (city_key, alert_type, start_at)
    WHERE end_at IS NULL;

CREATE INDEX alert_episodes_city_start_idx
    ON alert_episodes (city_key, start_at);

COMMENT ON TABLE alert_episodes IS
    'Canonical alert episodes. episode_uid is immutable DB identity; legacy_episode_id preserves the current project hash contract for final canonical intervals.';
COMMENT ON COLUMN alert_episodes.legacy_episode_id IS
    'Current project ID: SHA256(city_key|start_utc_z|end_utc_z)[:24], computed after final Stage-C boundaries are known. Future revision/alias history is outside Phase 1.';
COMMENT ON COLUMN alert_episodes.canonicalization_version IS
    'Phase-1 interval construction contract; 001_phase1_core freezes alert-canonicalization-v1.';
COMMENT ON COLUMN alert_episodes.start_at IS
    'Earliest contributing boundary after Stage-B reconciliation and Stage-C overlap/touch union.';
COMMENT ON COLUMN alert_episodes.end_at IS
    'Latest contributing boundary for a closed canonical episode. Local date is derived/export state and is not stored authoritatively here.';

CREATE TABLE alert_episode_sources (
    source_observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    episode_uid UUID REFERENCES alert_episodes(episode_uid) ON DELETE RESTRICT,

    source_key TEXT NOT NULL CHECK (btrim(source_key) <> ''),
    source_record_key_version TEXT NOT NULL CHECK (btrim(source_record_key_version) <> ''),
    source_record_key TEXT NOT NULL,
    source_native_id TEXT,

    city_key TEXT NOT NULL CHECK (btrim(city_key) <> ''),
    alert_type TEXT NOT NULL CHECK (btrim(alert_type) <> ''),

    source_start_at TIMESTAMPTZ NOT NULL,
    source_end_at TIMESTAMPTZ,

    source_retrieved_at TIMESTAMPTZ,

    binding_state TEXT NOT NULL CHECK (binding_state IN ('bound', 'ambiguous', 'rejected')),
    canonicalization_role TEXT NOT NULL CHECK (canonicalization_role IN ('canonical_input', 'duplicate_alias', 'excluded')),
    duplicate_of_observation_id UUID REFERENCES alert_episode_sources(source_observation_id) ON DELETE RESTRICT,

    match_method TEXT,
    start_delta_ms INTEGER,
    end_delta_ms INTEGER,

    contributes_start_boundary BOOLEAN NOT NULL DEFAULT FALSE,
    contributes_end_boundary BOOLEAN NOT NULL DEFAULT FALSE,

    raw_sha256 TEXT,
    raw_object_path TEXT,

    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,

    first_persisted_by_run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT,
    last_seen_by_run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT,
    first_persisted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT alert_episode_sources_record_key_format_check
        CHECK (source_record_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_episode_sources_raw_sha256_format_check
        CHECK (raw_sha256 IS NULL OR raw_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_episode_sources_interval_check
        CHECK (source_end_at IS NULL OR source_end_at > source_start_at),
    CONSTRAINT alert_episode_sources_binding_check
        CHECK (
            (binding_state = 'bound' AND episode_uid IS NOT NULL)
            OR
            (binding_state IN ('ambiguous', 'rejected') AND episode_uid IS NULL)
        ),
    CONSTRAINT alert_episode_sources_duplicate_role_check
        CHECK (
            (canonicalization_role = 'duplicate_alias' AND duplicate_of_observation_id IS NOT NULL)
            OR
            (canonicalization_role <> 'duplicate_alias' AND duplicate_of_observation_id IS NULL)
        ),
    CONSTRAINT alert_episode_sources_no_self_duplicate_check
        CHECK (duplicate_of_observation_id IS NULL OR duplicate_of_observation_id <> source_observation_id),
    CONSTRAINT alert_episode_sources_noninput_boundary_check
        CHECK (
            canonicalization_role = 'canonical_input'
            OR (NOT contributes_start_boundary AND NOT contributes_end_boundary)
        ),
    CONSTRAINT alert_episode_sources_boundary_binding_check
        CHECK (
            (NOT contributes_start_boundary AND NOT contributes_end_boundary)
            OR (binding_state = 'bound' AND canonicalization_role = 'canonical_input')
        ),
    CONSTRAINT alert_episode_sources_provenance_object_check
        CHECK (jsonb_typeof(provenance) = 'object'),
    CONSTRAINT alert_episode_sources_seen_time_check
        CHECK (last_seen_at >= first_persisted_at),
    CONSTRAINT alert_episode_sources_record_identity_key
        UNIQUE (source_key, source_record_key_version, source_record_key)
);

CREATE INDEX alert_episode_sources_episode_idx
    ON alert_episode_sources (episode_uid)
    WHERE episode_uid IS NOT NULL;

CREATE INDEX alert_episode_sources_source_time_idx
    ON alert_episode_sources (source_key, city_key, source_start_at);

COMMENT ON TABLE alert_episode_sources IS
    'Semantic upstream source records. Repeated ingestion of the same versioned source_record_key updates last-seen provenance instead of creating a second semantic observation.';
COMMENT ON COLUMN alert_episode_sources.episode_uid IS
    'Nullable so ambiguous, rejected, or not-yet-bound source records can be retained without inventing a canonical episode.';
COMMENT ON COLUMN alert_episode_sources.source_record_key IS
    'Lowercase SHA-256 hex digest over the versioned deterministic canonical-JSON preimage defined by the Phase-1 contract.';
COMMENT ON COLUMN alert_episode_sources.source_retrieved_at IS
    'Historical source retrieval time when actually known. Bootstrap persistence time must not be substituted when retrieval time is unknown.';
COMMENT ON COLUMN alert_episode_sources.binding_state IS
    'Current binding state: bound, ambiguous, or rejected. Historical workflow actions such as created_episode or matched_existing belong in match_method/provenance.';
COMMENT ON COLUMN alert_episode_sources.canonicalization_role IS
    'canonical_input participates independently in interval assembly; duplicate_alias is retained provenance reconciled to another observation; excluded is persisted but omitted from construction.';
COMMENT ON COLUMN alert_episode_sources.duplicate_of_observation_id IS
    'For duplicate_alias, points to the effective observation. Stage-B API/manual reconciliation must point the manual recovery observation at the effective UkraineAlarm observation.';
COMMENT ON COLUMN alert_episode_sources.start_delta_ms IS
    'Signed reconciliation diagnostic in milliseconds when a match method defines such a delta.';
COMMENT ON COLUMN alert_episode_sources.end_delta_ms IS
    'Signed reconciliation diagnostic in milliseconds when a match method defines such a delta.';
COMMENT ON COLUMN alert_episode_sources.contributes_start_boundary IS
    'True when this canonical input contributes the final episode start. Multiple observations may share the exact same boundary.';
COMMENT ON COLUMN alert_episode_sources.contributes_end_boundary IS
    'True when this canonical input contributes the final episode end. Multiple observations may share the exact same boundary.';

CREATE TABLE ingestion_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_key TEXT NOT NULL CHECK (btrim(source_key) <> ''),
    city_key TEXT NOT NULL CHECK (btrim(city_key) <> ''),
    stream_key TEXT NOT NULL CHECK (btrim(stream_key) <> ''),

    checkpoint_seq BIGINT NOT NULL,
    checkpoint_kind TEXT NOT NULL CHECK (checkpoint_kind IN ('bootstrap', 'poll')),

    previous_checkpoint_id UUID,

    checked_at TIMESTAMPTZ NOT NULL,

    continuity_verified BOOLEAN NOT NULL DEFAULT FALSE,
    continuity_method TEXT,
    continuity_anchor_at TIMESTAMPTZ,

    observed_oldest_start_at TIMESTAMPTZ,
    observed_latest_end_at TIMESTAMPTZ,
    observed_record_count BIGINT,

    cursor JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by_run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ingestion_checkpoints_seq_check
        CHECK (checkpoint_seq >= 1),
    CONSTRAINT ingestion_checkpoints_previous_presence_check
        CHECK (
            (checkpoint_seq = 1 AND previous_checkpoint_id IS NULL)
            OR
            (checkpoint_seq > 1 AND previous_checkpoint_id IS NOT NULL)
        ),
    CONSTRAINT ingestion_checkpoints_no_self_previous_check
        CHECK (previous_checkpoint_id IS NULL OR previous_checkpoint_id <> checkpoint_id),
    CONSTRAINT ingestion_checkpoints_observed_count_check
        CHECK (observed_record_count IS NULL OR observed_record_count >= 0),
    CONSTRAINT ingestion_checkpoints_continuity_method_check
        CHECK (NOT continuity_verified OR continuity_method IS NOT NULL),
    CONSTRAINT ingestion_checkpoints_observed_interval_check
        CHECK (
            observed_oldest_start_at IS NULL
            OR observed_latest_end_at IS NULL
            OR observed_latest_end_at >= observed_oldest_start_at
        ),
    CONSTRAINT ingestion_checkpoints_cursor_object_check
        CHECK (cursor IS NULL OR jsonb_typeof(cursor) = 'object'),
    CONSTRAINT ingestion_checkpoints_metadata_object_check
        CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ingestion_checkpoints_identity_stream_key
        UNIQUE (checkpoint_id, source_key, city_key, stream_key),
    CONSTRAINT ingestion_checkpoints_previous_same_stream_fk
        FOREIGN KEY (previous_checkpoint_id, source_key, city_key, stream_key)
        REFERENCES ingestion_checkpoints (checkpoint_id, source_key, city_key, stream_key)
        ON DELETE RESTRICT
);

-- One sequence number per stream; DESC also supports the known latest-checkpoint lookup.
CREATE UNIQUE INDEX ingestion_checkpoints_stream_seq_uidx
    ON ingestion_checkpoints (source_key, city_key, stream_key, checkpoint_seq DESC);

CREATE INDEX ingestion_runs_status_started_idx
    ON ingestion_runs (status, started_at DESC);

COMMENT ON TABLE ingestion_checkpoints IS
    'Append-only source-poll checkpoints. Phase 1 relies on the ingestion transaction/application to append rather than update/delete; DB-role enforcement is deferred to deployment.';
COMMENT ON COLUMN ingestion_checkpoints.checked_at IS
    'Successful source-poll time whose accepted normalized records and canonicalization effects were durably committed before this checkpoint was appended. It is not an event-time watermark.';
COMMENT ON COLUMN ingestion_checkpoints.continuity_anchor_at IS
    'Reference time used by the named continuity proof. For history_reaches_previous_poll this is the previous successful checked_at.';
COMMENT ON COLUMN ingestion_checkpoints.observed_oldest_start_at IS
    'Oldest source start observed in the accepted poll response. For the current UkraineAlarm continuation contract, observed_oldest_start_at <= previous checked_at proves history_reaches_previous_poll.';
COMMENT ON COLUMN ingestion_checkpoints.observed_latest_end_at IS
    'Latest end observed in this poll response. This is diagnostic observation metadata, not a coverage watermark.';
COMMENT ON COLUMN ingestion_checkpoints.previous_checkpoint_id IS
    'Previous checkpoint in the same source/city/stream chain; composite FK prevents cross-stream links.';

CREATE VIEW current_ingestion_checkpoints AS
SELECT DISTINCT ON (source_key, city_key, stream_key)
    checkpoint_id,
    source_key,
    city_key,
    stream_key,
    checkpoint_seq,
    checkpoint_kind,
    previous_checkpoint_id,
    checked_at,
    continuity_verified,
    continuity_method,
    continuity_anchor_at,
    observed_oldest_start_at,
    observed_latest_end_at,
    observed_record_count,
    cursor,
    metadata,
    created_by_run_id,
    created_at
FROM ingestion_checkpoints
ORDER BY source_key, city_key, stream_key, checkpoint_seq DESC;

COMMENT ON VIEW current_ingestion_checkpoints IS
    'Highest appended checkpoint_seq per source_key/city_key/stream_key.';

COMMIT;
