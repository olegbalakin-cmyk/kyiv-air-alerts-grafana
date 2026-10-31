# C6-23CITY-PUBLICATION-01: physical generation accepted, publication blocked

Final implementation: `37a8702972c7b875f60aa73e3b0b890b869ab73b`.
Saved proof: `bdb08b148b07f3bc6030adda09a071400ba30c9b` (direct child of implementation).
[Actions 41206457252](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41206457252): SUCCESS.
[Artifact 13044522236](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41206457252/artifacts/13044522236), ZIP SHA-256
`53a4c13e90b3179ee54ef3524766a22735ed75eec2e64907c9c192d607c8224b`.

An independent download matched the ZIP digest and all **37** manifest files.
Machine verdict and manifest fetched from the immutable proof commit match the
artifact bytes. The final historical KPI index matches the same candidate's
`source_dashboard_generated_at`; no browser or CSV proof was repeated.

- Input: existing child `br-crimson-star-b59u7ge3`, parent `br-bold-mode-b5rub8pq`,
  independently confirmed ready, expiry `2026-11-01T12:20:00Z` unchanged.
- Two independent REPEATABLE READ READ ONLY snapshots, identical dataset hashes:
  **31,977 closed AIR parents, 23 cities, 145 source observations, zero open rows**.
  Zero open rows is not a certificate of current AIR status. Source observation
  UUID/parent/city relationships and projected UTC union membership were retained.
- Output: **4 generated JSON files + 2 explicit pinned Git auxiliaries**. Exact
  city: Kyiv/Kharkiv/Zaporizhzhia/Sevastopol; 19 configured raion proxies. Sevastopol
  occupation-administration provenance retained. Four known physical DST cases
  remain unchanged; no DST simulation. Kyiv frozen B2 selection and classifications
  remain unchanged, with zero rebinds; later selection stays research-only.
- Only **Kyiv** has a verified recent source capture: the already authorized
  `2026-10-31T13:17:26.719743Z` HTTP observation, not a new request. Its accepted
  ingestion commit time is distinct from generated time
  `2026-10-31T13:38:57.260963Z`. Lviv has historical checkpoint evidence only
  (`2026-10-01T12:53:17.906Z`, source observation capture time missing). Other 21
  cities have persisted historical/frozen evidence without current source receipts.
- **PUBLICATION_BLOCKED.** Source freshness is BLOCKED; source continuity,
  current active status, source contracts/cache currency and continuous writer
  remain OPEN. Physical DST repairs and Kyiv current provenance are separate
  release dependencies. Existing historical gaps do not create a new complete
  backfill requirement. Production preflight and cutover authorization remain OPEN.

Existing accepted frozen parity, frontend/browser/CSV and source-only rollback
are compatibility evidence only. This checkpoint proves physical persisted-data
regeneration and safe publication blocking. It does not prove live updates for
23 cities or current active-to-closed transitions. Repetition here cannot create
DB duplicates because this runner invokes no writer. Earlier physical writer
crash/retry proof remains accepted separately.

Production remains Git JSON; C6/C3 PARTIAL; GLOBAL_CUTOVER=NO. No new upstream
HTTP capture, Neon write, branch/TTL change, parent/site-prod/WIP/Netlify change,
repair, backfill or casualty operation occurred.

## Next owner decision

Authorize one bounded **two-round, 23-city source-continuity experiment** on this
existing child: up to **60 upstream GETs total**, at most **70 minutes**, no
unbudgeted retries or redirects, existing source rate guards retained, with
current source observations -> existing C2/C3 isolated persistence -> independent
readback -> this 23-city generator/gate. Scope includes configured exact/proxy
history and current AIR status. Kyiv municipal historical input remains the
accepted pinned auxiliary unless a specific new request is authorized. Any city
without a valid current source contract, including the special Sevastopol
source, stays OPEN; no evidence is fabricated to exhaust the budget. No
production writes or publication. If the child expires first, stop and obtain
explicit authorization for a new isolated child; do not recreate automatically.

This is a proposed owner decision, **not permission already granted**. The
current read-only workflow is ready and reproducible; it has no enabled capture
or recurring writer. The user's previous HTTP authorization covered one capture
that has already been performed.
