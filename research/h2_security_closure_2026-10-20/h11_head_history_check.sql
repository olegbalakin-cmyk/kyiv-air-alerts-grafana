-- Read-only canonical current-head / full-history consistency check.
-- Requires PostgreSQL 18.6; caller owns REPEATABLE READ READ ONLY transaction.
-- Four-part identity from accepted 001; reports explicit diagnostic rows.
WITH RECURSIVE
h AS MATERIALIZED (
 SELECT classification_uid,supersedes_classification_uid,city_key,historical_episode_id,alert_start_at,alert_end_at
 FROM public.attack_event_classifications
),
ids AS MATERIALIZED (SELECT DISTINCT city_key,historical_episode_id,alert_start_at,alert_end_at FROM h),
walk(classification_uid,path) AS (
 SELECT classification_uid,ARRAY[classification_uid] FROM h WHERE supersedes_classification_uid IS NULL
 UNION ALL
 SELECT c.classification_uid,w.path||c.classification_uid
 FROM h c JOIN walk w ON c.supersedes_classification_uid=w.classification_uid
 WHERE NOT c.classification_uid=ANY(w.path)
),
issues AS (
 SELECT 'DUPLICATE_SUCCESSOR' AS code,supersedes_classification_uid::text AS key
 FROM h WHERE supersedes_classification_uid IS NOT NULL
 GROUP BY supersedes_classification_uid HAVING count(*)>1
 UNION ALL
 SELECT 'INVALID_PREDECESSOR_IDENTITY',c.classification_uid::text
 FROM h c LEFT JOIN h p ON p.classification_uid=c.supersedes_classification_uid
 WHERE c.supersedes_classification_uid IS NOT NULL AND
 (p.classification_uid IS NULL OR
 (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at) IS DISTINCT FROM
 (p.city_key,p.historical_episode_id,p.alert_start_at,p.alert_end_at))
 UNION ALL
 SELECT 'INVALID_ROOT_OR_TIP',i.city_key||':'||i.historical_episode_id||':'||i.alert_start_at::text||':'||i.alert_end_at::text
 FROM ids i WHERE
 (SELECT count(*) FROM h c WHERE
   (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at) IS NOT DISTINCT FROM
   (i.city_key,i.historical_episode_id,i.alert_start_at,i.alert_end_at)
   AND c.supersedes_classification_uid IS NULL)<>1
 OR
 (SELECT count(*) FROM h c WHERE
   (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at) IS NOT DISTINCT FROM
   (i.city_key,i.historical_episode_id,i.alert_start_at,i.alert_end_at)
   AND NOT EXISTS(SELECT 1 FROM h successor WHERE successor.supersedes_classification_uid=c.classification_uid))<>1
 UNION ALL
 SELECT 'UNREACHABLE_OR_CYCLE',c.classification_uid::text FROM h c
 WHERE NOT EXISTS(SELECT 1 FROM walk w WHERE w.classification_uid=c.classification_uid)
 UNION ALL
 SELECT 'MISSING_HEAD',i.city_key||':'||i.historical_episode_id||':'||i.alert_start_at::text||':'||i.alert_end_at::text
 FROM ids i LEFT JOIN public.h2_classification_heads x
 ON (i.city_key,i.historical_episode_id,i.alert_start_at,i.alert_end_at) IS NOT DISTINCT FROM
 (x.city_key,x.historical_episode_id,x.alert_start_at,x.alert_end_at)
 WHERE x.tip_classification_uid IS NULL
 UNION ALL
 SELECT 'ORPHAN_HEAD',x.tip_classification_uid::text
 FROM public.h2_classification_heads x LEFT JOIN ids i
 ON (x.city_key,x.historical_episode_id,x.alert_start_at,x.alert_end_at) IS NOT DISTINCT FROM
 (i.city_key,i.historical_episode_id,i.alert_start_at,i.alert_end_at)
 WHERE i.city_key IS NULL
 UNION ALL
 SELECT 'HEAD_NOT_CANONICAL_TIP',x.tip_classification_uid::text
 FROM public.h2_classification_heads x LEFT JOIN h c ON c.classification_uid=x.tip_classification_uid
 WHERE c.classification_uid IS NULL OR
 (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at) IS DISTINCT FROM
 (x.city_key,x.historical_episode_id,x.alert_start_at,x.alert_end_at)
 OR EXISTS(SELECT 1 FROM h next WHERE next.supersedes_classification_uid=x.tip_classification_uid)
)
SELECT code,key FROM issues ORDER BY code,key;
