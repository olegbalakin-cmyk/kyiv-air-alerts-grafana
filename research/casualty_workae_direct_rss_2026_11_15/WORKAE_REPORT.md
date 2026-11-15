# CASUALTY Work AE — direct RSS pilot preparation (2026-11-15)

## Scope and immutable base

Base Work AD PR #170 at `a502616d5264d7fd5dfe649d6a256f1a984e67cb`; Actions #43697942529 SUCCESS, GitHub artifact #14155356566 SHA-256 `99fe9eaad0ca0941caf693fe0c7ee2bc801d46f2073bd5909251446f5acc9510`.
Work AC #169; Work AB #163; Work J #121; root coordination docs inspected on main. Actual scheduled workflow checks out `multicity-wip-2026-09-16` at `45 */4 * * *`; no change made.
This research branch does not authorize source network, workflow activation, direct-source allowlist expansion or production changes.

## Baseline technical findings

- Existing Work AD is hard-coded to Google News RSS in `search_city_news`, and its candidate capture accepts source=`Google News RSS`. Direct feeds therefore need a minimal opt-in input and candidate source label; they are not already operational.
- Work AC exact HTTPS article allowlist includes `ukrinform.ua`, `www.ukrinform.ua`, `radiosvoboda.org`, `interfax.com.ua`, `suspilne.media`; **not** `www.pravda.com.ua`, `espreso.tv`, `hromadske.radio`, `gwaramedia.com`, `kordon.media`, `most.ks.ua`, `nikvesti.com`, `dnipro.media` (unlisted hosts require a separate security review). This is code policy, not network owner consent.
- Older main production generator contains RSS entry for `https://www.pravda.com.ua/rss/view_news/`; historical configured entry only, not a measured live success.
- No saved real direct-RSS responses / same-window real Google News corpus located in examined Work AB–AD retained proofs. Work AD used synthetic XML and saved Work Z article excerpts only. Quantitative direct-RSS incremental coverage remains **NOT MEASURED**, not zero.
- Code supports RSS 2.0 `item/title/link/pubDate`, preserves UTC-normalized RFC822 timezones and recognized `guid isPermaLink=true`. Atom is NOT supported in this minimal candidate and must be separately assessed.
- New optional direct-feed read reuses the existing Work AC pinned TLS+public DNS path and bounded 2 MiB body decoder; no extra parser, workflow or pipeline. Existing Google News path unchanged when option absent. Existing 23 RSS GET and 10 article GET ceilings remain unchanged.
- Direct RSS article URLs still require separately allowlisted Work AC hosts; feed host approval does not imply article host approval. Unrecognized hosts and redirects fail closed.

## Source inventory (none HTTP verified under Work AE)

| Media | Exact URL for later GO | HTTP/status | URL/coverage | Decision |
| --- | --- | --- | --- | --- |
| Укрінформ | https://www.ukrinform.ua/rss/block-lastnews | NOT TESTED | unknown | first pilot priority |
| Радіо Свобода | https://www.radiosvoboda.org/api/zrqiteuuir | NOT TESTED | unknown | first pilot priority |
| Українська правда | https://www.pravda.com.ua/rss/view_news/ | NOT TESTED; previously configured in main | unknown | first pilot priority, article host allowlist gap |
| Інтерфакс-Україна | https://en.interfax.com.ua/news/last.rss | NOT TESTED | unknown | first pilot priority, exact host not yet allowlisted |
| Еспресо | https://espreso.tv/rss | NOT TESTED | unknown | first pilot priority, allowlist gap |
| Громадське радіо | https://hromadske.radio/feed | NOT TESTED | unknown | first pilot priority, allowlist gap |
| Суспільне (Харків, Суми, Запоріжжя, Херсон, Миколаїв) | no verified channel-specific feed URL in retained sources | NOT TESTED | unknown | discover officially before GET |
| Ґвара | no verified RSS URL | NOT TESTED | unknown | feed discovery pending |
| Кордон.Медіа | no verified RSS URL | NOT TESTED | unknown | feed discovery pending |
| МОСТ | no verified RSS URL | NOT TESTED | unknown | feed discovery pending |
| МикВісті | no verified RSS URL | NOT TESTED | unknown | feed discovery pending |
| Dnipro.media | no verified RSS URL | NOT TESTED | unknown | feed discovery pending |
| Police and DSNS official feeds | none independently verified | NOT TESTED | unknown | no invented URLs / third-party substitutes |

