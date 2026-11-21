# SEO/AEO read-only audit — 16 November 2026

**ID:** `SEO-AEO-READONLY-BASELINE-2026-11-16-01`  
**Status:** completed **read-only baseline**; proposed remediation **NOT IMPLEMENTED**, production **NOT CHANGED**.  
**Target:** https://ukraine-air-alerts.netlify.app/ and /en/  
**Evidence:** [machine-readable evidence](../research/seo_aeo_2026_11_16/evidence.json).  
**Audit purpose:** assess whether search engines and AI-assisted search systems can discover, read and cite the site's *historical air-alert statistics*. No claim is made about ChatGPT's probability of choosing this source.

## Executive finding

The homepage has useful basic index metadata, and the bilingual generator already emits canonical/hreflang links for Ukrainian and English. However, the dashboard's principal KPI values are injected by client-side JavaScript; the original HTML uses `—` placeholders. The published build recipe does not copy a dedicated `robots.txt` or `sitemap.xml`, and a real Netlify edge log records **404 for /robots.txt**. The strongest intervention is to publish a small collection of genuinely useful, verified, no-JavaScript HTML data pages with explicit sources, periods, city-versus-district scope and dates of generation. Static indexing aids should accompany those pages.

Important nuance: **a 404 robots.txt does not itself prohibit crawling**. It is a missing discovery/control asset, not proof that search is blocked. A displayed `index,follow` meta tag is a permission signal, not evidence of indexing. A search result that does not show the site is not proof that it is not indexed. AI search crawlers contacting `robots.txt` are not proof of content reading or answer citation.

## Repository and production baselines

| Item | Verified evidence | Interpretation |
| --- | --- | --- |
| Coordination | `main:PROJECT_STATE.md` blob `c33500a114aabeeb3dc7d0d832ca34fa3e54634b`; `CHANGELOG.md` blob `e0e9325fcd78c8a5e9a7071342c74eeacbc7faa4` | Current coordinated historical cutover complete; scheduled C6 stabilization open; no SEO production authorization |
| Homepage template | `site-prod:kyiv-air-alerts-grafana/pages-preview/index.html` blob `7c33c8517c8521a67743ec29be79edec8b6b0933` | Has descriptive UA `title`, description, `robots=index,follow,max-snippet:-1`, canonical, social previews; KPI numerical elements initially contain `—` |
| Languages | `site-prod:kyiv-air-alerts-grafana/scripts/build_bilingual_html.py` blob `484457fe171c5d56627a4382f025ad41ed965d7a` | Generator builds `/` and `/en/`, separate canonical, `lang`, and `hreflang=uk,en,x-default`; **do not recreate these** |
| Deploy configuration | `site-prod:netlify.toml` blob `74979cf4887125a7b393db9ea8e4c7158c0267aa` | Current `_site` command copies listed assets, historical KPI JSON and builds two pages; neither `robots.txt` nor `sitemap.xml` is copied/generated |
| Earlier published UI checkpoint | `PROJECT_STATE.md` says `site-prod@901dab2f`, deploy `6af9a134186a8e5d83bb3cdf` | Coordinated evidence as of 15 Nov, not necessarily latest deployment |
| Live Netlify read-only API | Site `b5aafc46-7468-4070-baf1-db80a4d30501`, current READY deploy `6afa019d1d413ed7e10c27b1`, published `2026-11-15T19:01:51.024Z`, `locked=true`, public without password/SSO | **Newer deploy than documented checkpoint**. Its exact file-byte equivalence to a Git SHA was not proven: Netlify API `commit_ref=null`. Verify production provenance before any changes. No SEO deploy performed |
| Historic JSON | Coordinated Neon→Git six-JSON publication and 23-city KPI proof referenced by `PROJECT_STATE.md`; dynamic web app consumes JSON | Content source for possible *future* historical pages, but **no new SEO values recalculated or certified in this audit** |

## Live request evidence

**Source:** Netlify Observability, read-only edge aggregates and exact request logs. Queried window 2026-11-15 09:30 UTC through 2026-11-16 09:30 UTC; effective aggregate start was approximately 2026-11-15 09:30:54 UTC because of provider retention/clamping. Exact entries, IDs and timestamps are stored in the JSON proof.

