-- PostgreSQL 18.6 synthetic-only candidate: fail-closed BEFORE DDL.
-- Not a continuous authorization barrier. Recheck at each migration/activation.
-- Intended trusted boundary excludes external superuser h2_local fixture bootstrap.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout='10s';
DO $guard$
DECLARE app text := 'h2_app_ingest_writer_test';
BEGIN
 IF session_user <> 'h2_migrator_test'
 OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user
            AND (rolsuper OR rolcreaterole OR rolbypassrls))
 THEN RAISE EXCEPTION 'H2_ROLE_PREFLIGHT_PRINCIPAL_INVALID' USING ERRCODE='42501'; END IF;
 IF pg_has_role(app,'h2_schema_owner_test','MEMBER')
 OR pg_has_role(app,'h2_head_guard_test','MEMBER')
 OR has_table_privilege(app,'public.attack_event_classifications','UPDATE')
 OR has_table_privilege(app,'public.attack_event_classifications','DELETE')
 OR has_table_privilege(app,'public.attack_event_classifications','TRUNCATE')
 OR has_table_privilege(app,'public.h2_classification_heads','UPDATE')
 OR has_table_privilege(app,'public.h2_classification_heads','DELETE')
 OR has_schema_privilege(app,'public','CREATE')
 THEN RAISE EXCEPTION 'H2_ROLE_PREFLIGHT_UNSAFE_EFFECTIVE_APP_AUTHORITY'
      USING ERRCODE='42501'; END IF;
END $guard$;
COMMIT;
