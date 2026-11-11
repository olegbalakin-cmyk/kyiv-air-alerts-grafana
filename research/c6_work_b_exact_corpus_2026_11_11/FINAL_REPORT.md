# C6 WORK B — exact C2 corpus parity and capture continuity (2026-11-11)

**Scope:** read-only SQL on Neon branch `br-bold-mode-b5rub8pq`, offline analysis of C2 GitHub Actions [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190), artifact [#13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895). No new source HTTP, Neon writes, generator changes, production change, merge or cutover. This is not Work A independent Neon→JSON readback.

## Immutable identity

- Outer GitHub artifact: `c2-shadow-inputs-43055353190-1.zip`; embedded actual bundle SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`.
- Manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`; all eight archived member SHA-256 values verified offline.
- Corpus SHA-256 `4cd2fce445e49ec200ea3a202ed8bf9e1ada9c17d60c23eb7e9c7c65e1526226`; canonical Neon ingestion `f7da738b-9f8c-4845-bbe9-2a8073477dcb`.
- GitHub workflow `main@b22a2699466170d33ea72b71bd35b4aa12706bca`, checked-out site input `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20`; run/attempt `43055353190/1`.
- Actual payload **33,135 episodes**; Neon raw `public.alert_episodes` **33,397 closed AIR episodes**, 23 cities; no episode created/updated after C2 completion `2026-11-11T16:36:22Z` at the inspected snapshot.

## Exact diagnosis of the 262 additional Neon rows

Read-only SQL identified exactly **262 older, now-superseded overlapping intervals in 10 cities**. Each one overlaps a newer retained canonical interval of the same city and `AIR` type. No duplicate `legacy_episode_id` and no exact duplicate `(city,type,start,end)`; 75 older intervals are fully contained by a newer interval, 185 partially overlap it, and two contain it. All 262 were persisted in earlier ingestion runs (2026-10-01 through 2026-11-01); none has an `alert_episode_sources` link.

The full 262-record identity/provenance inventory is [STALE_262_EPISODES.csv](STALE_262_EPISODES.csv). Each row has stale and surviving IDs, temporal bounds, status/type, persistence times, GitHub ingestion run IDs and intersection seconds; its `canonical_id` is the surviving interval with the largest temporal overlap. The pairing is diagnostic, not an approval to erase history.

**Independent exact corpus proof:** a read-only SQL query selects canonical survivors, excluding any episode for which a strictly newer overlapping episode exists (same city/type; order by `created_at,episode_uid`). It produces exactly 33,135 rows. For every city, **both** MD5 of sorted canonical IDs **and** MD5 of the sorted tuple `(legacy_episode_id,city_key,alert_type,start_at,end_at,episode_state,canonicalization_version)` match independently computed hashes over the immutable C2 payload. Times were normalized to UTC at six-decimal-second precision on both sides. This is strong field-level parity but does not certify the age-ordering heuristic for future runs: a formal current/superseded state or approved read policy is still needed. The 262-row list is an audit artifact and must not be deleted by this research.

### Per-city corpus results

Here `PASS` means raw Neon matches the exact C2 rows; `EXPLAINED` means raw Neon has only identified superseded intervals and the derived canonical subset matches C2 exactly; `BLOCKED` additionally flags an unresolved event. These statuses **do not signify global historical completeness or cutover approval**.

| City | C2 | Neon raw | Superseded | Status | Capture from source |
| --- | ---: | ---: | ---: | --- | --- |
| Cherkasy | 1,917 | 1,919 | 2 | EXPLAINED | Verified |
| Chernihiv | 2,006 | 2,033 | 27 | EXPLAINED | Verified |
| Chernivtsi | 152 | 152 | 0 | PASS | Verified |
| Dnipro | 2,833 | 2,834 | 1 | EXPLAINED | Verified |
| Ivano-Frankivsk | 168 | 168 | 0 | PASS | Verified |
| Kharkiv | 4,130 | 4,131 | 1 | EXPLAINED | Verified |
| Kherson | 1,580 | 1,580 | 0 | PASS | Verified |
| Khmelnytskyi | 491 | 491 | 0 | PASS | Verified |
| Kropyvnytskyi | 1,526 | 1,533 | 7 | EXPLAINED | Verified |
| Kyiv | 2,852 | 3,045 | 193 | EXPLAINED | Verified |
| Lutsk | 324 | 324 | 0 | PASS | Verified |
| Lviv | 171 | 171 | 0 | PASS | Verified |
| Mykolaiv | 2,319 | 2,319 | 0 | PASS | Verified |
| Odesa | 1,827 | 1,827 | 0 | PASS | Verified |
| Poltava | 2,307 | 2,313 | 6 | EXPLAINED | Verified |
| Rivne | 506 | 506 | 0 | PASS | Verified |
| Sevastopol | 573 | 573 | 0 | BLOCKED — event `25006→25008` | Verified one-hop |
| Sumy | 2,776 | 2,799 | 23 | EXPLAINED | Verified |
| Ternopil | 241 | 241 | 0 | PASS | Verified |
| Uzhhorod | 94 | 94 | 0 | PASS | Verified |
| Vinnytsia | 664 | 665 | 1 | EXPLAINED | Verified |
| Zaporizhzhia | 2,660 | 2,660 | 0 | PASS | Verified |
| Zhytomyr | 1,018 | 1,019 | 1 | EXPLAINED | Verified |
| **Total** | **33,135** | **33,397** | **262** | **12 PASS / 10 EXPLAINED / 1 BLOCKED** | **23/23 one-hop** |

### Potential statistical impact of an unsafe raw-table reader

- Counting raw Neon rows would report **262 extra episodes**, a **0.79% increase over the correct C2 canonical count**.
- Summing raw episode durations without union/dedup would add approximately **295.4942 hours** of superseded intervals; this is **not** a measured change in union-time metrics, where overlapping time can be merged.
- Kyiv accounts for 193 old records, **6.77%** of its C2 episode count and **196.8** spurious sum-of-row-hours. Sumy adds 23 records and **61.1082** summed hours. Other affected cities: Chernihiv 27, Kropyvnytskyi 7, Poltava 6, Cherkasy 2, Dnipro/Kharkiv/Vinnytsia/Zhytomyr 1 each.
- A future reader must explicitly select canonical C2-identical intervals; a raw `SELECT *` is **unsafe**.

## Independent historical capture checks

The frozen `payload.json` and manifest contain **23/23 same-run historical source receipts**, `publication_allowed=false`. Offline verified: SHA-256 of 39 captured raw response pages; 23/23 `source_sha256`, completed interval digests, previous checkpoint digests and source identities; 23/23 temporal overlaps `oldest_completed_start <= previous_checked_at <= current_checked_at`; all source clocks belong to run `43055353190/1`. All responses were replayed from frozen source bytes and matched completed interval pairs: 21 UkraineAlarm regionHistory cities; Kyiv Digital HTML **2,851** completed pairs; Sevastopol Telegram **17 HTML pages**, 14 completed pairs, 165 distinct messages. Sevastopol replay reproduced one unresolved `missing_end_before_new_start` anomaly, **25006→25008**; it remains unresolved.

For 22 cities the previous capture checkpoint cites GitHub run **42970870607** (Nov 11 at ~06:14–06:38Z); for Sevastopol it cites **42817288652** (Nov 10 13:02Z). This independently establishes **one-hop source overlap**, not a complete historical chain from the first available alert. The external-source capture is distinct from the older Neon ingestion checkpoint system.

**Provenance boundary:** `public.alert_episode_sources` has only 143 source observations, all for **Lviv**, linked to 126 distinct episodes. The other 22 cities have no per-episode source links in this table. Same-run captured-source receipts cannot fill in each episode's historic record lineage. This is an unresolved data-evidence gate, not a newly discovered source fetch outage.

## Remaining release blockers and narrow next actions

1. **Unsafe raw Neon rows:** define and independently test an approved current/superseded episode projection, preserving 262 old rows as audit history. Do not let a generator/reader count them. No writes were performed here.
2. **Independent exact-run Neon→JSON readback:** Work A must separately prove all 23 cities using the immutable C2 payload and a read-only snapshot; this WORK B only verifies canonical episode fields and source receipts.
3. **Historic origin / provenance:** one-hop receipts 23/23 do not certify complete historical coverage since each city's first date. Resolve the all-city historical chain/legacy completeness conditions; distinguish source response checks from per-episode provenance, missing for 22 cities.
4. **Sevastopol:** retain `25006→25008` as unresolved; do not fabricate an end or silently accept historical completeness.
5. **Other independent release gates:** DST raw four-case baseline remains absent and correction OFF; C3 rollback/live publication/Netlify deployment need separate approval and evidence. Keep `GLOBAL_CUTOVER=NO`.

**Proposed coordination checkpoint (docs-only PR, not an accepted release): `C6-WORK-B-EXACT-CORPUS-23-01`.** No generator edits, production changes or promotion to cutover.