The full User-Agent ranking in that observable window contained **three requests** advertising `OAI-SearchBot/1.0`. The URL+status breakdown is:

| Time (UTC) | URL | HTTP | Request ID |
| --- | --- | --- | --- |
| 16 Nov 09:24:19.510 | `https://ukraine-air-alerts.netlify.app/robots.txt` | **404** | `01M7HTQWXPPKNPDSSZSZEB7CJ8` |
| 16 Nov 09:24:19.579 | `http://ukraine-air-alerts.netlify.app/robots.txt` | 301 | `01M7HTQWZVN8SCYSCGD73MGRCW` |
| 16 Nov 09:24:19.603 | `https://ukraine-air-alerts.netlify.app/robots.txt` | **404** | `01M7HTQX0KEY8GVJPV23SCAY8C` |

No content-page request was present **among these three matching User-Agent records**. A User-Agent string is spoofable, so this does not authenticate the network identity or prove organic search discovery. The timing may be related to this audit. The evidence supports only that these requests reached Netlify; **not** that ChatGPT indexed or cited the statistics.

The Netlify API also reported 18 successful HTTPS `/en/` responses (HTTP 200) in a 24-hour request window. This verifies actual network service, **not** that all English text is correct or indexed.

**Execution limitation:** independent direct fetch from the local execution container failed at DNS resolution for this domain; a web-page open through the browsing tool also did not yield trustworthy rendered HTML. Therefore no direct-response-body snapshot or controlled `/sitemap.xml` HTTP status is asserted. Netlify's deployment and access reports and source-code inspection are separate evidence classes.

## Findings and triage

| ID | Severity | Finding | Evidence strength | Recommended work |
| --- | --- | --- | --- | --- |
| AEO-01 | **P0** | Core historical KPI numbers are not in initial HTML; content is primarily JS/Canvas rendered | Confirmed at source-template level; not tested with each crawler | Publish fixed historical city/month HTML pages with actual numeric table cells, metric definitions, date of dataset generation, source links and availability caveats; reuse **published canonical Git historical data**, never recompute from raw event parents |
| TECH-02 | **P1** | `/robots.txt` currently returns 404 | Confirmed live edge requests and build recipe | Add a minimal deliberate robots policy that permits legitimate search discovery, plus `Sitemap:` reference. Check desired AI-agent policy with owner; do not imply that missing robots currently blocks indexing |
| TECH-03 | **P1** | `sitemap.xml` missing from the inspected deployment recipe | Confirmed in build recipe, **live path HTTP unverified** | Generate sitemap with only publicly served, indexable canonical URLs; validate built `_site` and HTTP response |
| TECH-04 | P1 | No `Dataset` schema in the inspected UA HTML template | Confirmed in template, **built-output/live version unverified** | Add restrained, truthful `schema.org/Dataset` JSON-LD to factual data pages; describe geographic/temporal coverage, provenance and limitations; test JSON-LD and no invented metric |
| LANG-05 | **Already addressed** | Bilingual language discovery | Generator has `lang`, canonical, alternate `uk/en/x-default` | Preserve and assert in tests. Do not duplicate links |
| SEO-06 | P1 | No dedicated stable textual URL for one city + a completed period in inspected build | Build supports dashboard homepage and English variant only | Pilot **Kyiv, Kharkiv, Lviv** for one verified full month each; explicitly distinguish city/hromada vs administrative district proxies and coverage start |
| META-07 | P2 | Homepage title/description are broad, not city/period query-specific | Confirmed template | Future pages need human-readable UA/EN titles, headings, canonical URLs, concise methodology and downloadable source links |
| OBS-08 | **Unverified** | Index coverage and search visibility | No authenticated GSC/Bing, no controlled ranking sample | Verify ownership, submit sitemap after release, collect impressions/clicks/index-state; use consistent query set and date-stamped snapshots |
| OBS-09 | **Unverified** | Actual citations of this site by ChatGPT/Perplexity/Gemini | No controlled multi-run answer sampling | Establish fixed test prompts, languages and repetition; record *citations*, not just answer correctness; avoid numeric probability claims without measured denominators |
| REL-10 | **Release gate** | Live deploy `6afa019d…` is newer than root coordination checkpoint `6af9a134…` | Confirmed by Netlify deployment metadata | Audit exact active artifact/branch and latest coordination state before any deploy. Preserve Netlify lock; do not infer producer from empty `commit_ref` |

