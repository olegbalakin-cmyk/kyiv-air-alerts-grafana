-- MANUAL-ONLY, NOT EXECUTED. Restricted four-case readback, no DML/DDL/grant.
-- Authorized role only: c6_shared_reader_v2; read-only compute ep-calm-rice-b5073ypp.
-- Run once after permission remediation/approval; capture output securely.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

-- psql-level fail-closed identity and isolation guard.
SELECT (
  current_user = 'c6_shared_reader_v2'
  AND current_database() = 'neondb'
  AND current_setting('transaction_isolation') = 'repeatable read'
  AND current_setting('transaction_read_only') = 'on'
  AND pg_is_in_recovery()
)::int AS identity_ok \gset
\if :identity_ok
\else
\echo 'BLOCKED: wrong role, database, isolation, read-only state or compute'
ROLLBACK;
\quit 3
\endif

-- Read-only access guard: a missing required table SELECT is a hard block.
SELECT bool_and(has_table_privilege(current_user, t.tbl, 'SELECT'))::int AS permission_ok
FROM (VALUES
  ('public.alert_episodes'),('public.alert_episode_sources'),
  ('public.ingestion_runs'),('public.attack_event_classifications'),
  ('public.attack_events'),('public.alert_state_snapshots')
) AS t(tbl) \gset
\if :permission_ok
\else
\echo 'BLOCKED: one or more required SELECT grants are missing; no owner fallback'
ROLLBACK;
\quit 4
\endif

SELECT current_user AS reader_role, current_database() AS database_name,
       current_setting('transaction_isolation') AS isolation_level,
       current_setting('transaction_read_only') AS read_only,
       pg_is_in_recovery() AS replica, pg_current_snapshot()::text AS snapshot_id,
       clock_timestamp() AS captured_at_utc;

-- Exact old episode row BEFORE-IMAGES; zero or changed rows = BLOCKED.
WITH targets(city_key,uid,legacy,start_utc,end_utc) AS (
 VALUES
 ('kharkiv','bb7d4952-52a3-45f8-a1db-13153c8f6ca3'::uuid,'604d9e3f63fa9bc3cbd78adb','2026-10-24T23:24:46.944947Z'::timestamptz,'2026-10-25T02:22:46.862159Z'::timestamptz),
 ('poltava','74ba1017-63af-4137-a5ba-246795613615'::uuid,'81ba41902e7642b95aacde52','2026-10-25T00:06:15.155767Z'::timestamptz,'2026-10-25T01:29:42.507155Z'::timestamptz),
 ('zhytomyr','b40c570e-f9db-4c7d-b7e4-3f7769e12a95'::uuid,'3d1ae87e479c137d912f9b49','2026-10-25T00:06:17.978268Z'::timestamptz,'2026-10-25T01:30:52.777820Z'::timestamptz)
)
SELECT t.city_key, t.uid AS expected_uuid, t.legacy AS expected_legacy,
       (e.episode_uid IS NOT NULL AND e.city_key=t.city_key AND
        e.legacy_episode_id=t.legacy AND e.start_at=t.start_utc AND
        e.end_at=t.end_utc AND e.alert_type='AIR') AS exact_match,
       to_jsonb(e) AS full_before_image
FROM targets t LEFT JOIN public.alert_episodes e ON e.episode_uid=t.uid
ORDER BY t.city_key;

