# WORK I — STRICT REDIRECT-PATH SAFETY FIX

**Scope:** Offline-only code safety hardening of existing Work E controlled source capture. Work G baseline is PR #111 HEAD `630c996b2de8263bf3e9c359b388d300ebd1a741`; Work E PR #110 HEAD `6b44b9766fdbe2cd2d65a20413d08f4f5ca91916`. No media/police HTTP or deployment.

## Minimal fix

- Existing `_NoRedirect` remains active and every redirect Location is validated **before** any next GET.
- Initial requests must match an exact approved source URL. Redirects are permitted only when listed separately as exact `approved_redirect_urls` **for that individual initial source**. No implicit acceptance of another source or attack, same-host path, query change, trailing slash, AMP or canonical variant.
- Strict HTTPS, hostname, 443 port, path and query checks reject HTTP, unknown domains, credentials, invalid ports and IP targets. A blocked URL is never requested; reason and redirect chain stay in receipt.
- Self-redirects and cycles blocked, maximum three redirects, aggregate 20 request budget including redirect hops, delay ≥1 second, ≤1 MB, 15-second timeout, no retry. Approval must be valid before each HTTP attempt and expires within 24 hours. Safety violations stop the entire one-time run.
- Preserve existing Work E parser, reviewer handoff, source/candidate bindings and default `OFFLINE_REPLAY` mode. Work G preflight and Work E safety regression tests remain in offline CI.

## Exact authorization package — NOT AUTHORIZED

Unchanged Work G `capture_plan.json`: 10 initial exact HTTPS source URLs, 7 domains, 10 target IDs with their `candidate_id` associations. Updated `authorization_template.json` includes `approved_redirect_urls: []` separately for each of those 10 targets; unknown redirect destinations are prohibited. Budget: maximum 20 total GETs inclusive of redirects; at least one second between requests; no more than 1,000,000 bytes per response, 15-second timeout, maximum 3 redirects per initial URL, 0 retries, maximum 24-hour UTC approval window.

Authorization ID, approval timestamp and expiration timestamp are deliberately NULL; `enable_controlled_capture=false`, publication=false, schedule=false. No actual HTTP approval has been granted. Future exact redirect additions require a separate explicit owner decision, tied to the original target; never extend allowlists automatically.

## Conditional instructions for a future authorized, one-time research run

1. Review the unchanged 10 exact URLs, each candidate ID and its source/attack grouping; approve the finite 20-request budget and explicitly approve each exact redirect URL, if any.
2. Independently record an owner grant with real authorization ID and UTC grant/expiry times (no longer than 24 hours), the immutable approved commit, target bindings and run-once condition. Only then prepare an independently reviewed **manual** capture invocation with private authorization input. Never enable the offline CI as a live collector or activate a recurring schedule.
3. Stop the whole research run before any disallowed redirect request, redirect loop, exceeded budget, expired grant, unexpected changed code/target/queue pins or suspicious access. Other HTTP/content/size failures stop the corresponding target without retry, and require review.
4. Keep a private/ephemeral receipt for each attempt: source and requested URL, `candidate_id`, UTC retrieval timestamp, redirect chain and Location, decision/block reason, HTTP status, content type, response size/SHA-256, final URL and short de-identified claim excerpt/hash when appropriate. Do not upload full publisher or police articles to public GitHub.
5. Result is **research-only**. Work E official source bodies are not automatically adjudicated or incident-linked; `HTTP 200` never proves death. Event identity, September historical allocation and alleged later 5 October death remain blocked pending independently confirmed evidence. Never automatically PROMOTE or update casualty JSON, WIP, C2, Neon, Netlify or any production publication.
6. A new attempt, even following partial failure, requires an entirely **new** owner grant and renewed exact URL, incident and receipt review. No automatic rerun.

## Proof and verdict boundary

Baseline Work G [Actions #43387015696](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387015696) SUCCESS, 12/12 offline tests, artifact #14019520132, GitHub-reported sha256 `a06147b9a566c372eca725fa083342e239ed229609c6c77939dbdd9021b7e71e`. That run does **not** prove strict redirect-path checks.

Work I separate CI: `.github/workflows/research-casualty-strict-redirect-offline.yml`, runs the unchanged Work E tests, all 12 Work G tests (with self-loop expectation corrected), and 14 additional Work I safety tests. The workflow uploads test logs and `offline_proof.json`, whose SHA-256 source hashes bind the tested input package.

**Final release gate:** declare `STRICT_REDIRECT_PREFLIGHT_PASS` only after an exact-HEAD GitHub Actions SUCCESS for all those offline tests, verified artifact and SHA-256. Until then: `PARTIAL — exact-HEAD proof pending`. A later PASS never authorizes media HTTP.

## Physical GitHub Actions checkpoint (initial exact-head proof)

- [Actions #43396876089](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43396876089): SUCCESS at code HEAD `b97865c57823a6b7eff2d3b932a79f20a26b45fc`, 36/36 offline tests PASS (Work E 10, Work G 12, Work I 14), zero publisher HTTP.
- Artifact [#14023541047](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43396876089/artifacts/14023541047): GitHub-reported SHA-256 `f40e8bf8286d582aefbd21c946880be7db06d810a277c429a6e0c6eb83f8b895`. ZIP digest from GitHub metadata, not independently downloaded/recomputed.
- **Offline technical decision: STRICT_REDIRECT_PREFLIGHT_PASS.** Authorization status remains NOT_AUTHORIZED, and the successful test provides **no** permission for live HTTP. This documentation-only addition must receive a fresh exact-head offline CI PASS before the final HEAD is handed off.
