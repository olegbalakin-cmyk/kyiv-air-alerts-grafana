-- PROOF ONLY. DO NOT APPLY AS A MIGRATION.
-- Candidate extension to the existing Phase-1 alert_episodes / alert_episode_sources model.
-- The parent AIR episode remains authoritative and unchanged.

CREATE TABLE alert_state_snapshots (
    snapshot_uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_key_version TEXT NOT NULL,
    snapshot_key TEXT NOT NULL UNIQUE,

    episode_uid UUID REFERENCES alert_episodes(episode_uid) ON DELETE RESTRICT,
    episode_source_observation_id UUID REFERENCES alert_episode_sources(source_observation_id) ON DELETE RESTRICT,
    binding_state TEXT NOT NULL CHECK (binding_state IN ('BOUND', 'AMBIGUOUS', 'UNBOUND')),

    source_key TEXT NOT NULL,
    source_alert_id TEXT,
    alert_type TEXT NOT NULL DEFAULT 'AIR',

    target_city_key TEXT NOT NULL,
    source_geo_scope TEXT NOT NULL CHECK (source_geo_scope IN ('CITY', 'HROMADA', 'RAION', 'OBLAST', 'OTHER')),
    source_geo_type_raw TEXT,
    source_geo_id_raw TEXT,

    observed_at TIMESTAMPTZ NOT NULL,
    source_state_at TIMESTAMPTZ,
    source_alert_started_at TIMESTAMPTZ,
    source_alert_ended_at TIMESTAMPTZ,
    source_active BOOLEAN,
    source_alert_level_raw TEXT,
    source_state_raw TEXT,

    raw_sha256 TEXT NOT NULL,
    raw_object_path TEXT,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT alert_state_snapshots_key_format_check
        CHECK (snapshot_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_state_snapshots_raw_sha256_format_check
        CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_state_snapshots_binding_check
        CHECK (
            (binding_state = 'BOUND' AND episode_uid IS NOT NULL)
            OR
            (binding_state IN ('AMBIGUOUS', 'UNBOUND') AND episode_uid IS NULL)
        )
);

CREATE INDEX alert_state_snapshots_episode_idx
    ON alert_state_snapshots (episode_uid, observed_at)
    WHERE episode_uid IS NOT NULL;

CREATE INDEX alert_state_snapshots_source_scope_idx
    ON alert_state_snapshots (source_key, source_geo_scope, source_geo_id_raw, observed_at);

CREATE TABLE alert_threat_observations (
    threat_observation_uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_uid UUID NOT NULL REFERENCES alert_state_snapshots(snapshot_uid) ON DELETE RESTRICT,
    threat_observation_key_version TEXT NOT NULL,
    threat_observation_key TEXT NOT NULL UNIQUE,

    source_threat_id TEXT,
    component_signature_version TEXT,
    component_signature TEXT,
    component_identity_basis TEXT NOT NULL CHECK (
        component_identity_basis IN ('NATIVE', 'DETERMINISTIC_INFERRED', 'SNAPSHOT_ONLY')
    ),

    level_raw TEXT,
    cause_raw TEXT,
    reason_raw TEXT,
    source_message_raw TEXT,
    source_started_at TIMESTAMPTZ,
    source_ended_at TIMESTAMPTZ,

    CONSTRAINT alert_threat_observations_key_format_check
        CHECK (threat_observation_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_threat_observations_component_signature_check
        CHECK (component_signature IS NULL OR component_signature ~ '^[0-9a-f]{64}$'),
    CONSTRAINT alert_threat_observations_end_after_start_check
        CHECK (source_ended_at IS NULL OR source_started_at IS NULL OR source_ended_at >= source_started_at)
);

CREATE INDEX alert_threat_observations_snapshot_idx
    ON alert_threat_observations (snapshot_uid);

CREATE INDEX alert_threat_observations_component_idx
    ON alert_threat_observations (component_signature)
    WHERE component_signature IS NOT NULL;

-- Deliberately not persisted here:
--   * effective_severity
--   * derived threat-component intervals
--   * inferred end timestamps
--
-- A derived interval may expose:
--   source_started_at            -- exact only when source supplied it
--   first_seen_active_at
--   last_seen_active_at
--   first_seen_inactive_at
--   end_lower_bound
--   end_upper_bound
--   source_ended_at              -- exact only when source supplied it
--   end_basis                    -- SOURCE_EXPLICIT | SNAPSHOT_INFERRED |
--                                   EPISODE_CLOSE_INFERRED | UNKNOWN
--
-- In particular, first_seen_inactive_at MUST NOT be copied into source_ended_at.
