-- H2 candidate only. DO NOT RUN ON NEON without separate authorization and preflight.
-- Source: observed-partial Neon schema fixture Git blob 09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3.
-- Exact runtime equivalence and historical row population on Neon are not proven.
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

-- Fail closed, before modifying any objects. All four columns form the
-- existing application _current_tip() logical identity.
DO $preflight$
DECLARE
  n_total bigint;
  n_reachable bigint;
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.attack_event_classifications
    WHERE supersedes_classification_uid IS NOT NULL
    GROUP BY supersedes_classification_uid HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION 'H2_PREFLIGHT_DUPLICATE_SUCCESSOR' USING ERRCODE='23514';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.attack_event_classifications c
    JOIN public.attack_event_classifications p
      ON p.classification_uid = c.supersedes_classification_uid
    WHERE (c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at)
       IS DISTINCT FROM
          (p.city_key,p.historical_episode_id,p.alert_start_at,p.alert_end_at)
  ) THEN
    RAISE EXCEPTION 'H2_PREFLIGHT_CROSS_IDENTITY_PARENT' USING ERRCODE='23514';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (
      SELECT c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at,
             COUNT(*) FILTER (WHERE c.supersedes_classification_uid IS NULL) AS roots,
             COUNT(*) FILTER (WHERE NOT EXISTS (
               SELECT 1 FROM public.attack_event_classifications next
               WHERE next.supersedes_classification_uid = c.classification_uid
             )) AS tips
      FROM public.attack_event_classifications c
      GROUP BY c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at
    ) grouped WHERE grouped.roots <> 1 OR grouped.tips <> 1
  ) THEN
    RAISE EXCEPTION 'H2_PREFLIGHT_MULTIPLE_ROOTS_OR_TIPS' USING ERRCODE='23514';
  END IF;

  SELECT COUNT(*) INTO n_total FROM public.attack_event_classifications;
  WITH RECURSIVE connected(classification_uid) AS (
    SELECT classification_uid FROM public.attack_event_classifications
      WHERE supersedes_classification_uid IS NULL
    UNION ALL
    SELECT c.classification_uid FROM public.attack_event_classifications c
      JOIN connected prev ON c.supersedes_classification_uid=prev.classification_uid
  )
  SELECT COUNT(*) INTO n_reachable FROM connected;
  IF n_reachable <> n_total THEN
    RAISE EXCEPTION 'H2_PREFLIGHT_UNREACHABLE_OR_CYCLIC_REVISION count=%/%',
      n_reachable,n_total USING ERRCODE='23514';
  END IF;
END
$preflight$;

-- PostgreSQL ordinary UNIQUE permits many NULLs: independent roots remain valid.
CREATE UNIQUE INDEX h2_classification_one_successor_uidx
  ON public.attack_event_classifications (supersedes_classification_uid)
  WHERE supersedes_classification_uid IS NOT NULL;
CREATE UNIQUE INDEX h2_classification_one_root_uidx
  ON public.attack_event_classifications
    (city_key,historical_episode_id,alert_start_at,alert_end_at)
  WHERE supersedes_classification_uid IS NULL;

-- A mutable pointer is separate from append-only classifications.
-- Do not add an is_current field or update historical revisions.
CREATE TABLE public.h2_classification_heads (
  city_key text NOT NULL,
  historical_episode_id text NOT NULL,
  alert_start_at timestamptz NOT NULL,
  alert_end_at timestamptz NOT NULL,
  tip_classification_uid uuid NOT NULL
    REFERENCES public.attack_event_classifications(classification_uid)
    ON DELETE RESTRICT,
  changed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (city_key,historical_episode_id,alert_start_at,alert_end_at)
);

-- Historical backfill: unique current tip was checked before schema changes.
INSERT INTO public.h2_classification_heads
  (city_key,historical_episode_id,alert_start_at,alert_end_at,tip_classification_uid)
SELECT c.city_key,c.historical_episode_id,c.alert_start_at,c.alert_end_at,c.classification_uid
FROM public.attack_event_classifications c
WHERE NOT EXISTS (
  SELECT 1 FROM public.attack_event_classifications child
  WHERE child.supersedes_classification_uid=c.classification_uid
);

-- Fixed search_path + SECURITY DEFINER permit INSERT-only restricted writers
-- to maintain the pointer. Only the table/function owner can modify this DDL.
CREATE FUNCTION public.h2_enforce_revision_head()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $body$
DECLARE
  predecessor record;
  updated_count bigint;
BEGIN
  IF NEW.supersedes_classification_uid IS NULL THEN
    INSERT INTO public.h2_classification_heads
      (city_key,historical_episode_id,alert_start_at,alert_end_at,tip_classification_uid)
    VALUES
      (NEW.city_key,NEW.historical_episode_id,
       NEW.alert_start_at,NEW.alert_end_at,NEW.classification_uid);
  ELSE
    SELECT city_key,historical_episode_id,alert_start_at,alert_end_at
    INTO predecessor
    FROM public.attack_event_classifications
    WHERE classification_uid=NEW.supersedes_classification_uid;
    IF NOT FOUND OR
      (NEW.city_key,NEW.historical_episode_id,NEW.alert_start_at,NEW.alert_end_at)
        IS DISTINCT FROM
      (predecessor.city_key,predecessor.historical_episode_id,
       predecessor.alert_start_at,predecessor.alert_end_at)
    THEN
      RAISE EXCEPTION 'H2_REVISION_PARENT_IDENTITY_MISMATCH'
        USING ERRCODE='23514';
    END IF;

    UPDATE public.h2_classification_heads
    SET tip_classification_uid=NEW.classification_uid, changed_at=now()
    WHERE city_key=NEW.city_key
      AND historical_episode_id=NEW.historical_episode_id
      AND alert_start_at=NEW.alert_start_at
      AND alert_end_at=NEW.alert_end_at
      AND tip_classification_uid=NEW.supersedes_classification_uid;
    GET DIAGNOSTICS updated_count=ROW_COUNT;
    IF updated_count <> 1 THEN
      RAISE EXCEPTION 'H2_STALE_EXPECTED_TIP_OR_MISSING_HEAD'
        USING ERRCODE='P0001';
    END IF;
  END IF;
  RETURN NEW;
END
$body$;

REVOKE ALL ON FUNCTION public.h2_enforce_revision_head() FROM PUBLIC;
REVOKE ALL ON public.h2_classification_heads FROM PUBLIC;
CREATE TRIGGER h2_revision_head_after_insert
  AFTER INSERT ON public.attack_event_classifications
  FOR EACH ROW EXECUTE FUNCTION public.h2_enforce_revision_head();

COMMIT;