## Search-discovery sampling

The browsing/search tool was asked seven exploratory queries; examples are in the JSON evidence, spanning `site:` checks, Ukrainian city/month questions and English historical-statistics questions. The **returned search samples did not surface our target domain**; several unrelated public alerts/statistics sites appeared. This is a weak discovery signal, not a measured Google/Bing index state or ranking. Results vary by engine, location, timing and personalization. Do not extrapolate a probability that any AI will choose this website.

## Recommended minimum release plan

1. **Read-only data contract and pilot scope (P0).** Select a complete historic calendar month for Kyiv, Kharkiv and Lviv with the correct administrative-unit descriptions. Derive exactly from the *same published Git JSON generation* the dashboard uses. Document date boundary convention (Europe/Kyiv), alarm count vs occupied hours, partial-month exclusions, metric definitions and whether an indicator is available or not. Never combine casualties with current-alert status.
2. **Offline proof (P0).** Generate static UA/EN textual data pages and compare every number byte-for-byte or by defined numeric tolerance to accepted same-generation site data. Require non-empty page body and meaningful tables in HTML with JavaScript disabled, unique canonical, correct `hreflang`, optional `Dataset` JSON-LD and valid sources.
3. **Discovery assets (P1).** Publish `robots.txt` and `sitemap.xml` in the explicit Netlify build output. Verify the final `_site` files; verify HTTP 200 and MIME types on a preview, then on production. No implicit `site-prod` push, Netlify deployment or schedule changes.
4. **Owner-gated preview/publish (P1).** Verify current Netlify deploy vs branch, resolve existing HTML QA harness failure, show preview to owner, obtain explicit GO before unlocking/releasing/relocking Netlify. Maintain Git-only four-hour JSON publishing; no extra Netlify deployment per routine update.
5. **Post-publication measurement (P2).** Register Search Console and Bing if authorized; submit sitemap; record search impressions, page-index counts, eligible crawler requests, referral sessions and citations to exact pages over consistent 30/60/90-day periods. Re-audit with identical prompts. Distinguish AI bot crawl from genuine referrals and answers.

**Do not implement in this audit:** website/page changes, production deploy, `site-prod` commit, C2, Neon writes, casualties, backfill, active alert service changes, or invented SEO traffic projections. This is a documentation-only proposal pending owner acceptance.

## Verification checklist for a future implementation

- [ ] Confirm current `PROJECT_STATE.md` and `CHANGELOG.md`, latest `site-prod` HEAD, published Netlify deploy and any newer accepted checkpoint.
- [ ] Ensure branch diff touches only SEO/audit code/doc files; root build and deploy gates receive explicit review.
- [ ] Use **complete verified past periods**; never represent a missing/incomplete city interval as zero alarms.
- [ ] Compare pilot values to same-generation Git JSON for all selected cities.
- [ ] Verify static HTML contains numeric tables, definitions, dates, citations and unambiguous geographic coverage without JS.
- [ ] Assert both language URLs, unique canonical and nonduplicate hreflang; all listed sitemap links resolve 200.
- [ ] Assert robots status is 200 and policy matches owner-approved crawler preferences.
- [ ] Preserve existing 23/23 data parity, Git-only updates, Netlify lock and separation from casualty/persistence.
- [ ] Preserve real proof artifacts: generated page snapshots, input blob SHAs, test outputs, deployment receipt and live HTTP checks.

## Source references

- [PROJECT_STATE.md](../PROJECT_STATE.md) and [CHANGELOG.md](../CHANGELOG.md) from `main`.
- [site-prod homepage](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/site-prod/kyiv-air-alerts-grafana/pages-preview/index.html)
- [site-prod bilingual builder](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/site-prod/kyiv-air-alerts-grafana/scripts/build_bilingual_html.py)
- [site-prod Netlify recipe](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/site-prod/netlify.toml)
- [Google: JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Google: robots.txt specification](https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt)
- [Google: dataset structured data](https://developers.google.com/search/docs/appearance/structured-data/dataset)
- [OpenAI: web crawler controls](https://platform.openai.com/docs/bots)
