# WORK G — Controlled live-source capture PRE-FLIGHT (offline only)

**Scope:** 2026-11-13; research Draft PR stacked on Work E PR #110, frozen HEAD `6b44b9766fdbe2cd2d65a20413d08f4f5ca91916`. **No HTTP to publishers or official source pages was made by this work.** No merge, production, WIP updates, C2, Neon, casualty JSON, site publication or schedule.

## Evidence and existing code

Read `main:PROJECT_STATE.md`, `main:CHANGELOG.md`; reviewed PR #71 accepted coordination and PRs #102/#105/#106/#110. PR #110 already implements `OFFLINE_REPLAY` (default) and a separately gated `CONTROLLED_CAPTURE` using existing Work A parsing and reviewer; no new parser/collector was added. Work E exact-HEAD proof: [Actions #43320351570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320351570), success, artifact #13990550763, reported ZIP SHA-256 `5d313e372e53f4afd9c2d9f412e0b30c9b9f41880fae94e6f404fd4a1126b7e5`. This does not prove live media ingestion.

PR #102 frozen 11 candidates → **10 distinct publisher URLs** (two Ukr.net candidates share one ZaBor original) plus four police originals; all 14 had HTTP-200/hash receipts in [Actions #43261676781](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43261676781), artifact #13963708531. Their original bodies were **not** retained, so none of these receipts establishes the textual casualty claim.

## Exact future authorization package — NOT AUTHORIZED

Machine-readable exact URLs, domains, candidate ID linkages, known attack question, evidence gaps, and prior official requirement are in [capture_plan.json](capture_plan.json). The **intentionally invalid** [authorization_template.json](authorization_template.json) lists precisely the ten targets below and the maximum requested scope. No placeholder authorization ID or invented owner grant is accepted.

| Target | Original source and role | Candidate ID(s) | Purpose / blocking condition |
|---|---|---|---|
| T01 | ZPRZ.CITY publisher | `43a268ae2e19123554d6d476` | 18 Oct UAV, 1; source body and date/location |
| T02 | Zaporizhzhia police official | linked T01 | Independent original police body for 18 Oct |
| T03 | Ukrinform publisher | `7c3ac3280ba7ad4b9c10f3b1` | 22 Oct earlier death total 2 |
| T04 | MIG publisher | `dcdd2fe28fd1464e7fbabdc1` | 22 Oct later **cumulative** total 3 |
| T05 | Zaporizhzhia police official | linked T03/T04 | Link both updates to **one** strike; never 2+3 |
| T06 | Interfax Ukraine publisher | `db8ada77be0650fbf7c686cd` | 26 Sep UAV, 2, separate earlier credited check |
| T07 | Zaporizhzhia police official | linked T06 | Independent 26 Sep source body |
| T08 | First Zaporizhzhia publisher | `7f57e0e0e4743e98c8a88186` | 27 Sep Shahed, 1, distinct from 26 Sep |
| T09 | Zaporizhzhia police official | linked T08 | Independent 27 Sep body / incident identity |
| T10 | ZaBor original | `103256b72707ad66d91f6aae`, `cb222eea2a20aa1db2d67d5d` | Possible later death after **5 Oct** strike. **No matching independent official late-death URL is established. Cannot credit.** |

Ten URLs span seven exact allowed hostnames. No Google News or Ukr.net aggregator is a request target; the 22 Oct additional ZPRZ.CITY article and other duplicated follow-ups are deferred, not classified negative.

**Requested one-time limits:** 10 initial exact HTTPS URLs, maximum 20 HTTP requests **inclusive of redirects** (absolute Work E ceiling 30), ≥1 second between requests, ≤1,000,000 bytes per response, 15s timeout each, maximum three redirects, each redirected host revalidated. No retries, credentials, proxies, bypass of paywalls, CAPTCHA, blocking, or JavaScript fetching. Expire the proposed grant no later than 24 hours after separately recorded owner approval (Work E also enforces a 48h upper bound). Use fresh authorization ID, UTC `approved_at_utc` and `expires_at_utc`, exact target array, host allowlist, source-only research scope and single execution permission. **Prior PR #102 owner approval is spent and cannot be reused.**

**Execution control:** only after a separate owner message explicitly approving the exact URLs, limits and validity window; create a new immutable authorization file outside public deployment, replace placeholder with actual approved ID/times, and run a **separately reviewed, manual / workflow_dispatch, default-OFF, read-only research workflow** on the exact accepted commit. The workflow created by this PR, `.github/workflows/research-casualty-controlled-capture-preflight.yml`, is **strictly offline** and **must never be repurposed to fetch publishers by merely toggling an input**. No live-capture workflow has been activated or executed. Any live research workflow requires its own review before a pilot.

