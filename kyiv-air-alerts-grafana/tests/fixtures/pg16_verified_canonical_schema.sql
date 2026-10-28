-- Disposable PostgreSQL 16 only. Seven canonical tables faithfully reconstructed from

-- READ-ONLY Neon schema/constraint/index metadata on br-bold-mode-b5rub8pq, 2026-10-11.

-- No row data, credentials, branch creation, or Neon DDL was read/executed.

-- NOT NULL from catalog column nullable flags; all CHECK/PK/UNIQUE/FK constraints retained.

BEGIN;

CREATE TABLE public.ingestion_runs (
  run_id uuid NOT NULL DEFAULT gen_random_uuid(),
  run_kind text NOT NULL,
  source_key text,
  city_key text,
  workflow_repository text,
  workflow_name text,
  workflow_ref text,
  workflow_sha text,
  input_repository text,
  input_ref text,
  input_sha text,
  github_run_id bigint,
  github_run_attempt integer,
  db_branch text,
  schema_version text NOT NULL,
  canonicalization_version text,
  status text NOT NULL,
  started_at timestamp with time zone NOT NULL,
  ingest_committed_at timestamp with time zone,
  finished_at timestamp with time zone,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  stats jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb
);

CREATE TABLE public.ingestion_checkpoints (
  checkpoint_id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_key text NOT NULL,
  city_key text NOT NULL,
  stream_key text NOT NULL,
  checkpoint_seq bigint NOT NULL,
  checkpoint_kind text NOT NULL,
  previous_checkpoint_id uuid,
  checked_at timestamp with time zone NOT NULL,
  continuity_verified boolean NOT NULL DEFAULT false,
  continuity_method text,
  continuity_anchor_at timestamp with time zone,
  observed_oldest_start_at timestamp with time zone,
  observed_latest_end_at timestamp with time zone,
  observed_record_count bigint,
  cursor jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by_run_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE public.alert_episodes (
  episode_uid uuid NOT NULL DEFAULT gen_random_uuid(),
  legacy_episode_id text,
  city_key text NOT NULL,
  alert_type text NOT NULL,
  start_at timestamp with time zone NOT NULL,
  end_at timestamp with time zone,
  episode_state text NOT NULL,
  canonicalization_version text NOT NULL,
  created_by_run_id uuid NOT NULL,
  updated_by_run_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE public.alert_episode_sources (
  source_observation_id uuid NOT NULL DEFAULT gen_random_uuid(),
  episode_uid uuid,
  source_key text NOT NULL,
  source_record_key_version text NOT NULL,
  source_record_key text NOT NULL,
  source_native_id text,
  city_key text NOT NULL,
  alert_type text NOT NULL,
  source_start_at timestamp with time zone NOT NULL,
  source_end_at timestamp with time zone,
  source_retrieved_at timestamp with time zone,
  binding_state text NOT NULL,
  canonicalization_role text NOT NULL,
  duplicate_of_observation_id uuid,
  match_method text,
  start_delta_ms integer,
  end_delta_ms integer,
  contributes_start_boundary boolean NOT NULL DEFAULT false,
  contributes_end_boundary boolean NOT NULL DEFAULT false,
  raw_sha256 text,
  raw_object_path text,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  first_persisted_by_run_id uuid NOT NULL,
  last_seen_by_run_id uuid NOT NULL,
  first_persisted_at timestamp with time zone NOT NULL DEFAULT now(),
  last_seen_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE public.attack_event_classifications (
  classification_uid uuid NOT NULL DEFAULT gen_random_uuid(),
  classification_key_version text NOT NULL,
  classification_key text NOT NULL,
  historical_episode_id text NOT NULL,
  city_key text NOT NULL,
  alert_type text NOT NULL DEFAULT 'AIR'::text,
  alert_start_at timestamp with time zone NOT NULL,
  alert_end_at timestamp with time zone NOT NULL,
  verdict text NOT NULL,
  is_event boolean NOT NULL,
  positive_tier text,
  event_types text[] NOT NULL DEFAULT '{}'::text[],
  qa_reasons_state text NOT NULL,
  qa_reasons jsonb,
  classifier_reason_codes text[] NOT NULL DEFAULT '{}'::text[],
  classifier_blob_sha text NOT NULL,
  classifier_methodology_version text NOT NULL,
  normalization_version text NOT NULL,
  evidence_set_sha256 text NOT NULL,
  review_provenance_sha256 text,
  human_review_state text NOT NULL DEFAULT 'NONE'::text,
  review_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  originating_frozen_case_id text,
  binding_state text NOT NULL,
  alert_episode_uid uuid,
  origin_repository text NOT NULL,
  origin_ref text,
  origin_commit_sha text,
  origin_artifact_path text,
  origin_artifact_blob_sha text,
  origin_target_state_sha256 text,
  origin_workflow_run_id bigint,
  classified_at timestamp with time zone,
  supersedes_classification_uid uuid,
  revision_reason text,
  correction_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  persisted_by_run_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  origin_provenance jsonb NOT NULL,
  origin_provenance_sha256 text NOT NULL,
  originating_frozen_case_id_state text NOT NULL
);

CREATE TABLE public.attack_event_sources (
  attack_event_source_uid uuid NOT NULL DEFAULT gen_random_uuid(),
  source_link_key_version text NOT NULL,
  source_link_key text NOT NULL,
  classification_uid uuid NOT NULL,
  observation_id text NOT NULL,
  source_family text,
  source_type text,
  source_url text,
  telegram_channel text,
  telegram_message_id bigint,
  source_timestamp timestamp with time zone,
  event_timestamp_if_stated timestamp with time zone,
  excerpt text,
  content_sha256 text NOT NULL,
  content_hash_basis text NOT NULL,
  observation_classification_outcome text,
  classification_episode_id text,
  evidence_payload jsonb NOT NULL,
  retrieval_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  origin_artifact_path text,
  origin_git_ref text,
  origin_git_blob_sha text,
  raw_object_path text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  origin_provenance jsonb NOT NULL,
  origin_provenance_sha256 text NOT NULL,
  source_type_state text NOT NULL,
  source_timestamp_state text NOT NULL,
  source_timestamp_raw text
);

CREATE TABLE public.attack_events (
  attack_event_uid uuid NOT NULL DEFAULT gen_random_uuid(),
  attack_event_key_version text NOT NULL,
  attack_event_key text NOT NULL,
  event_grain text NOT NULL,
  historical_episode_id text NOT NULL,
  city_key text NOT NULL,
  alert_type text NOT NULL DEFAULT 'AIR'::text,
  alert_start_at timestamp with time zone NOT NULL,
  alert_end_at timestamp with time zone NOT NULL,
  event_status text NOT NULL,
  current_classification_uid uuid NOT NULL,
  binding_state text NOT NULL,
  alert_episode_uid uuid,
  correction_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by_run_id uuid,
  updated_by_run_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_pkey PRIMARY KEY (run_id);

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_pkey PRIMARY KEY (checkpoint_id);

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_pkey PRIMARY KEY (episode_uid);

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_pkey PRIMARY KEY (source_observation_id);

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_pkey PRIMARY KEY (classification_uid);

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_pkey PRIMARY KEY (attack_event_source_uid);

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_pkey PRIMARY KEY (attack_event_uid);

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_identity_stream_key UNIQUE (checkpoint_id, source_key, city_key, stream_key);

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_exact_interval_key UNIQUE (city_key, alert_type, start_at, end_at);

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_legacy_episode_id_key UNIQUE (legacy_episode_id);

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_record_identity_key UNIQUE (source_key, source_record_key_version, source_record_key);

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_classification_key_key UNIQUE (classification_key);

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_classification_observation_unique UNIQUE (classification_uid, observation_id, content_sha256);

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_source_link_key_key UNIQUE (source_link_key);

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_attack_event_key_key UNIQUE (attack_event_key);

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_historical_episode_unique UNIQUE (city_key, historical_episode_id);

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_commit_before_finish_check CHECK (((ingest_committed_at IS NULL) OR (finished_at IS NULL) OR (ingest_committed_at <= finished_at)));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_commit_time_check CHECK (((ingest_committed_at IS NULL) OR (ingest_committed_at >= started_at)));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_error_object_check CHECK (((error IS NULL) OR (jsonb_typeof(error) = 'object'::text)));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_finished_time_check CHECK (((finished_at IS NULL) OR (finished_at >= started_at)));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_github_attempt_check CHECK (((github_run_attempt IS NULL) OR (github_run_attempt >= 1)));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_parameters_object_check CHECK ((jsonb_typeof(parameters) = 'object'::text));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_run_kind_check CHECK ((btrim(run_kind) <> ''::text));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_schema_version_check CHECK ((btrim(schema_version) <> ''::text));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_stats_object_check CHECK ((jsonb_typeof(stats) = 'object'::text));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_status_check CHECK ((status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'cancelled'::text])));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_status_time_check CHECK ((((status = 'running'::text) AND (finished_at IS NULL)) OR ((status <> 'running'::text) AND (finished_at IS NOT NULL))));

ALTER TABLE public.ingestion_runs ADD CONSTRAINT ingestion_runs_succeeded_commit_check CHECK (((status <> 'succeeded'::text) OR (ingest_committed_at IS NOT NULL)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_checkpoint_kind_check CHECK ((checkpoint_kind = ANY (ARRAY['bootstrap'::text, 'poll'::text])));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_city_key_check CHECK ((btrim(city_key) <> ''::text));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_continuity_method_check CHECK (((NOT continuity_verified) OR (continuity_method IS NOT NULL)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_cursor_object_check CHECK (((cursor IS NULL) OR (jsonb_typeof(cursor) = 'object'::text)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_metadata_object_check CHECK ((jsonb_typeof(metadata) = 'object'::text));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_no_self_previous_check CHECK (((previous_checkpoint_id IS NULL) OR (previous_checkpoint_id <> checkpoint_id)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_observed_count_check CHECK (((observed_record_count IS NULL) OR (observed_record_count >= 0)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_observed_interval_check CHECK (((observed_oldest_start_at IS NULL) OR (observed_latest_end_at IS NULL) OR (observed_latest_end_at >= observed_oldest_start_at)));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_previous_presence_check CHECK ((((checkpoint_seq = 1) AND (previous_checkpoint_id IS NULL)) OR ((checkpoint_seq > 1) AND (previous_checkpoint_id IS NOT NULL))));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_seq_check CHECK ((checkpoint_seq >= 1));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_source_key_check CHECK ((btrim(source_key) <> ''::text));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_stream_key_check CHECK ((btrim(stream_key) <> ''::text));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_alert_type_check CHECK ((btrim(alert_type) <> ''::text));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_canonicalization_version_check CHECK ((canonicalization_version = 'alert-canonicalization-v1'::text));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_city_key_check CHECK ((btrim(city_key) <> ''::text));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_episode_state_check CHECK ((episode_state = ANY (ARRAY['open'::text, 'closed'::text])));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_legacy_id_format_check CHECK (((legacy_episode_id IS NULL) OR (legacy_episode_id ~ '^[0-9a-f]{24}$'::text)));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_open_legacy_id_check CHECK (((episode_state <> 'open'::text) OR (legacy_episode_id IS NULL)));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_state_interval_check CHECK ((((episode_state = 'open'::text) AND (end_at IS NULL)) OR ((episode_state = 'closed'::text) AND (end_at IS NOT NULL) AND (end_at > start_at))));

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_updated_time_check CHECK ((updated_at >= created_at));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_alert_type_check CHECK ((btrim(alert_type) <> ''::text));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_binding_check CHECK ((((binding_state = 'bound'::text) AND (episode_uid IS NOT NULL)) OR ((binding_state = ANY (ARRAY['ambiguous'::text, 'rejected'::text])) AND (episode_uid IS NULL))));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_binding_state_check CHECK ((binding_state = ANY (ARRAY['bound'::text, 'ambiguous'::text, 'rejected'::text])));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_boundary_binding_check CHECK ((((NOT contributes_start_boundary) AND (NOT contributes_end_boundary)) OR ((binding_state = 'bound'::text) AND (canonicalization_role = 'canonical_input'::text))));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_canonicalization_role_check CHECK ((canonicalization_role = ANY (ARRAY['canonical_input'::text, 'duplicate_alias'::text, 'excluded'::text])));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_city_key_check CHECK ((btrim(city_key) <> ''::text));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_duplicate_role_check CHECK ((((canonicalization_role = 'duplicate_alias'::text) AND (duplicate_of_observation_id IS NOT NULL)) OR ((canonicalization_role <> 'duplicate_alias'::text) AND (duplicate_of_observation_id IS NULL))));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_interval_check CHECK (((source_end_at IS NULL) OR (source_end_at > source_start_at)));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_no_self_duplicate_check CHECK (((duplicate_of_observation_id IS NULL) OR (duplicate_of_observation_id <> source_observation_id)));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_noninput_boundary_check CHECK (((canonicalization_role = 'canonical_input'::text) OR ((NOT contributes_start_boundary) AND (NOT contributes_end_boundary))));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_provenance_object_check CHECK ((jsonb_typeof(provenance) = 'object'::text));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_raw_sha256_format_check CHECK (((raw_sha256 IS NULL) OR (raw_sha256 ~ '^[0-9a-f]{64}$'::text)));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_record_key_format_check CHECK ((source_record_key ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_seen_time_check CHECK ((last_seen_at >= first_persisted_at));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_source_key_check CHECK ((btrim(source_key) <> ''::text));

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_source_record_key_version_check CHECK ((btrim(source_record_key_version) <> ''::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_alert_type_check CHECK ((alert_type = 'AIR'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_binding_check CHECK ((((binding_state = 'BOUND'::text) AND (alert_episode_uid IS NOT NULL)) OR ((binding_state = ANY (ARRAY['AMBIGUOUS'::text, 'UNBOUND'::text])) AND (alert_episode_uid IS NULL))));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_binding_state_check CHECK ((binding_state = ANY (ARRAY['BOUND'::text, 'AMBIGUOUS'::text, 'UNBOUND'::text])));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_city_check CHECK ((btrim(city_key) <> ''::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_classifier_sha_check CHECK ((classifier_blob_sha ~ '^[0-9a-f]{40}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_episode_id_check CHECK ((historical_episode_id ~ '^[0-9a-f]{24}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_evidence_sha_check CHECK ((evidence_set_sha256 ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_frozen_case_id_state_check CHECK ((originating_frozen_case_id_state = ANY (ARRAY['MATERIALIZED'::text, 'UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text, 'NOT_APPLICABLE'::text])));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_frozen_case_id_value_check CHECK ((((originating_frozen_case_id_state = 'MATERIALIZED'::text) AND (originating_frozen_case_id IS NOT NULL) AND (btrim(originating_frozen_case_id) <> ''::text)) OR ((originating_frozen_case_id_state = ANY (ARRAY['UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text, 'NOT_APPLICABLE'::text])) AND (originating_frozen_case_id IS NULL))));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_interval_check CHECK ((alert_end_at > alert_start_at));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_key_format_check CHECK ((classification_key ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_key_version_check CHECK ((classification_key_version = 'attack-event-classification-key-v2'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_origin_commit_check CHECK ((origin_commit_sha ~ '^[0-9a-f]{40}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_origin_provenance_sha256_check CHECK ((origin_provenance_sha256 ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_origin_state_sha_check CHECK (((origin_target_state_sha256 IS NULL) OR (origin_target_state_sha256 ~ '^[0-9a-f]{64}$'::text)));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_positive_check CHECK ((((verdict = 'STRICT_EVENT_POSITIVE'::text) AND is_event AND (positive_tier = 'STRICT'::text)) OR ((verdict = 'SENSITIVITY_EVENT_POSITIVE'::text) AND is_event AND (positive_tier = 'SENSITIVITY'::text)) OR ((verdict = ANY (ARRAY['NO_CONFIRMED_EVENT'::text, 'NEEDS_REVIEW'::text])) AND (NOT is_event) AND (positive_tier IS NULL))));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_qa_state_check CHECK ((qa_reasons_state = ANY (ARRAY['MATERIALIZED'::text, 'UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text])));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_qa_value_check CHECK ((((qa_reasons_state = 'MATERIALIZED'::text) AND (jsonb_typeof(qa_reasons) = 'array'::text)) OR ((qa_reasons_state = 'UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text) AND (qa_reasons IS NULL))));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_review_sha_check CHECK (((review_provenance_sha256 IS NULL) OR (review_provenance_sha256 ~ '^[0-9a-f]{64}$'::text)));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_review_state_check CHECK ((human_review_state = ANY (ARRAY['NONE'::text, 'NEEDS_REVIEW'::text, 'REVIEWED_EVIDENCE'::text])));

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_verdict_check CHECK ((verdict = ANY (ARRAY['STRICT_EVENT_POSITIVE'::text, 'SENSITIVITY_EVENT_POSITIVE'::text, 'NO_CONFIRMED_EVENT'::text, 'NEEDS_REVIEW'::text])));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_content_sha_check CHECK ((content_sha256 ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_hash_basis_check CHECK ((content_hash_basis = ANY (ARRAY['SOURCE_NATIVE'::text, 'NORMALIZED_EVIDENCE'::text])));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_key_format_check CHECK ((source_link_key ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_key_version_check CHECK ((source_link_key_version = 'attack-event-source-link-key-v1'::text));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_observation_outcome_check CHECK (((observation_classification_outcome IS NULL) OR (observation_classification_outcome = ANY (ARRAY['approved_strict'::text, 'approved_sensitivity'::text, 'needs_review'::text, 'rejected'::text]))));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_origin_provenance_sha256_check CHECK ((origin_provenance_sha256 ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_source_timestamp_state_check CHECK ((source_timestamp_state = ANY (ARRAY['MATERIALIZED'::text, 'ABSENT_IN_ACCEPTED_SOURCE'::text, 'UNPARSEABLE_IN_ACCEPTED_SOURCE'::text])));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_source_timestamp_value_check CHECK ((((source_timestamp_state = 'MATERIALIZED'::text) AND (source_timestamp IS NOT NULL)) OR ((source_timestamp_state = 'ABSENT_IN_ACCEPTED_SOURCE'::text) AND (source_timestamp IS NULL) AND (source_timestamp_raw IS NULL)) OR ((source_timestamp_state = 'UNPARSEABLE_IN_ACCEPTED_SOURCE'::text) AND (source_timestamp IS NULL) AND (source_timestamp_raw IS NOT NULL) AND (btrim(source_timestamp_raw) <> ''::text))));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_source_type_state_check CHECK ((source_type_state = ANY (ARRAY['MATERIALIZED'::text, 'UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text])));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_source_type_value_check CHECK ((((source_type_state = 'MATERIALIZED'::text) AND (source_type IS NOT NULL) AND (btrim(source_type) <> ''::text)) OR ((source_type_state = 'UNMATERIALIZED_IN_ACCEPTED_SOURCE'::text) AND (source_type IS NULL))));

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_telegram_pair_check CHECK ((((telegram_channel IS NULL) AND (telegram_message_id IS NULL)) OR ((telegram_channel IS NOT NULL) AND (telegram_message_id IS NOT NULL))));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_alert_type_check CHECK ((alert_type = 'AIR'::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_binding_check CHECK ((((binding_state = 'BOUND'::text) AND (alert_episode_uid IS NOT NULL)) OR ((binding_state = ANY (ARRAY['AMBIGUOUS'::text, 'UNBOUND'::text])) AND (alert_episode_uid IS NULL))));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_binding_state_check CHECK ((binding_state = ANY (ARRAY['BOUND'::text, 'AMBIGUOUS'::text, 'UNBOUND'::text])));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_city_check CHECK ((btrim(city_key) <> ''::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_episode_id_check CHECK ((historical_episode_id ~ '^[0-9a-f]{24}$'::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_grain_check CHECK ((event_grain = 'HISTORICAL_ALERT_EPISODE'::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_interval_check CHECK ((alert_end_at > alert_start_at));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_key_format_check CHECK ((attack_event_key ~ '^[0-9a-f]{64}$'::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_key_version_check CHECK ((attack_event_key_version = 'attack-event-key-v1'::text));

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_status_check CHECK ((event_status = ANY (ARRAY['ACTIVE'::text, 'WITHDRAWN'::text, 'SUPERSEDED'::text])));

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_created_by_run_id_fkey FOREIGN KEY (created_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.ingestion_checkpoints ADD CONSTRAINT ingestion_checkpoints_previous_same_stream_fk FOREIGN KEY (previous_checkpoint_id, source_key, city_key, stream_key) REFERENCES ingestion_checkpoints(checkpoint_id, source_key, city_key, stream_key) ON DELETE RESTRICT;

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_created_by_run_id_fkey FOREIGN KEY (created_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.alert_episodes ADD CONSTRAINT alert_episodes_updated_by_run_id_fkey FOREIGN KEY (updated_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_duplicate_of_observation_id_fkey FOREIGN KEY (duplicate_of_observation_id) REFERENCES alert_episode_sources(source_observation_id) ON DELETE RESTRICT;

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_episode_uid_fkey FOREIGN KEY (episode_uid) REFERENCES alert_episodes(episode_uid) ON DELETE RESTRICT;

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_first_persisted_by_run_id_fkey FOREIGN KEY (first_persisted_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.alert_episode_sources ADD CONSTRAINT alert_episode_sources_last_seen_by_run_id_fkey FOREIGN KEY (last_seen_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_alert_episode_uid_fkey FOREIGN KEY (alert_episode_uid) REFERENCES alert_episodes(episode_uid) ON DELETE RESTRICT;

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_persisted_by_run_id_fkey FOREIGN KEY (persisted_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.attack_event_classifications ADD CONSTRAINT attack_event_classifications_supersedes_classification_uid_fkey FOREIGN KEY (supersedes_classification_uid) REFERENCES attack_event_classifications(classification_uid) ON DELETE RESTRICT;

ALTER TABLE public.attack_event_sources ADD CONSTRAINT attack_event_sources_classification_uid_fkey FOREIGN KEY (classification_uid) REFERENCES attack_event_classifications(classification_uid) ON DELETE RESTRICT;

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_alert_episode_uid_fkey FOREIGN KEY (alert_episode_uid) REFERENCES alert_episodes(episode_uid) ON DELETE RESTRICT;

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_created_by_run_id_fkey FOREIGN KEY (created_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_current_classification_uid_fkey FOREIGN KEY (current_classification_uid) REFERENCES attack_event_classifications(classification_uid) ON DELETE RESTRICT;

ALTER TABLE public.attack_events ADD CONSTRAINT attack_events_updated_by_run_id_fkey FOREIGN KEY (updated_by_run_id) REFERENCES ingestion_runs(run_id) ON DELETE RESTRICT;

CREATE INDEX ingestion_runs_status_started_idx ON public.ingestion_runs USING btree (status, started_at DESC);

CREATE UNIQUE INDEX ingestion_checkpoints_stream_seq_uidx ON public.ingestion_checkpoints USING btree (source_key, city_key, stream_key, checkpoint_seq DESC);

CREATE UNIQUE INDEX alert_episodes_open_interval_uidx ON public.alert_episodes USING btree (city_key, alert_type, start_at) WHERE (end_at IS NULL);

CREATE INDEX alert_episodes_city_start_idx ON public.alert_episodes USING btree (city_key, start_at);

CREATE INDEX alert_episode_sources_episode_idx ON public.alert_episode_sources USING btree (episode_uid) WHERE (episode_uid IS NOT NULL);

CREATE INDEX alert_episode_sources_source_time_idx ON public.alert_episode_sources USING btree (source_key, city_key, source_start_at);

CREATE INDEX attack_event_classifications_episode_idx ON public.attack_event_classifications USING btree (city_key, historical_episode_id, created_at);

CREATE INDEX attack_event_classifications_parent_idx ON public.attack_event_classifications USING btree (alert_episode_uid, created_at) WHERE (alert_episode_uid IS NOT NULL);

CREATE INDEX attack_event_classifications_verdict_idx ON public.attack_event_classifications USING btree (verdict, city_key, alert_start_at);

CREATE INDEX attack_event_sources_classification_idx ON public.attack_event_sources USING btree (classification_uid);

CREATE INDEX attack_event_sources_url_idx ON public.attack_event_sources USING btree (source_url) WHERE (source_url IS NOT NULL);

CREATE INDEX attack_event_sources_source_time_idx ON public.attack_event_sources USING btree (source_type, source_timestamp);

CREATE INDEX attack_events_active_city_time_idx ON public.attack_events USING btree (city_key, alert_start_at) WHERE (event_status = 'ACTIVE'::text);

CREATE INDEX attack_events_parent_idx ON public.attack_events USING btree (alert_episode_uid) WHERE (alert_episode_uid IS NOT NULL);

COMMIT;
