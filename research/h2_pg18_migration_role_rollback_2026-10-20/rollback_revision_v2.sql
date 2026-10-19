-- Synthetic-only, never run against live Neon.
BEGIN;
SET LOCAL lock_timeout='10s';
DO $pre$
BEGIN
 IF to_regclass('public.h2_classification_heads') IS NULL
 OR to_regprocedure('public.h2_enforce_revision_head()') IS NULL
 OR to_regclass('public.h2_classification_one_root_uidx') IS NULL
 OR to_regclass('public.h2_classification_one_successor_uidx') IS NULL
 OR NOT EXISTS (
   SELECT 1 FROM pg_trigger
   WHERE tgrelid='public.attack_event_classifications'::regclass
     AND tgname='h2_revision_head_after_insert' AND NOT tgisinternal
 ) THEN
   RAISE EXCEPTION 'H2_ROLLBACK_EXPECTED_OBJECT_MISSING' USING ERRCODE='23514';
 END IF;
END $pre$;
LOCK TABLE public.attack_event_classifications IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.h2_classification_heads IN ACCESS EXCLUSIVE MODE;
DO $check$
BEGIN
 IF EXISTS(
  SELECT 1 FROM public.h2_classification_heads h
  LEFT JOIN public.attack_event_classifications c
   ON c.classification_uid=h.tip_classification_uid
  WHERE c.classification_uid IS NULL
   OR (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at)
     IS DISTINCT FROM
      (h.city_key,h.historical_episode_id,h.alert_start_at,h.alert_end_at)
   OR EXISTS(SELECT 1 FROM public.attack_event_classifications x
             WHERE x.supersedes_classification_uid=h.tip_classification_uid)
 ) OR EXISTS (
   SELECT 1 FROM public.attack_event_classifications c
   WHERE NOT EXISTS(
     SELECT 1 FROM public.attack_event_classifications x
     WHERE x.supersedes_classification_uid=c.classification_uid
   ) AND NOT EXISTS(
     SELECT 1 FROM public.h2_classification_heads h
     WHERE h.tip_classification_uid=c.classification_uid
   )
 ) THEN
   RAISE EXCEPTION 'H2_ROLLBACK_INCONSISTENT_HEAD' USING ERRCODE='23514';
 END IF;
END $check$;
DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications;
DROP FUNCTION public.h2_enforce_revision_head();
DROP TABLE public.h2_classification_heads;
DROP INDEX public.h2_classification_one_root_uidx;
DROP INDEX public.h2_classification_one_successor_uidx;
COMMIT;