## Mandatory factual provenance after a separately authorized pilot

For every HTTP attempt, preserve in a private/ephemeral receipt: target URL, final URL, redirect-chain request URLs and status, response status, UTC retrieval time, response length/type, response SHA-256, failure reason; record separately each attributed claim source URL, candidate ID and event identity. For a death claim keep attack date/time vs publication date, geographic scope, weapon, civilian status, number, whether it is a new incident total, latest cumulative total or correction, prior-reported total, independent official body/source and short (≤170-character) de-identified factual excerpt plus SHA-256. Do not commit complete publisher or police pages to public GitHub; hashes/very short extracts only. Avoid conflating response hash with verified factual assertions.

**Critical integration limit:** Work E collects official articles in `official_articles` but does not independently match their claims to individual published events. Treat the results as **capture-only, NEEDS_REVIEW** until Work A/independent reviewer validates source claims. No auto-promotion, dedup credit or generator writes are authorized by successful HTTP. This is specifically **not** an end-to-end live accuracy certification.

## Baseline credit and late-death gates

Pinned `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d` city manifest `validated_through=2026-09-18`; September monthly CSV shows **4 deaths** but it does not allocate them to 26/27 September incidents. October 2026 has no monthly CSV row; `revisions.csv` contains no Zaporizhzhia revision. This does **not** prove no earlier incident credit from other inputs, or complete monthly coverage. Any September `baseline_credited` or `credited_proof` remains **UNKNOWN / BLOCKED** pending event-level reconciliation to pinned source package and latest production ledger. No synthetic `baseline_credited=0`. Do not fabricate an extra death from later 5 Oct reporting: require a **separate dated official statement naming the later death and linking it to the 5 Oct incident**, plus a verified prior-credit audit. The publication date 26 Oct is not an attack date. October remains `COVERAGE_INCOMPLETE` and no full-month total is established.

## Fail-closed authorization and automatic stop rules

- Preflight fails with no runtime flag, authorization ID, UTC validity, exact approved targets and domain subset, candidate binding, or resource budget. Invalid scheme/host/port, username/password, duplicate URL or unknown candidate also fail.
- During a future attempt stop the affected target on non-200, unexpected content type, inaccessible/blocked body, body >1 MB, nonallowlisted redirect, >3 redirects, expired/used budget; no retry or bypass.
- Stop the **entire** one-time pilot on changed code/URL/queue pins, anomalous same-host redirect to an unexpected path, multiple unexpected redirects or suspicious responses, evidence/metadata output mismatch, or any sign of media access outside exact targets.
- A run is non-repeatable by default. Re-run requires **a new explicit owner-approved authorization ID/window**, source/ledger freshness recheck, exact URL review, and prior attempt receipts/request budget accounting. No automatic rerun after partial failure.
- No HTTP-200 receipt automatically confirms a death or unlocks `PROMOTE`; no casualty publication, Netlify change or regular collection is in scope.

**Known safety residual:** existing Work E `_capture_once` revalidates allowlisted host (including a redirect) but does **not** require every same-host redirected URL to match a separately authorized exact path. For a ten-target constrained owner grant, a redirect to any new path must be held for manual review and **not considered an independently authorized primary source**. The offline tests prove rejection of redirects to other hosts, not that same-host redirect paths are exact pinned. Implementing strict redirect-path validation would be a narrow future safety hardening if the owner requires literal exact-URL redirect targeting. No claim of unconditional safe live pilot is made without resolving this policy point.

## Offline proof and decision

Offline CI tests synthetic/mock local responses and rejection paths only: exact PR #102 mappings, no dedup original URLs, official linked targets, flag & missing/expired authorization, hosts/URL guards, 14-target ceiling, request/body budgets, rejected unsafe redirects, max redirects and response sizes, private baseline checks, no automatic credit and no external requests. It compares pinned `_pr102` and `_site` immutable HEADs, emits an isolated `offline_proof.json` with source SHA-256, and uploads only that small diagnostic artifact.

**Decision: `CONTROLLED_CAPTURE_PREFLIGHT_PASS` if exact-HEAD CI is successful and all tests pass, otherwise `PARTIAL`.** PASS means a bounded one-time research pilot can be *proposed* for separate owner approval, **not** that automated casualty adjudication, exact-path redirect semantics, September credit reconciliation, or late-death confirmation is solved. Authorization remains `NOT_AUTHORIZED`, live capture OFF, publication blocked. Do not edit PR #71; send coordinator this report, tested exact HEAD, run/artifact SHA and owner approval gaps.
