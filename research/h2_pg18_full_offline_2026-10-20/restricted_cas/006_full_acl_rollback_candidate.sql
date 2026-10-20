-- Synthetic-only rollback candidate. NOT approved for production or Neon.
-- Requires independently captured, immutable pre-migration history fingerprint.
-- psql invocation MUST supply -v expected_history=<hex md5>. Fails closed otherwise.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '10s';
SELECT set_config('h2.expected_history_md5', :'expected_history', true);
SELECT set_config('h2.rollback_fault', :'fault', true);
DO $pre$
DECLARE actual text;
BEGIN
 IF to_regclass('public.h2_classification_heads') IS NULL
 OR to_regprocedure('public.h2_enforce_revision_head()') IS NULL
 OR to_regclass('public.h2_classification_one_root_uidx') IS NULL
 OR to_regclass('public.h2_classification_one_successor_uidx') IS NULL
 OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.attack_event_classifications'::regclass
                 AND tgname='h2_revision_head_after_insert' AND NOT tgisinternal)
 THEN RAISE EXCEPTION 'H2_FULL_ROLLBACK_MISSING_OBJECT' USING ERRCODE='23514'; END IF;
 IF (SELECT count(*) FROM pg_roles
     WHERE rolname IN ('h2_head_guard_test','h2_app_ingest_writer_test')) <> 2
 THEN RAISE EXCEPTION 'H2_FULL_ROLLBACK_ROLE_MISSING' USING ERRCODE='23514'; END IF;
 IF pg_get_userbyid((SELECT proowner FROM pg_proc
    WHERE oid='public.h2_enforce_revision_head()'::regprocedure)) <> 'h2_head_guard_test'
 THEN RAISE EXCEPTION 'H2_FULL_ROLLBACK_OWNER_MISMATCH' USING ERRCODE='23514'; END IF;
 SELECT md5(COALESCE(string_agg(to_jsonb(x)::text, '|' ORDER BY classification_uid::text),''))
   INTO actual FROM public.attack_event_classifications x;
 IF current_setting('h2.expected_history_md5',true) !~ '^[a-f0-9]{32}$'
    OR actual <> current_setting('h2.expected_history_md5',true)
 THEN RAISE EXCEPTION 'H2_FULL_ROLLBACK_HISTORY_CHANGED' USING ERRCODE='23514'; END IF;
END $pre$;
LOCK TABLE public.attack_event_classifications IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.h2_classification_heads IN ACCESS EXCLUSIVE MODE;
-- Recheck after acquiring locks to protect against a concurrent writer.
DO $locked$
DECLARE actual text;
BEGIN
 SELECT md5(COALESCE(string_agg(to_jsonb(x)::text, '|' ORDER BY classification_uid::text),''))
 INTO actual FROM public.attack_event_classifications x;
 IF actual <> current_setting('h2.expected_history_md5',true) THEN
  RAISE EXCEPTION 'H2_FULL_ROLLBACK_RACING_WRITE' USING ERRCODE='23514';
 END IF;
 IF current_setting('h2.rollback_fault',true)='acl' THEN
  RAISE EXCEPTION 'H2_FULL_ROLLBACK_INJECTED_ACL' USING ERRCODE='23514';
 END IF;
END $locked$;
-- Guard owner first, using synthetic superuser. Non-superuser deployment NOT proven.
ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_local;
DO $failure$
BEGIN
 IF current_setting('h2.rollback_fault',true)='owner' THEN
  RAISE EXCEPTION 'H2_FULL_ROLLBACK_INJECTED_OWNER' USING ERRCODE='23514';
 END IF;
END $failure$;
DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications;
DROP FUNCTION public.h2_enforce_revision_head();
DROP TABLE public.h2_classification_heads;
DROP INDEX public.h2_classification_one_root_uidx;
DROP INDEX public.h2_classification_one_successor_uidx;
-- Both principals are created solely for this fresh isolated synthetic cluster.
-- Revoke their schema and table access, including any column-level UPDATE.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM h2_app_ingest_writer_test;
REVOKE UPDATE (event_status, current_classification_uid, binding_state,
 alert_episode_uid, correction_provenance, updated_by_run_id, updated_at)
 ON public.attack_events FROM h2_app_ingest_writer_test;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM h2_head_guard_test;
REVOKE ALL ON SCHEMA public FROM h2_app_ingest_writer_test;
REVOKE ALL ON SCHEMA public FROM h2_head_guard_test;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM h2_app_ingest_writer_test;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM h2_head_guard_test;
-- DROP ROLE will reject unexpected dependencies in other databases, atomically.
DROP ROLE h2_app_ingest_writer_test;
DROP ROLE h2_head_guard_test;
COMMIT;
