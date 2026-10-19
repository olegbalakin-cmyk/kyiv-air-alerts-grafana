-- Exact pg_get_viewdef reconstruction from authorized read-only Neon catalog, 2026-10-19.
-- Source: project green-cake-44216048, branch br-bold-mode-b5rub8pq,
-- database neondb, read_only compute ep-calm-rice-b5073ypp.
-- Isolated offline fixture ONLY. Do not apply to Neon, operational or production databases.
-- PostgreSQL printer emitted an unqualified ingestion_checkpoints reference.
-- Reconstructed public. qualification below is an environment-binding adaptation.
CREATE VIEW public.current_ingestion_checkpoints AS
 SELECT DISTINCT ON (source_key, city_key, stream_key) checkpoint_id,
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
   FROM public.ingestion_checkpoints
  ORDER BY source_key, city_key, stream_key, checkpoint_seq DESC;
-- Catalog-specified owner: neondb_owner.
-- Owner/GRANT defaults deliberately not reproduced: exact runtime roles unverified.
-- No runtime writer/monitor changes; current-tip DB invariant gaps are preserved.
