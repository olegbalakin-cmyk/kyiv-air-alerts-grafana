-- Research-only synthetic PostgreSQL 18 guard hardening after candidate 004.
-- Explicit pg_temp last for protected SECURITY DEFINER trigger.
ALTER FUNCTION public.h2_enforce_revision_head() SET search_path TO pg_catalog, pg_temp;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM h2_app_ingest_writer_test;
