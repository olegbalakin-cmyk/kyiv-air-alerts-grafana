# CASUALTY Work AF — RSS FILTER, ARTICLE HOSTS, ONE-SHOT OWNER GO

Research-only, stacked on Work AE PR #172. **Strict offline toward media:** no new RSS/article GET, PROMOTE OFF, no main/site-prod/active WIP/Neon/Netlify/C2 writes. The existing 4-hour schedule and 23 RSS/10 article budgets remain unchanged. This is a staged technical test, NOT authorization to enable network monitoring.

## Saved physical evidence independently checked

- Pilot A #43700780104, artifact #14156356307: ZIP SHA256 `28ad8b5cc105c81d87d15d04912af1285bf4c1bd62e52cacbfb6d4226770041d`; inner `pilot_receipt.json` SHA256 `ce2e86e194bd48ea4fa08e5dcdfde72bda121068271c1f38c1ba7c6ae0a7dde0`.
- Pilot B #43700806130, artifact #14156048863: ZIP SHA256 `95898566c9dba46bf83a5f2c8711698078d9c3a4b5f55737f61306261423e41f`; inner `rss_pilot_metadata.json` SHA256 `4e9aefeb1d2c1326c8959819c6a94d10110fa1248102c32571338fbabbea11f4`.
- A reported **one** Odesa city+fatality+attack hit; B reported **six** broader fatality+attack keyword hits (3 Radio Svoboda, 1 Ukrainska Pravda, 2 Hromadske Radio). B included English fatality and broader military/Russia terms, did **not** enforce exact city. Snapshots differ: A's relevant Odesa URL hash does not occur in B's full Hromadske Radio URL-hash list. **This is not a measurable six-versus-one recall delta**, and neither preserved the exact six headlines or article URLs.

## Host evidence and staged article allowlist

| Source | Exact hostname observed in Pilot B's retained first-three samples | Status |
| --- | --- | --- |
| Ukrinform | `www.ukrinform.ua` | Previously permitted |
| Radio Svoboda | `www.radiosvoboda.org` | Added, syntactic offline only |
| Ukrainska Pravda | `www.pravda.com.ua` | Added, syntactic offline only |
| Interfax Ukraine | `en.interfax.com.ua` | Added, syntactic offline only |
| Hromadske Radio | `hromadske.radio` | Added, syntactic offline only |
| Espreso | No article hostname verified; feed HTTP 403 | BLOCKED |

Exact observed hosts only, no wildcards; 115 article hostnames were **not** individually saved. Unknown subdomains and private IP targets remain blocked. DNS resolution verifies all returned IPs are public, the chosen pinned address is checked again before connection, TLS uses original hostname, redirects are blocked, 8-second connect/20-second article deadline and 2 MiB wire/decompressed caps remain. Host allowlisting is not owner network GO.

## Conservative filter behavior

Keep old Work AD `relevant_news` for comparison; new `classify_source_news` retains potentially relevant attack-only items for future casualty updates and distinguishes late death, attack with wounded only, missing attack causality, historical anniversary and region-only/multi-city reports. Region-only/multi-city results have status `NEEDS_ARTICLE_CITY_CHECK` and **do not enter** any arbitrary city's candidate queue. This is conservative: unresolved results are not yet persisted across cycles, requiring explicit future owner-approved shadow routing if they are to be reviewed. No new confirmed deaths or incident identity. Offline synthetic fixtures are not a real-world precision/recall measure.

## Single-use GO safety boundary

A new **staged, not activated** `casualty_go_guard.py` validates unique ID, exact head, expiry, canonical owner-approved grant digest, HTTPS literal URL list and separate attempt budgets, then performs exactly one non-retried atomic GitHub tag-ref creation `refs/tags/casualty-owner-go-consumed/<id>` before allowing a request. Duplicate creates and ambiguous timeouts fail closed; a consumed GO is never automatically returned. A two-worker mock and a GitHub API synthetic tag collision test are part of the existing offline workflow. The latter proves GitHub API cross-run atomicity only after an exact-head physical SUCCESS. It never contacts media.

**Critical limitation:** older research workflows are not yet forced to use this module; it cannot prevent a separate worker from re-running a legacy network pilot. Therefore a future owner article GO remains blocked until the **one designated executor** is confirmed to use the shared guard for every network entry point, with an immutable owner-approved manifest and exact URLs. Permissions to delete or overwrite the spent ref must be excluded from the threat model or denied by ruleset for an irreversible guarantee.

## Next request — not an article GO yet

The real article URLs in saved Pilot A/B proofs are SHA256-only and cannot be reconstructed. Request new owner approval for a **minimal 1–3 feed GET metadata recapture** restricted to exact known feed URLs and a maximum three literal article URLs retained from items. The follow-on, separate article GO should cover at most three approved exact URLs, GET only, HTTPS + DNS/IP pinned, 8-second connect/20-second total, 2 MiB, no redirects/retries, 0 active WIP writes/credits, PROMOTE OFF. Without exact URLs or verified GO integration do NOT perform article HTTP.

Google News comparison requires same-window observations and remains NOT MEASURED.