-- Seven candidate identities: none may currently exist; exact time boundaries pinned.
WITH proposed(city_key,legacy,start_utc,end_utc) AS (
 VALUES
 ('kharkiv','5e1419914aca832269aecd97','2026-10-24T23:24:46.944947Z'::timestamptz,'2026-10-25T00:30:17.068083Z'::timestamptz),
 ('kharkiv','1f926bf2181429b41da57787','2026-10-25T01:25:28.327265Z'::timestamptz,'2026-10-25T02:22:46.862159Z'::timestamptz),
 ('poltava','9d82fda26301c5813fd5995e','2026-10-25T00:06:15.155767Z'::timestamptz,'2026-10-25T00:26:57.986096Z'::timestamptz),
 ('poltava','a8bb035a0a6b812384a61f9a','2026-10-25T01:17:40.643305Z'::timestamptz,'2026-10-25T01:29:42.507155Z'::timestamptz),
 ('zhytomyr','770e55ab0c608d531c7d1f05','2026-10-25T00:06:17.978268Z'::timestamptz,'2026-10-25T00:26:58.980319Z'::timestamptz),
 ('zhytomyr','7a37899cb0e694f822b56661','2026-10-25T01:16:21.087757Z'::timestamptz,'2026-10-25T01:30:52.777820Z'::timestamptz),
 ('cherkasy','cdbf2515f5abb87b26588794','2026-10-25T01:14:53.333785Z'::timestamptz,'2026-10-25T01:19:09.997656Z'::timestamptz)
)
SELECT p.*, count(e.episode_uid) AS existing_legacy_hits,
       count(b.episode_uid) AS existing_exact_interval_hits,
       jsonb_agg(DISTINCT to_jsonb(e)) FILTER (WHERE e.episode_uid IS NOT NULL) AS legacy_conflicting_rows
FROM proposed p
LEFT JOIN public.alert_episodes e ON e.legacy_episode_id=p.legacy
LEFT JOIN public.alert_episodes b ON b.city_key=p.city_key AND b.start_at=p.start_utc AND b.end_at=p.end_utc AND b.alert_type='AIR'
GROUP BY p.city_key,p.legacy,p.start_utc,p.end_utc
ORDER BY p.city_key,p.start_utc;

-- A valid, earlier Cherkasy row MUST remain byte-equivalent to its pinned before-image.
SELECT to_jsonb(e) AS protected_cherkasy_before_image,
       (e.legacy_episode_id='a7dd6c572640b6396fb7bec7'
        AND e.start_at='2026-10-25T00:06:18.166695Z'::timestamptz
        AND e.end_at='2026-10-25T00:26:58.650073Z'::timestamptz) AS exact_cherkasy
FROM public.alert_episodes e
WHERE e.episode_uid='ff046d6c-fc7e-4cd2-9470-3e5433c3d582'::uuid;

-- Small local collision search (do not replay complete history).
SELECT to_jsonb(e) AS nearby_row
FROM public.alert_episodes e WHERE e.city_key IN ('kharkiv','poltava','zhytomyr','cherkasy')
 AND e.start_at <= '2026-10-25T03:45:00Z'::timestamptz
 AND e.end_at >= '2026-10-24T22:00:00Z'::timestamptz AND e.alert_type='AIR'
ORDER BY e.city_key,e.start_at LIMIT 100;

-- Source and capture lineage. Empty != verified provenance. No new HTTP.
SELECT to_jsonb(s) AS source_on_old_or_protected
FROM public.alert_episode_sources s
WHERE s.episode_uid IN
 ('bb7d4952-52a3-45f8-a1db-13153c8f6ca3'::uuid,
  '74ba1017-63af-4137-a5ba-246795613615'::uuid,
  'b40c570e-f9db-4c7d-b7e4-3f7769e12a95'::uuid,
  'ff046d6c-fc7e-4cd2-9470-3e5433c3d582'::uuid)
ORDER BY s.city_key,s.source_start_at LIMIT 100;
SELECT to_jsonb(s) AS source_near_four_cases
FROM public.alert_episode_sources s
WHERE s.city_key IN ('kharkiv','poltava','zhytomyr','cherkasy')
  AND s.source_start_at <= '2026-10-25T03:45:00Z'::timestamptz
  AND COALESCE(s.source_end_at,s.source_start_at) >= '2026-10-24T22:00:00Z'::timestamptz
ORDER BY s.city_key,s.source_start_at LIMIT 100;
SELECT to_jsonb(r) AS original_ingestion_run
FROM public.ingestion_runs r WHERE r.run_id IN (
  SELECT e.created_by_run_id FROM public.alert_episodes e
  WHERE e.episode_uid IN
   ('bb7d4952-52a3-45f8-a1db-13153c8f6ca3'::uuid,
    '74ba1017-63af-4137-a5ba-246795613615'::uuid,
    'b40c570e-f9db-4c7d-b7e4-3f7769e12a95'::uuid))
LIMIT 10;

