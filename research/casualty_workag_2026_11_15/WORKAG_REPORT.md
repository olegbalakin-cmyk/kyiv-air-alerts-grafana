# CASUALTY — Work AG: article-first parser, offline proof and controlled pilot gate

**Scope:** isolated research branch stacked on Work AF PR #173. No main/site-prod/WIP writes, no casualty revisions/JSON changes, no source HTTP or RSS HTTP, no PROMOTE, no merge.

## Verified source inventory

- Work P/Q/R/Z and Work X retain short verifiable source excerpts, URL and response hashes, not recoverable complete article HTML. This supports claim/replay tests, **not** a real-publisher HTML parser benchmark.
- Work AE A/B save RSS metadata/URL digests, not individual full article URLs. Do not reverse SHA-256 or invent URL.
- Work X has saved exact direct URLs for T03/T04/T05 (below). These are previous research targets, **not** proof of accessible article bodies today.
- Four fixtures in `test_workag.py` emulate the structural HTML layouts `article`, `article__body`, `post-content`, and `entry-content`. **All are synthetic**, even when the fixture key is a publisher's name. No copyrighted article body was persisted.

## Minimal implementation

- Reuses `casualty_workac_capture.py` with `analyze_direct_article(url, offline_html=...)` for a direct URL; the existing Work J/AA/X card-building path is unchanged.
- Parses transient HTML metadata (`og:title`, headline, `article:published_time`, `time.datetime`, `lang`), selects the article/body section, rejects shell/chrome-only pages as `ARTICLE_BODY_UNAVAILABLE` instead of inferring a fact from related links.
- Records publication-time provenance and a hashed title, never silently infers an attack date from a publication date. City mentions are unverified and incomplete language extraction stays UNKNOWN/NEEDS_REVIEW.
- Work J adds only `п'ять`, `п'яти`, `п'ятеро` to explicit five-death count forms. The earlier 18→20→23 rules remain conservative.
- Strict offline testing uses pre-supplied HTML bytes; network invocation requires a `ClaimedGo`. A standalone **inert** `article_oneshot.py` research executor validates exact HEAD, expiry, canonical owner digest, article-only budget ≤3, allowed literal URLs, first-run gate and GitHub atomic consumed tag before any publisher GET. No workflow calls it by default. Existing research network paths are not globally fenced by this code.

## Physical offline validation

Existing WIP test workflow gained only an isolated Work AG job. `test_workag.py` covers four layouts, metadata extraction, chrome-only HTML, wounded-vs-deaths, ages, explicit cumulative update, late death, multi-attack aggregate, region-only uncertainty, missing publication date, identical URL/body replay, changed-body update, cross-URL review, missing GO, single-use attempt budget, privacy preservation, determinism, and fail-closed runner environment. `offline_proof.py` writes a hash-manifested summary, not full source HTML.

**Evidence boundaries:**

| Check | Observed / expected boundary |
| --- | --- |
| HTML examples | 4 synthetic publisher-shaped fixtures; 0 saved full real HTML |
| Main text | 4 synthetic article bodies extracted, boilerplate excluded |
| Numeric facts | Cumulative, update and delta regression covered; no automatic credits |
| Publication date | Article metadata preferred; missing date remains unknown |
| Attack date / place | Never inferred from publication date or RSS city alone |
| Same URL same response | `DUPLICATE_SOURCE_REPLAY` |
| Same URL changed response | `NEEDS_REVIEW`, possible update |
| Different URLs / same count | No automatic incident link |
| T03–T05 | Retain `INSUFFICIENT_EVIDENCE` pending new article content |
| Network / data mutation | 0 media GET; 0 WIP/production writes; `PROMOTE=OFF` |

The current green offline tests **do not establish** live publisher extraction accuracy, JavaScript rendering support or real-world precision/recall. They prove only the tested offline and fail-closed contracts.

## Previously retained exact URLs suitable for owner review

These three addresses were recorded in Work X, not reconstructed from RSS digests:

1. **T03 / Укрінформ:** https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
2. **T04 / MIG:** https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
3. **T05 / Поліція:** https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

These are a useful primary-vs-media / revised-total test. They **do not** constitute a verified late-hospital-death trio; that scenario remains synthetic. A redirect or blocked publisher GET must fail closed, without extra URL fetch.

## ONE-SHOT ARTICLE GO REQUEST — NOT APPROVED OR ACTIVATED

**Proposed owner grant:** One one-shot research invocation of the existing offline-by-default `article_oneshot.py`, using only the three URLs above. Before approval, verify current exact HEAD and inspect the literal grant file and its canonical SHA-256. The actual approved HEAD must match `GITHUB_SHA` and grant field `approved_head`; approval is not transferable to a future commit.

- `allowed_urls.rss=[]`, `rss_get_budget=0`.
- `allowed_urls.article=[T03,T04,T05]`, `article_get_budget=3`.
- `allowed_methods=["GET"]`, unique `owner_go_id`, short expiry, owner-approved canonical grant SHA-256, immutable exact HEAD.
- Maximum 3 publisher GET attempts total, exactly one per literal URL. HTTPS + exact host allowlist, DNS/IP SSRF guard, pinned public IP, TLS original hostname, 8s connect / 20s total, maximum 2 MiB wire and decompressed, redirects OFF, retries OFF.
- The designated executor must claim an atomic spent-tag before any media GET, deny reruns (`GITHUB_RUN_ATTEMPT != 1`), reject failed/uncertain ledger writes, and leave flags OFF unless the separate grant is accepted.
- Only privacy-screened short excerpts, provenance, SHA-256, decisions and bounded evidence output. No full HTML in public artifacts. No active WIP/production writes, no incident creation, no automatic death credits, `PROMOTE=OFF`.
- Old Work AE/AF grants cannot authorize this pilot. No standalone RSS fetch and no Google News comparison are required.

**Operational caveat:** The runner has been prepared in source only; no network-enabled Actions entrypoint was activated and old network paths remain outside its GO protection. Before executing this one-shot pilot, the existing research runner must invoke only this guarded entrypoint and verify exact HEAD/permissions/no rerun. An owner grant itself is still required.

## Status

- `ARTICLE_PARSER_OFFLINE=PASS` (synthetic HTML only; real HTML unverified)
- `NUMERIC_FACT_EXTRACTION=PARTIAL` (tested common Ukrainian claims; real article and other languages unverified)
- `INCIDENT_DEDUP=PARTIAL` (same source replay safe; cross-source event identity unresolved)
- `GO_SAFETY=BLOCKED` (guarded research source exists; network executor not operationally integrated and legacy bypass exists)
- `ARTICLE_PILOT_READINESS=BLOCKED` until exact-head proof and controlled network-entrypoint verification, then separately owner GO.

No new accepted casualty checkpoint in `PROJECT_STATE.md`/`CHANGELOG.md` yet. Those files remain untouched pending coordination acceptance.
