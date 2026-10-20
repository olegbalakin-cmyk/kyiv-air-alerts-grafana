-- H2 synthetic PostgreSQL 18.6 v4 guarded downgrade.
-- Original role topology is pre-provisioned and retained; non-superuser migrator
-- needs time-limited guard INHERIT TRUE, SET TRUE membership for reversal.
-- Exact pg_class.relacl NULL restoration is NOT promised; verify effective access.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '10s';
SELECT set_config('h2.expected_history_md5', :'expected_history', true);
SELECT set_config('h2.rollback_fault', :'fault', true);
DO $pre$
DECLARE h text;
BEGIN
 IF session_user <> 'h2_migrator_test' OR current_user <> 'h2_migrator_test'
 OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user
            AND (rolsuper OR rolbypassrls OR rolcreaterole))
 THEN RAISE EXCEPTION 'H2_ROLLBACK_MIGRATOR_INVALID' USING ERRCODE='42501'; END IF;
 IF to_regclass('public.h2_classification_heads') IS NULL
 OR to_regprocedure('public.h2_enforce_revision_head()') IS NULL
 OR to_regclass('public.h2_classification_one_root_uidx') IS NULL
 OR to_regclass('public.h2_classification_one_successor_uidx') IS NULL
 OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='h2_revision_head_after_insert'
 AND tgrelid='public.attack_event_classifications'::regclass AND NOT tgisinternal)
 THEN RAISE EXCEPTION 'H2_ROLLBACK_OBJECT_MISSING' USING ERRCODE='23514'; END IF;
 IF (SELECT proowner::regrole::text FROM pg_proc
     WHERE oid='public.h2_enforce_revision_head()'::regprocedure) <> 'h2_head_guard_test'
 OR NOT pg_has_role(current_user,'h2_head_guard_test','SET')
 OR NOT pg_has_role(current_user,'h2_head_guard_test','USAGE')
 THEN RAISE EXCEPTION 'H2_ROLLBACK_GUARD_ROLE_INVALID' USING ERRCODE='42501'; END IF;
 SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'|' ORDER BY classification_uid::text),''))
  INTO h FROM public.attack_event_classifications c;
 IF current_setting('h2.expected_history_md5',true) !~ '^[0-9a-f]{32}$'
 OR h <> current_setting('h2.expected_history_md5',true)
 THEN RAISE EXCEPTION 'H2_ROLLBACK_HISTORY_CHANGED' USING ERRCODE='23514'; END IF;
END $pre$;
LOCK TABLE public.attack_event_classifications IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.h2_classification_heads IN ACCESS EXCLUSIVE MODE;
DO $locked$
DECLARE h text;
BEGIN
 SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'|' ORDER BY classification_uid::text),''))
 INTO h FROM public.attack_event_classifications c;
 IF h <> current_setting('h2.expected_history_md5',true)
 THEN RAISE EXCEPTION 'H2_ROLLBACK_RACING_WRITE' USING ERRCODE='23514'; END IF;
 IF current_setting('h2.rollback_fault',true)='acl'
 THEN RAISE EXCEPTION 'H2_ROLLBACK_INJECT_ACL' USING ERRCODE='23514'; END IF;
END $locked$;
ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_migrator_test;
DO $fault$
BEGIN
 IF current_setting('h2.rollback_fault',true)='owner'
 THEN RAISE EXCEPTION 'H2_ROLLBACK_INJECT_OWNER' USING ERRCODE='23514'; END IF;
END $fault$;
DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications;
DROP FUNCTION public.h2_enforce_revision_head();
DROP TABLE public.h2_classification_heads;
DROP INDEX public.h2_classification_one_root_uidx;
DROP INDEX public.h2_classification_one_successor_uidx;
REVOKE SELECT ON public.alert_episodes, public.ingestion_runs,
 public.ingestion_checkpoints, public.current_ingestion_checkpoints,
 public.attack_event_classifications, public.attack_event_sources,
 public.attack_events FROM h2_app_ingest_writer_test;
REVOKE INSERT ON public.attack_event_classifications, public.attack_event_sources,
 public.attack_events FROM h2_app_ingest_writer_test;
REVOKE UPDATE (event_status,current_classification_uid,binding_state,
 alert_episode_uid,correction_provenance,updated_by_run_id,updated_at)
 ON public.attack_events FROM h2_app_ingest_writer_test;
-- RESEARCH ONLY: fault follows the ACTUAL original SELECT, INSERT and
-- column UPDATE REVOKEs; the accepted 008 SQL above is not edited in place.
-- The harness independently establishes these grants were present before 008.
DO $h2_research_late_acl$
DECLARE
 s bool; i bool; u bool;
BEGIN
 SELECT EXISTS(
   SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
   WHERE c.oid='public.alert_episodes'::regclass
     AND a.grantee='h2_app_ingest_writer_test'::regrole::oid
     AND a.privilege_type='SELECT'
 ) INTO s;
 SELECT EXISTS(
   SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
   WHERE c.oid='public.attack_event_classifications'::regclass
     AND a.grantee='h2_app_ingest_writer_test'::regrole::oid
     AND a.privilege_type='INSERT'
 ) INTO i;
 SELECT EXISTS(
   SELECT 1 FROM pg_attribute at
   CROSS JOIN LATERAL aclexplode(at.attacl) a
   WHERE at.attrelid='public.attack_events'::regclass
     AND at.attname='updated_at'
     AND a.grantee='h2_app_ingest_writer_test'::regrole::oid
     AND a.privilege_type='UPDATE'
 ) INTO u;
 RAISE NOTICE 'H2_008_STAGED_AFTER_3_ACL_REVOKES SELECT_PRESENT=% INSERT_PRESENT=% COLUMN_UPDATE_PRESENT=%',s,i,u;
 IF s OR i OR u THEN
  RAISE EXCEPTION 'H2_008_ACL_CHANGE_NOT_OBSERVED'
   USING ERRCODE='23514';
 END IF;
 IF current_setting('h2.rollback_fault',true)='late_acl' THEN
  RAISE EXCEPTION 'H2_008_LATE_AFTER_REAL_ACL_REVOKES'
   USING ERRCODE='23514';
 END IF;
END $h2_research_late_acl$;
REVOKE SELECT ON public.attack_event_classifications FROM h2_head_guard_test;
REVOKE USAGE ON SCHEMA public FROM h2_app_ingest_writer_test;
REVOKE USAGE ON SCHEMA public FROM h2_head_guard_test;
COMMIT;