-- Three known downstream tables, including non-FK textual/JSON references.
WITH refs AS (SELECT '(bb7d4952-52a3-45f8-a1db-13153c8f6ca3|74ba1017-63af-4137-a5ba-246795613615|b40c570e-f9db-4c7d-b7e4-3f7769e12a95|604d9e3f63fa9bc3cbd78adb|81ba41902e7642b95aacde52|3d1ae87e479c137d912f9b49)'::text AS needle)
SELECT 'classifications' AS relation, to_jsonb(c) AS row_before_image
FROM public.attack_event_classifications c,refs WHERE to_jsonb(c)::text ~* refs.needle LIMIT 100;
WITH refs AS (SELECT '(bb7d4952-52a3-45f8-a1db-13153c8f6ca3|74ba1017-63af-4137-a5ba-246795613615|b40c570e-f9db-4c7d-b7e4-3f7769e12a95|604d9e3f63fa9bc3cbd78adb|81ba41902e7642b95aacde52|3d1ae87e479c137d912f9b49)'::text AS needle)
SELECT 'attack_events' AS relation, to_jsonb(a) AS row_before_image
FROM public.attack_events a,refs WHERE to_jsonb(a)::text ~* refs.needle LIMIT 100;
WITH refs AS (SELECT '(bb7d4952-52a3-45f8-a1db-13153c8f6ca3|74ba1017-63af-4137-a5ba-246795613615|b40c570e-f9db-4c7d-b7e4-3f7769e12a95|604d9e3f63fa9bc3cbd78adb|81ba41902e7642b95aacde52|3d1ae87e479c137d912f9b49)'::text AS needle)
SELECT 'alert_state_snapshots' AS relation, to_jsonb(a) AS row_before_image
FROM public.alert_state_snapshots a,refs WHERE to_jsonb(a)::text ~* refs.needle LIMIT 100;

-- Physical catalog: all inbound and outbound FK/constraints, not only 4 known tables.
SELECT co.conrelid::regclass AS on_relation,co.conname,co.contype,
       CASE WHEN co.confrelid=0 THEN NULL ELSE co.confrelid::regclass::text END AS references_relation,
       pg_get_constraintdef(co.oid) AS definition
FROM pg_catalog.pg_constraint co
WHERE co.conrelid IN ('public.alert_episodes'::regclass,'public.alert_episode_sources'::regclass,
                      'public.attack_event_classifications'::regclass,'public.attack_events'::regclass,
                      'public.alert_state_snapshots'::regclass)
   OR co.confrelid='public.alert_episodes'::regclass
ORDER BY 1,2;
SELECT t.tgrelid::regclass AS on_relation,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) AS definition
FROM pg_catalog.pg_trigger t
WHERE NOT t.tgisinternal AND t.tgrelid IN
 ('public.alert_episodes'::regclass,'public.alert_episode_sources'::regclass,
  'public.attack_event_classifications'::regclass,'public.attack_events'::regclass,
  'public.alert_state_snapshots'::regclass)
ORDER BY 1,2;
SELECT schemaname,tablename,indexname,indexdef FROM pg_catalog.pg_indexes
WHERE schemaname='public' AND tablename IN
 ('alert_episodes','alert_episode_sources','attack_event_classifications','attack_events','alert_state_snapshots')
ORDER BY tablename,indexname;
SELECT * FROM pg_catalog.pg_policies WHERE schemaname='public'
AND tablename IN ('alert_episodes','alert_episode_sources','attack_event_classifications','attack_events','alert_state_snapshots');
SELECT r.ev_class::regclass AS dependent_view,r.rulename,pg_get_ruledef(r.oid) AS definition
FROM pg_catalog.pg_rewrite r JOIN pg_catalog.pg_depend d ON d.objid=r.oid
WHERE d.refobjid='public.alert_episodes'::regclass;
SELECT i.inhparent::regclass AS parent_relation,i.inhrelid::regclass AS child_relation
FROM pg_catalog.pg_inherits i
WHERE i.inhparent='public.alert_episodes'::regclass OR i.inhrelid='public.alert_episodes'::regclass;
SELECT c.relname AS relation,a.attname AS column_name,pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
 AND a.attname ~* '(episode|legacy|observation|source|alert|event|provenance|run|supersed|snapshot|alias|canonical)'
ORDER BY c.relname,a.attnum;
ROLLBACK; -- intentionally never COMMIT
