-- H2 synthetic PostgreSQL 18.6 candidate v4: limited-role SECURITY DEFINER transfer.
-- Requires a pre-provisioned migration login, guard NOLOGIN role, app writer, and
-- a short-lived GRANT guard TO migrator WITH SET TRUE, INHERIT TRUE, ADMIN FALSE.
-- An authorized role administrator supplies/removes that membership separately.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '10s';
SELECT set_config('h2.transfer_fault', :'fault', true);
DO $pre$
BEGIN
 IF session_user <> 'h2_migrator_test' OR current_user <> 'h2_migrator_test'
 OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user
            AND (rolsuper OR rolbypassrls OR rolcreaterole))
 THEN RAISE EXCEPTION 'H2_MIGRATION_PRINCIPAL_INVALID' USING ERRCODE='42501'; END IF;
 IF to_regprocedure('public.h2_enforce_revision_head()') IS NULL
 OR (SELECT proowner::regrole::text FROM pg_proc
     WHERE oid='public.h2_enforce_revision_head()'::regprocedure) <> current_user
 OR NOT (SELECT prosecdef FROM pg_proc
         WHERE oid='public.h2_enforce_revision_head()'::regprocedure)
 THEN RAISE EXCEPTION 'H2_GUARD_FUNCTION_PRECONDITION' USING ERRCODE='23514'; END IF;
 IF NOT pg_has_role(current_user,'h2_head_guard_test','SET')
 OR NOT pg_has_role(current_user,'h2_head_guard_test','USAGE')
 OR NOT has_schema_privilege('h2_head_guard_test','public','CREATE')
 THEN RAISE EXCEPTION 'H2_GUARD_TRANSFER_MEMBERSHIP_OR_CREATE' USING ERRCODE='42501'; END IF;
 IF pg_has_role('h2_app_ingest_writer_test','h2_head_guard_test','MEMBER')
 THEN RAISE EXCEPTION 'H2_GUARD_WRITER_MEMBERSHIP_UNSAFE' USING ERRCODE='42501'; END IF;
END $pre$;
GRANT USAGE ON SCHEMA public TO h2_head_guard_test;
GRANT SELECT ON public.attack_event_classifications TO h2_head_guard_test;
GRANT SELECT, INSERT, UPDATE ON public.h2_classification_heads TO h2_head_guard_test;
ALTER FUNCTION public.h2_enforce_revision_head()
 SET search_path TO pg_catalog, pg_temp;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.h2_enforce_revision_head()
 FROM h2_app_ingest_writer_test;
ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_head_guard_test;
DO $post$
BEGIN
 IF current_setting('h2.transfer_fault',true)='owner' THEN
  RAISE EXCEPTION 'H2_GUARD_TRANSFER_INJECT_OWNER' USING ERRCODE='23514'; END IF;
 IF (SELECT proowner::regrole::text FROM pg_proc
     WHERE oid='public.h2_enforce_revision_head()'::regprocedure) <> 'h2_head_guard_test'
 OR NOT (SELECT prosecdef AND proconfig @> ARRAY['search_path=pg_catalog, pg_temp']
         FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure)
 THEN RAISE EXCEPTION 'H2_GUARD_TRANSFER_POSTCHECK' USING ERRCODE='23514'; END IF;
END $post$;
COMMIT;
