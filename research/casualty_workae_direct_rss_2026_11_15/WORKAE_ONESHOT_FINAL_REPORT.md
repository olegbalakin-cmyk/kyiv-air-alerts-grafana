# CASUALTY Work AE — one-shot six-direct-RSS HTTP pilot FINAL REPORT

**Date:** 2026-11-15. **Approval:** owner explicitly permitted exactly six read-only RSS GET for exact six Work AE addresses, max 1 GET/URL, 15-second request deadline, redirects/retries OFF, HTTPS, public-IP SSL pin, 2 MiB response, zero article GET, no active WIP writes or death credits.

## Immutable execution proof

- Research source baseline: Work AE Draft PR #171 at `53c48f0b6b3ed515df34eb13c01a0872d9e65d32`, rechecked immediately before activation.
- One-shot execution commit: `1f5b8f9e64b3583f56c8f5cba84977c7eacd2241` on isolated `research-casualty-workae-six-rss-live-2026-11-15`; single-use trigger message, no rerun.
- Physical Actions [#43700780104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700780104) **SUCCESS**; active one-shot job only, WIP/smoke skipped.
- ZIP [artifact #14156356307](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700780104/artifacts/14156356307), **independently downloaded and rehashed** SHA-256 `28ad8b5cc105c81d87d15d04912af1285bf4c1bd62e52cacbfb6d4226770041d`.
- Inner `pilot_receipt.json` SHA-256 `ce2e86e194bd48ea4fa08e5dcdfde72bda121068271c1f38c1ba7dde0`, independently rehashed against `sha256_manifest.json`.
- Time window: 2026-11-15 09:45:48.715–09:45:51.031 UTC. Six attempted GET, one per address; **no retries, no redirect follows, no article GET, no current WIP writes, zero death credits, PROMOTE OFF.** The test job used source code Work AC pinned HTTPS + public-DNS-address check; no special broad network permissions.

## Real observed feed data

| Feed / URL | HTTP | Content-Type | Entries | Direct publisher links | Work AC exact article-host allowlist | Keyword relevant 23-city entries | Items <=8h | Oldest to newest UTC | Cache headers |
|---|---:|---|---:|---:|---:|---:|---:|---|---|
| Укрінформ — https://www.ukrinform.ua/rss/block-lastnews | 200 | application/rss+xml | 30 | 30 | 30 | 0 | 30 | 2026-11-15 05:03 to 09:27 | ETag no; Last-Modified no |
| Радіо Свобода — https://www.radiosvoboda.org/api/zrqiteuuir | 200 | text/xml | 20 | 20 | 0 | 0 | 7 | 2026-11-14 15:51 to 2026-11-15 09:31 | ETag no; Last-Modified no |
| Українська правда — https://www.pravda.com.ua/rss/view_news/ | 200 | application/rss+xml | 20 | 20 | 0 | 0 | 16 | 2026-11-14 22:03 to 2026-11-15 09:26 | ETag no; Last-Modified yes |
| Інтерфакс-Україна — https://en.interfax.com.ua/news/last.rss | 200 | application/rss+xml | 25 | 25 | 0 | 0 | 0 | 2026-11-14 09:08 to 14:58 | ETag no; Last-Modified yes |
| Еспресо — https://espreso.tv/rss | **403** | text/html | — | — | — | — | — | no RSS payload | ETag no; Last-Modified no |
| Громадське радіо — https://hromadske.radio/feed | 200 | application/rss+xml | 20 | 20 | 0 | **1 (Odesa)** | 5 | 2026-11-14 10:40 to 2026-11-15 09:42 | ETag yes; Last-Modified yes |
| **Total available** | 5 successful / 6 | RSS2 all | **115** | **115** | **30** | **1** | **58** | one single sampled cycle | — |

Notes: Only 1/115 is a *keyword candidate*, **not a confirmed fatal attack, verified numeric death assertion, or source article proof**. No article capture was authorized. Every successful feed was RSS2 with readably time-zoned RFC822 `pubDate`; sample showed 0 invalid/missing timestamps. Links are syntactically direct publisher URLs, **NOT article HTTP availability tested**. Radio Svoboda publisher URLs do not satisfy Work AC's exact non-www allowlist, as evidenced by 0/20 in its verified RSS sample; other feed hosts also need a security review. National feeds capture only 0–1 relevant entry on one brief snapshot, so it would be wrong to rank their long-term value or mark 0 as general absence.

## Depth and four-hour continuity

- Ukrinform: 30 items spanning **4.40 hours**. This is only marginally more than one four-hour interval. A single failed cycle would likely outrun the oldest item at this observed publishing rate, even if there is a 48-hour scan-state overlap. Feed retention, not cursor overlap, is the limiting factor.
- Radio Svoboda: 20 items spanning 17.66 hours; coverage of a missed cycle *possible* in this sample, but not guaranteed under higher publishing volume.
- Ukrainska Pravda: 20 items spanning 11.38 hours. Similar caveat.
- Interfax: 25 items spanning 5.82 hours, but the newest entry at 14:58 UTC on 14 Nov is ~19h old at sampling; possible stale/limited English-language news feed; cannot infer live continuity.
- Hromadske Radio: 20 items spanning 23.03 hours; stronger observed depth than most, but only five posts in the most recent 8h.
- The observed feed span is not a guaranteed depth/service-level commitment. We did not sample 2+ successive cycles.

## Incremental reach vs Google News

No same-window real Google News snapshot from this specific 09:45Z pilot existed in Work AB–AD retained proofs, and no Google News GET was permitted. Hence **Google News matches, incremental detections, incident-level duplicates and real numeric fact cards = NOT MEASURED, not zero**. The pilot found 0 identical article URL hashes shared across the five direct feeds, but **this does not prove different attacks**. This is a publisher-URL crossfeed dedup metric only. No incident IDs or credits.

## Source decisions

- **Primary follow-up:** Ukrinform: direct publisher links and already allowlisted article host; however the 4.4h sample depth is fragile. Hromadske Radio: one relevant Odesa keyword hit and deeper snapshot; exact article host not allowlisted, requiring separate review before Work AC capture. Radio Svoboda: more snapshot depth, but article host allowlist mismatch; promising conditional supplement.
- **Secondary / reserve:** Ukrainska Pravda: direct links and prior configuration in main, but no relevant hits in this snapshot and article host not allowlisted. Interfax-Ukraine: direct links but old newest article, no relevant hits; consider lower priority. Espreso: HTTP 403; **do not activate** pending a separate investigation/authorization (do not retry under this GO).
- Regional feeds (Suspilne regional pages, Gwara, Kordon.Media, MOST, MykVisti, Dnipro.media) and official police/DSNS RSS were **not sent requests**, as their exact feed URL was not independently confirmed and they were outside the owner-approved six. Do not invent endpoints.

## Production constraints and release/rollback gate

Research branch only. No merge to `main`/`site-prod`/active WIP; no edits to `.github/workflows/casualty-monitor-wip.yml` or schedule `45 */4 * * *`; existing request budget stays **23 RSS GET and 10 article GET / 4h**. Since 23 Google News city queries exhaust the RSS budget already, adding any real direct RSS requires approved budget reallocation, without losing 23-city geographic coverage. No Netlify/Neon/C2/casualty JSON/revisions changes.

This owner GO is consumed. Subsequent feed GETs, article captures, RSS header/duration checks or live shadow all require **new owner GO**. No further HTTP after the one-shot. To rollback research change, close/discard draft research branch/PR or use a scoped revert only of Work AE commits; never rewind unrelated work. The one-time trigger has already executed, so its future runs/reruns are blocked by the separate run-attempt/commit-message conditions.

**Verdict:** `PHYSICAL_RSS_TRANSPORT=5/6 PASS`; `DIRECT_PUBLISHER_LINKS=115/115 IN AVAILABLE FEEDS`; `ACTUAL_FACT_CARD_COVERAGE=NOT_PROVEN`; `GOOGLE_NEWS_INCREMENTAL_COVERAGE=NOT_MEASURED`; `LIVE_SHADOW=NO_GO_PENDING_NEW_APPROVAL`; `PROMOTE=OFF`.
