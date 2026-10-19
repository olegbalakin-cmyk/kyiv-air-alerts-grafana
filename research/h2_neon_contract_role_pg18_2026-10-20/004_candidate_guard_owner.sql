-- RESEARCH-ONLY. Security-definer owner isolation; owner-transfer capability on
-- neondb_owner remains UNVERIFIED and requires a separate live preflight.
-- In CI, h2_local can execute ALTER FUNCTION OWNER because it is a superuser.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='h2_head_guard_test') THEN
    CREATE ROLE h2_head_guard_test NOLOGIN NOSUPERUSER NOINHERIT
      NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO h2_head_guard_test;
GRANT SELECT ON public.attack_event_classifications TO h2_head_guard_test;
GRANT INSERT, UPDATE ON public.h2_classification_heads TO h2_head_guard_test;
ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_head_guard_test;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head()
  FROM h2_app_ingest_writer_test;
-- Direct writer cannot insert/update heads; trigger executes as no-login guard.
-- A real migration requires confirmed ownership-transfer authority and safe ACL snapshot.