-- Research-only synthetic PostgreSQL 18 guard hardening after candidate 004.
-- Explicit pg_temp last for protected SECURITY DEFINER trigger.
-- Required: UPDATE expressions read the guarded head in WHERE.
GRANT SELECT ON public.h2_classification_heads TO h2_head_guard_test;
ALTER FUNCTION public.h2_enforce_revision_head() SET search_path TO pg_catalog, pg_temp;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM h2_app_ingest_writer_test;
