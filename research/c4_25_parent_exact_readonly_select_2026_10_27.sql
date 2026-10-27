-- C4: 25 historical UNBOUND canonical parents — exact current-state READ-ONLY inspection.
-- Source: e44df1cfbdcf67c058ceb472d8f6daa3fc00ee27
--         research/c4_25_parent_materialization_root_cause_2026_10_27/registry.json
--         verified Git blob 812bbdc14b132083af58478d811e3c47516d7aa8.
-- Not executed. Requires separate owner permission to run against the approved
-- permanent-shadow Neon branch via its PINNED physical read-only compute.
-- One SELECT only. No fuzzy/same-minute matching. Keep original UTC precision;
-- do not bind, update, import, or classify on the strength of this lookup.
-- Current row presence never proves original 2026-10-01 transaction provenance.

WITH expected (
  ordinal, cohort, city_key, classification_uid, legacy_episode_id,
  start_at, end_at, historical_physical_uid
) AS (
  VALUES
    (1, 'H1', 'lviv', '1bd00338-dea9-48d2-8eae-6545f11d805e'::uuid, '202d8d1527183a6282ccf1e2', '2026-09-13T02:32:14.172141Z'::timestamptz, '2026-09-13T06:11:11.976953Z'::timestamptz, 'c90e7b05-1982-461f-945f-53d8130c627b'::uuid),
    (2, 'H1', 'lviv', 'f34a3a0e-fa4e-47c2-b660-e927c828ae46'::uuid, 'b24ba103214a22f4d5e65ce4', '2026-09-15T16:44:13.025549Z'::timestamptz, '2026-09-15T17:08:51.287249Z'::timestamptz, '451c8a2c-248a-41e5-b49e-31af3f44631f'::uuid),
    (3, 'H1', 'lviv', 'df9913ca-388b-4c52-bb86-fd195d700ad0'::uuid, 'b3df9090f7264ddbd726e113', '2026-09-12T22:00:05.398348Z'::timestamptz, '2026-09-12T22:14:23.315771Z'::timestamptz, '575f370c-6e99-4623-8219-f8fbdfd6c978'::uuid),
    (4, 'H1', 'sumy', '0a40106c-7ee9-40c4-b268-504954f3be19'::uuid, 'd1d8f1e454e15cb6ed6b306c', '2026-09-17T17:12:24Z'::timestamptz, '2026-09-17T20:56:00Z'::timestamptz, NULL::uuid),
    (5, 'H1', 'zaporizhzhia', '31f8a1e3-6380-464d-9a35-f6ddecb1b02c'::uuid, 'c138680a6beb87a4aa8be6fc', '2026-09-17T19:33:49Z'::timestamptz, '2026-09-17T21:54:45Z'::timestamptz, NULL::uuid),
    (6, 'H2', 'kharkiv', '8c01721e-b4e8-4b63-b789-9801efbd63f8'::uuid, '0fc4be61b3b03eb9027c2536', '2025-03-05T19:08:24Z'::timestamptz, '2025-03-06T03:03:45Z'::timestamptz, NULL::uuid),
    (7, 'H2', 'kharkiv', 'cbf4dd1e-1215-4595-9388-d0d30bcd55a2'::uuid, 'fc1226778d0125bc91aa669c', '2026-09-17T17:41:38Z'::timestamptz, '2026-09-17T20:55:54Z'::timestamptz, NULL::uuid),
    (8, 'H2', 'kyiv', 'b455c332-17ec-43c1-8bf4-7d2c589451ed'::uuid, '1a603e438745d4a3d6408639', '2026-09-17T02:03:00+03:00'::timestamptz, '2026-09-17T02:54:00+03:00'::timestamptz, NULL::uuid),
    (9, 'H2', 'kyiv', 'c1b3791f-2c8c-4167-bea8-622c78d044ea'::uuid, '1a8900b3e09048b0a61db83c', '2026-09-17T11:40:00+03:00'::timestamptz, '2026-09-17T11:55:00+03:00'::timestamptz, NULL::uuid),
    (10, 'H2', 'kyiv', '7617c848-89be-4d2e-8910-207f25fcd678'::uuid, '5ecf681dfd050d9e65c9d03c', '2026-09-15T15:07:00+03:00'::timestamptz, '2026-09-15T16:20:00+03:00'::timestamptz, NULL::uuid),
    (11, 'H2', 'kyiv', '7f6741fb-915d-4152-8e74-b023f05f470e'::uuid, '659fa411a4626d02df3c16b6', '2026-09-17T09:01:00+03:00'::timestamptz, '2026-09-17T09:03:00+03:00'::timestamptz, NULL::uuid),
    (12, 'H2', 'kyiv', 'b9fb0a9e-e980-4923-9ef9-a87575645e46'::uuid, '73184793018bc20346494560', '2026-09-17T09:30:00+03:00'::timestamptz, '2026-09-17T10:02:00+03:00'::timestamptz, NULL::uuid),
    (13, 'H2', 'kyiv', '457dba20-311a-4531-86a4-8d3f92efd1db'::uuid, '82984c3ddb21c5c68d737e8c', '2026-09-15T19:44:00+03:00'::timestamptz, '2026-09-15T20:09:00+03:00'::timestamptz, NULL::uuid),
    (14, 'H2', 'kyiv', 'c96ac20b-8915-4454-9197-1dc58e6fcd7c'::uuid, '874b0acd3bce44540edb93a9', '2026-09-17T21:56:00+03:00'::timestamptz, '2026-09-17T22:10:00+03:00'::timestamptz, NULL::uuid),
    (15, 'H2', 'kyiv', '5ccc8492-7b04-49db-8b61-cb91bf0f85a3'::uuid, '8ea7bc150c61e8de2929ab25', '2026-09-16T17:23:00+03:00'::timestamptz, '2026-09-16T18:08:00+03:00'::timestamptz, NULL::uuid),
    (16, 'H2', 'kyiv', '9e7e550b-03b2-43f9-bba9-2b3dc5883629'::uuid, '8fdc1d511a3ff6d0e5061c91', '2026-09-17T13:22:00+03:00'::timestamptz, '2026-09-17T13:42:00+03:00'::timestamptz, NULL::uuid),
    (17, 'H2', 'kyiv', '29a5f5ce-771a-4ef1-83d6-a1da1062e992'::uuid, '9f4dbbf90ee53e405d3f0bdb', '2026-09-16T09:10:00+03:00'::timestamptz, '2026-09-16T09:31:00+03:00'::timestamptz, NULL::uuid),
    (18, 'H2', 'kyiv', '92096abc-07aa-42b8-89b5-f249650340fc'::uuid, 'a018066fae8d383f5351c7cc', '2026-09-17T04:33:00+03:00'::timestamptz, '2026-09-17T07:18:00+03:00'::timestamptz, NULL::uuid),
    (19, 'H2', 'kyiv', '0fef7097-990b-405c-b687-3c52a1360deb'::uuid, 'a141391372695315ed5f73f7', '2026-09-16T19:59:00+03:00'::timestamptz, '2026-09-16T20:13:00+03:00'::timestamptz, NULL::uuid),
    (20, 'H2', 'kyiv', '8050c3dd-866d-4f6b-ac05-ace19b338e0e'::uuid, 'ba16519469117045b3c662e7', '2026-09-17T20:40:00+03:00'::timestamptz, '2026-09-17T20:45:00+03:00'::timestamptz, NULL::uuid),
    (21, 'H2', 'kyiv', '6562b215-5a14-4d1f-8e53-0a9ed942ef72'::uuid, 'baaa05dfc347eee6e22e2eb5', '2026-09-17T16:31:00+03:00'::timestamptz, '2026-09-17T16:57:00+03:00'::timestamptz, NULL::uuid),
    (22, 'H2', 'kyiv', 'e47ed5ca-09c1-4be1-ae74-f7ab714f1ace'::uuid, 'cce2ce6afe7dca47f7c21d4b', '2026-09-17T00:21:00+03:00'::timestamptz, '2026-09-17T01:33:00+03:00'::timestamptz, NULL::uuid),
    (23, 'H2', 'kyiv', '24e15ef6-2309-4801-89c8-ff5dc270e5dc'::uuid, 'db5d4ace535298a36b0ceadc', '2026-09-16T05:05:00+03:00'::timestamptz, '2026-09-16T05:09:00+03:00'::timestamptz, NULL::uuid),
    (24, 'H2', 'kyiv', 'b644517c-e393-4078-8fde-d53799ea4071'::uuid, 'ed5c27624d6bef47b04b5050', '2026-09-16T21:20:00+03:00'::timestamptz, '2026-09-16T21:31:00+03:00'::timestamptz, NULL::uuid),
    (25, 'H2', 'kyiv', '583be6d4-adb1-4938-8186-d97d9012c2be'::uuid, 'ef14e0c9d07f731fa667653f', '2026-09-16T06:53:00+03:00'::timestamptz, '2026-09-16T07:36:00+03:00'::timestamptz, NULL::uuid)
)
SELECT
  e.ordinal,
  e.cohort,
  e.city_key,
  e.classification_uid,
  e.legacy_episode_id AS original_id,
  e.start_at AS original_start_at,
  e.end_at AS original_end_at,
  CASE
    WHEN by_id.episode_uid IS NOT NULL AND by_interval.episode_uid IS NOT NULL
       AND by_id.episode_uid = by_interval.episode_uid
       AND by_interval.episode_state = 'closed'
       AND by_interval.canonicalization_version = 'alert-canonicalization-v1'
      THEN 'EXACT_CURRENT_PARENT'
    WHEN by_id.episode_uid IS NOT NULL AND by_interval.episode_uid IS NOT NULL
       AND by_id.episode_uid <> by_interval.episode_uid
      THEN 'TWO_DIFFERENT_PARENTS_ID_VS_INTERVAL'
    WHEN by_id.episode_uid IS NOT NULL AND by_interval.episode_uid IS NOT NULL
      THEN 'EXACT_KEYS_BUT_CONTRACT_MISMATCH'
    WHEN by_id.episode_uid IS NOT NULL
      THEN 'ID_EXISTS_BOUNDARY_OR_CITY_MISMATCH'
    WHEN by_interval.episode_uid IS NOT NULL
      THEN 'INTERVAL_EXISTS_DIFFERENT_ID'
    ELSE 'NO_EXACT_ID_OR_INTERVAL_PARENT'
  END AS current_match_status,
  by_id.episode_uid AS parent_uid_by_original_id,
  by_id.city_key AS id_match_city,
  by_id.start_at AS id_match_start_at,
  by_id.end_at AS id_match_end_at,
  by_interval.episode_uid AS parent_uid_by_exact_interval,
  by_interval.legacy_episode_id AS interval_match_legacy_id,
  by_interval.episode_state AS interval_match_state,
  by_interval.canonicalization_version AS interval_match_version,
  e.historical_physical_uid AS original_lviv_physical_uid,
  old_parent.legacy_episode_id AS lviv_physical_uid_current_id,
  old_parent.start_at AS lviv_physical_uid_current_start_at,
  old_parent.end_at AS lviv_physical_uid_current_end_at,
  old_parent.created_by_run_id AS lviv_parent_created_by_run_id,
  creator.run_kind AS lviv_creator_run_kind,
  creator.github_run_id AS lviv_creator_github_run_id,
  creator.ingest_committed_at AS lviv_creator_committed_at,
  old_parent.updated_by_run_id AS lviv_parent_updated_by_run_id,
  updater.run_kind AS lviv_updater_run_kind,
  updater.github_run_id AS lviv_updater_github_run_id,
  updater.ingest_committed_at AS lviv_updater_committed_at
FROM expected AS e
LEFT JOIN public.alert_episodes AS by_id
  ON by_id.legacy_episode_id = e.legacy_episode_id
LEFT JOIN public.alert_episodes AS by_interval
  ON by_interval.city_key = e.city_key
 AND by_interval.alert_type = 'AIR'
 AND by_interval.start_at = e.start_at
 AND by_interval.end_at = e.end_at
LEFT JOIN public.alert_episodes AS old_parent
  ON old_parent.episode_uid = e.historical_physical_uid
LEFT JOIN public.ingestion_runs AS creator
  ON creator.run_id = old_parent.created_by_run_id
LEFT JOIN public.ingestion_runs AS updater
  ON updater.run_id = old_parent.updated_by_run_id
ORDER BY e.ordinal;
