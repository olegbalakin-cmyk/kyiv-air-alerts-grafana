-- Synthetic-only role topology. NOT a live Neon migration.
-- Execute as schema owner after 001. Real owners/admins can bypass.
DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='h2_app_writer_test') THEN
   CREATE ROLE h2_app_writer_test LOGIN PASSWORD 'synthetic_local_only' NOINHERIT NOCREATEDB NOCREATEROLE;
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO h2_app_writer_test;
GRANT SELECT ON public.alert_episodes,public.ingestion_runs,
  public.attack_event_classifications,public.attack_event_sources,
  public.attack_events,public.h2_classification_heads TO h2_app_writer_test;
GRANT INSERT ON public.attack_event_classifications,public.attack_event_sources TO h2_app_writer_test;
-- Operational writer updates derived mutable attack_events; do not revoke those updates.
GRANT INSERT,UPDATE ON public.attack_events TO h2_app_writer_test;
REVOKE UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES
  ON public.attack_event_classifications FROM h2_app_writer_test;
REVOKE UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES
  ON public.attack_event_sources FROM h2_app_writer_test;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES
  ON public.h2_classification_heads FROM h2_app_writer_test;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- For dedicated application role: do not grant membership in neondb_owner/neon_superuser.
-- Real deployment must separately audit every schema/function/table and membership.
