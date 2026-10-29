-- C6-OCT184-B1: immutable snapshot audit, NO DML/DDL.
-- Execute on existing Neon RO compute; single-statement snapshot mode.
-- Distinguish this from Python's REPEATABLE READ RO transaction.
WITH e AS MATERIALIZED (
 SELECT episode_uid::text AS uid, city_key, alert_type, episode_state,
        start_at, end_at
 FROM public.alert_episodes
 WHERE city_key='kyiv' AND alert_type='AIR' AND episode_state='closed'
   AND (start_at AT TIME ZONE 'Europe/Kyiv') >= timestamp '2026-10-01'
   AND (start_at AT TIME ZONE 'Europe/Kyiv') < timestamp '2026-11-01'
), c AS MATERIALIZED (
 SELECT classification_uid::text AS uid,
        alert_episode_uid::text AS parent_uid, classification_key,
        binding_state, verdict, supersedes_classification_uid::text
 FROM public.attack_event_classifications
 WHERE alert_episode_uid::text IN (SELECT uid FROM e)
), sl AS MATERIALIZED (
 SELECT attack_event_source_uid::text AS uid,
        classification_uid::text, source_link_key
 FROM public.attack_event_sources
 WHERE classification_uid::text IN (SELECT uid FROM c)
), ev AS MATERIALIZED (
 SELECT attack_event_uid::text AS uid,
        current_classification_uid::text, alert_episode_uid::text AS parent_uid,
        event_status
 FROM public.attack_events
 WHERE alert_episode_uid::text IN (SELECT uid FROM e)
)
SELECT current_database() AS database_name,
       current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       pg_is_in_recovery() AS recovery,
       txid_current_snapshot()::text AS snapshot,
       pg_last_wal_replay_lsn()::text AS replay_lsn,
       (SELECT count(*) FROM e) AS raw_episodes,
       (SELECT count(*) FROM c) AS classifications,
       (SELECT count(*) FROM sl) AS source_links,
       (SELECT count(*) FROM ev) AS events;
