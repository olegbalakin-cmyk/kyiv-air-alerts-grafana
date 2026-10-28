-- C6-R1 research-only SELECT prototype. No DDL, no database writes.
-- Execute only against green-cake-44216048 / br-bold-mode-b5rub8pq / neondb
-- with physical read-only compute ep-calm-rice-b5073ypp.
-- Fail the reader gate unless alias and canonical rows are individually verified
-- against the pinned site-prod precise JSON before applying the crosswalk.
WITH exact_alias(alias_uid, canonical_uid) AS (
 VALUES
 ('0a72deb0-42c3-4807-aaa2-14641e4bc775'::uuid, 'f6cf2b5b-fc5d-4584-8cbd-cb242a41850d'::uuid),
 ('3520172f-6cfb-438d-a72f-311cf57aa467'::uuid, '933404bd-bd22-4f9e-8aa9-3ce873dd1848'::uuid),
 ('0fd9d070-10df-43ef-8c88-4236506b8452'::uuid, '155a160b-ae27-49bc-948d-a308ca438224'::uuid),
 ('d5b44d9b-502d-4380-bb88-c96ed2e35c67'::uuid, '7fd8fe7d-ab74-4463-8c39-9d245aea92e3'::uuid),
 ('2fc3c7fd-e339-4790-b0c1-4a6940fb642d'::uuid, '06d8398a-d7d3-44ef-b784-ac7d82fb1617'::uuid),
 ('41f46049-f9b4-4cea-9cdc-1ae787023b1b'::uuid, 'f9ba3120-8d44-4344-989d-a8d59ca5ce9a'::uuid),
 ('06ed7f0e-cb7c-41e5-9c11-058275fc662e'::uuid, 'eaa8488c-b738-4ee7-b5ef-f62f6f9a11fa'::uuid),
 ('ac4d60e9-01c5-4bd2-a675-a7b6483a2223'::uuid, '0ce0a9c2-c29c-46c7-aa0a-c37847c80639'::uuid),
 ('e0ed7957-1f8e-4d2a-b817-be94fcaf4103'::uuid, 'e16f3671-48a4-4c15-9a3d-9cf59a466db8'::uuid)
), physical_alerts AS (
 SELECT e.episode_uid, e.legacy_episode_id, e.city_key, e.alert_type,
        e.start_at, e.end_at, e.episode_state, e.canonicalization_version
 FROM public.alert_episodes e
 WHERE e.alert_type='AIR' AND e.episode_state='closed'
), verified_mapping AS (
 SELECT a.alias_uid, a.canonical_uid
 FROM exact_alias a
 JOIN physical_alerts old ON old.episode_uid=a.alias_uid
 JOIN physical_alerts canonical ON canonical.episode_uid=a.canonical_uid
 WHERE old.city_key='kyiv' AND canonical.city_key=old.city_key
   AND old.canonicalization_version=canonical.canonicalization_version
   AND old.start_at=date_trunc('minute',canonical.start_at)
   AND old.end_at=date_trunc('minute',canonical.end_at)
   AND old.episode_uid<>canonical.episode_uid
), mapping_gate AS (
 SELECT (SELECT COUNT(*) FROM exact_alias)=9
        AND (SELECT COUNT(*) FROM verified_mapping)=9
        AND (SELECT COUNT(DISTINCT canonical_uid) FROM verified_mapping)=9
        AS ok
), projected_physical AS (
 SELECT e.* FROM physical_alerts e
 CROSS JOIN mapping_gate g
 WHERE g.ok AND NOT EXISTS (
   SELECT 1 FROM verified_mapping v WHERE v.alias_uid=e.episode_uid
 )
)
SELECT p.* FROM projected_physical p ORDER BY p.city_key,p.start_at,p.episode_uid;

-- Classification/event consumer contract (separate from physical count):
-- SELECT c.*, p.episode_uid AS physical_uid
-- FROM attack_event_classifications c
-- LEFT JOIN verified_mapping m ON m.alias_uid=c.alert_episode_uid
-- LEFT JOIN alert_episodes p ON p.episode_uid=COALESCE(m.canonical_uid,c.alert_episode_uid);
-- For 25 UNBOUND, p remains NULL but c survives; do not INNER JOIN.
-- Load attack_events by event UID / current_classification_uid independently.
-- Load source memberships by classification_uid independently or aggregate via
-- LATERAL/JSONB_AGG before joining. Never join raw event x source rows for counts.
-- The COALESCE alias is a READ VIEW ONLY: it does not alter persisted A5 FK.
