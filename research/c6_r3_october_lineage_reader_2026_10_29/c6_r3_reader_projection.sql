-- C6-R3 research-only candidate discovery, never a de-duplication authority.
-- Execute in the SAME REPEATABLE READ READ ONLY transaction as mapping validation.
WITH air AS (
 SELECT episode_uid,city_key,alert_type,episode_state,canonicalization_version,start_at,end_at
 FROM public.alert_episodes WHERE city_key='kyiv' AND alert_type='AIR'
 AND episode_state='closed' AND (start_at AT TIME ZONE 'Europe/Kyiv') >= :scope_start::timestamp
 AND (start_at AT TIME ZONE 'Europe/Kyiv') < :scope_end::timestamp
)
SELECT a.episode_uid AS minute_uid, b.episode_uid AS precise_uid
FROM air a JOIN air b ON a.episode_uid<>b.episode_uid
 AND a.start_at=date_trunc('minute',b.start_at)
 AND a.end_at=date_trunc('minute',b.end_at)
 AND a.canonicalization_version=b.canonicalization_version
 AND (a.start_at<>b.start_at OR a.end_at<>b.end_at);
-- All unknown UID-pairs must become HARD FAIL in Python before physical projection.
-- Read classifications, sources, and events separately; NEVER INNER JOIN UNBOUND parents.