## Quantitative coverage comparison

Window: **none measured**. No authorized GET for real direct feeds, so no matching 24–48h RSS/Google News observation is available.
For every feed, counts of relevant hits, Google News matches, incremental hits, cross-feed duplicates, direct-publisher links, accessible pages and extractable numeric fact cards are **N/A — NOT OBSERVED**.
Never interpret "not found in saved Google News samples" as "absent from Google News generally". Matching candidate URLs/title is source dedup only; attack identity requires human-reviewed evidence.

## Work AE offline proof

Synthetic direct RSS (Ukrinform-shaped, not claimed to be a genuine feed) -> existing `search_city_news` (optional direct feed, same RSS 2.0 parser) -> `add_news_candidates` -> direct Work AC publisher URL -> mocked Work AC page -> existing Work J numeric facts -> Work X source evidence index. Tests: normalized timezone; two feeds one article -> one queue/card; rerun no new card; failed feed does not move state cursor; unsafe hosts and malformed feed rejected; separate URLs not automatically incident-merged; hard-OFF and unchanged request budgets. All article GETs mocked, no source HTTP or operational WIP writes. Actual test run verdict is tracked independently in CI; do not claim a PASS until exact HEAD succeeds.

## ONE-SHOT RSS GO REQUEST (NOT YET APPROVED)

Expected base: this Work AE PR HEAD (must be re-read immediately before any pilot); expected production/WIP runtime: unchanged.
Six precise candidate URLs (each *one* GET; no invented region RSS):
1. https://www.ukrinform.ua/rss/block-lastnews
2. https://www.radiosvoboda.org/api/zrqiteuuir
3. https://www.pravda.com.ua/rss/view_news/
4. https://en.interfax.com.ua/news/last.rss
5. https://espreso.tv/rss
6. https://hromadske.radio/feed

One *separate* owner GO needed first. **No HTTP GET has been done under AE**. Approved pilot may use up to 12 total GET but this exact proposal uses only 6. One GET/URL, HTTP redirects OFF, retries OFF, timeout 15 seconds, HTTPS + DNS public-IP check and TLS pinning, 2 MiB max compressed and decoded, no cookies/auth/proxy; 0 article GET, 0 active WIP writes. Preserve bounded feed metadata only; no HTML articles, no personal information.

Record HTTP status, Content-Type, compression, ETag, Last-Modified, byte size, RSS2 vs Atom, valid item/link/guid, RFC822 timezone, earliest/latest item times and total depth, duplicate direct URLs, category relevant match for 23 cities. Google News comparison requires a saved, time-aligned 24–48h corpus and *separately authorized network GET* if not already present. A single RSS sample is insufficient to establish 4-hour robustness across missed cycles.

STOP on any 3xx, unexpected host/IP/redirect, payload >2MiB, non-XML, failed TLS, excessive errors or surprise outbound requests. Article HTTP and PROMOTE remain OFF. Do not change budgets or schedule. Any future activation must fit **within** 23 total RSS GET and 10 article GET per four-hour tick; 23 city Google News calls already use all 23 RSS slots, so adding direct RSS requires explicit reallocation or reducing city-specific Google News queries after measured coverage, not +6 requests.

## Proposed decision and rollback

PRIMARY CANDIDATES (pending physical test): Ukrinform, Radio Svoboda, Ukrainska Pravda, Interfax. RESERVE CANDIDATES: Espreso and Hromadske Radio, plus future verified Suspilne/independent regional publisher feeds. None is approved for live addition by this report alone; rankings provisional based on prospective editorial coverage, **not measured yield**.
Research rollback is to revert Work AE's isolated opt-in code on its research branch if needed. Existing live workflow never supplies `feed_url`, so is unchanged; source opt-ins remain OFF. On any future staged WIP merge use an owner-gated revert of only approved Work AE commits; preserve other tracks, no force-push. No modifications to `main`, `site-prod`, active WIP, casualty JSON, revisions, C2, Neon, Netlify or cron.
