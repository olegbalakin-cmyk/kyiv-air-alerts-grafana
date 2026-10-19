-- SYNTHETIC-OFFLINE ONLY. Not an authorization to rollback in Neon.
-- Requires all writers stopped, exclusivity verified, and external ACL restoration plan.
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE public.attack_event_classifications IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.h2_classification_heads IN ACCESS EXCLUSIVE MODE;
DO $check$
BEGIN
  IF to_regclass('public.h2_classification_heads') IS NULL
     OR NOT EXISTS (SELECT 1 FROM pg_trigger
       WHERE tgname='h2_revision_head_after_insert' AND NOT tgisinternal) THEN
    RAISE EXCEPTION 'H2_ROLLBACK_EXPECTED_OBJECT_MISSING' USING ERRCODE='23514';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.h2_classification_heads h
    WHERE NOT EXISTS (
      SELECT 1 FROM public.attack_event_classifications c
      WHERE c.classification_uid = h.tip_classification_uid
      AND (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at)
      IS NOT DISTINCT FROM
        (h.city_key,h.historical_episode_id,h.alert_start_at,h.alert_end_at)
    )
  ) THEN
    RAISE EXCEPTION 'H2_ROLLBACK_INCONSISTENT_HEAD' USING ERRCODE='23514';
  END IF;
END
$check$;
DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications;
DROP FUNCTION public.h2_enforce_revision_head();
DROP TABLE public.h2_classification_heads;
DROP INDEX public.h2_classification_one_root_uidx;
DROP INDEX public.h2_classification_one_successor_uidx;
COMMIT;
-- Role/ACL reversal is separate: do not drop roles in a shared cluster.
-- On disposable single-purpose PostgreSQL use explicit REVOKEs / DROP ROLE
-- only after checking all cross-database dependencies.