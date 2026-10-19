-- RESEARCH-ONLY candidate. Local PG18 synthetic fixture; NEVER run on Neon here.
-- This writer is intentionally NOT a member of neondb_owner or guard-owner.
-- h2_local is the offline cluster superuser; not the Neon deployment principal.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='h2_app_ingest_writer_test') THEN
    CREATE ROLE h2_app_ingest_writer_test LOGIN PASSWORD 'synthetic_only_local_role'
      NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO h2_app_ingest_writer_test;
GRANT SELECT ON
  public.alert_episodes, public.ingestion_runs, public.ingestion_checkpoints,
  public.current_ingestion_checkpoints,
  public.attack_event_classifications, public.attack_event_sources,
  public.attack_events, public.h2_classification_heads
  TO h2_app_ingest_writer_test;
GRANT INSERT ON
  public.attack_event_classifications, public.attack_event_sources,
  public.attack_events TO h2_app_ingest_writer_test;
-- Operational CAS writer mutates ONLY derived event state, never classification history.
GRANT UPDATE (
  event_status, current_classification_uid, binding_state, alert_episode_uid,
  correction_provenance, updated_by_run_id, updated_at
) ON public.attack_events TO h2_app_ingest_writer_test;
REVOKE UPDATE, DELETE, TRUNCATE, TRIGGER, REFERENCES
  ON public.attack_event_classifications, public.attack_event_sources
  FROM h2_app_ingest_writer_test;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER, REFERENCES
  ON public.h2_classification_heads FROM h2_app_ingest_writer_test;
REVOKE EXECUTE ON FUNCTION public.h2_enforce_revision_head()
  FROM h2_app_ingest_writer_test;
-- v2: Preserve pre-existing PUBLIC schema grants rather than revoking them.
DO $check$
BEGIN
  IF EXISTS(
    SELECT 1 FROM pg_namespace n,
    LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a
    WHERE n.nspname='public' AND a.grantee=0 AND a.privilege_type='CREATE'
  ) THEN
    RAISE EXCEPTION 'H2_UNSAFE_PUBLIC_SCHEMA_CREATE'
       USING ERRCODE='42501';
  END IF;
END
$check$;
-- Built-in pg_advisory_xact_lock and hashtextextended are available via pg_catalog.
-- No CREATE / SET ROLE / owner membership / BYPASSRLS granted.