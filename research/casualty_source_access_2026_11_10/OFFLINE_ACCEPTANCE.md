# CASUALTY SOURCE ACCESS — narrow offline acceptance (2026-11-10)

**Scope:** research only, based on PR #58 exact HEAD `603496cc4a9072a734e80d50c0d880aa80ee7470`. No owner permission for new live HTTP. No production, operational WIP queue, `revisions.csv`, reviewer, automatic publication, Neon, workflows schedule, or merge changes.

## Evidence and exact limits

- Read current `main:PROJECT_STATE.md` and `main:CHANGELOG.md`, plus heads PR #56 (`d86d7095`), #57 (`13e1254f`), #58 (`603496cc`). The casualty track is independently documented in **draft** coordination PR #56; no main acceptance from that PR is inferred.
- Previous real direct publisher proof [run #42873836462](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42873836462), 3 useful documents / 4 HTML documents, one offline Odesa +3 proposal. It is NOT a five-URL WIP proof.
- Previous WIP Google wrapper failure [run #42893729621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42893729621), 20/20 wrappers unresolved.
- Last approved five-URL RSS RPC test [run #42899975187](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42899975187), artifact [13801289333](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42899975187/artifacts/13801289333), source ZIP SHA-256 `914524081d5177dc7a008bc59d8e3d6f12d93b018ff9f94fe930e73ec6a2bea4`; all 9 internal manifest SHA-256 PASS. Five wrappers resolved beyond earlier stage, three Google RPC target rejections, two publisher HTTP 403, zero captured HTML, zero proposals, replay zero. 1,656 WIP candidates frozen, 61 recent/unreviewed, sample five cities. Operational input hashes remained unchanged.
- The archived failure records include **original Google RSS URLs** and reasons, but **not** the three RPC target URLs, their destination hostname, the two Suspilne final URL paths, HTTP response headers, or redirects. The RSS `publisher_url` is a homepage metadata field, NOT verified RPC destination. An HTTP 403 does not prove a permanent block or its cause.

| Candidate/city | RSS publisher metadata | Prior result | Cause established | Decision |
| --- | --- | --- | --- | --- |
| `9d25546e422f9888a3da1964`, Kropyvnytskyi | `espreso.tv` | `GOOGLE_RPC_TARGET_NOT_ALLOWED` | RPC target failed current allowlist, exact hostname NOT retained | Keep `NEEDS_REVIEW`; no host expansion. |
| `8f3a8c96fd72c8b98fa87830`, Vinnytsia | `vinnitsa.info` | `GOOGLE_RPC_TARGET_NOT_ALLOWED` | Exact RPC destination NOT retained; headline says *Vinnytsia oblast*, not city | Keep `NEEDS_REVIEW`; require city evidence. |
| `8e4014bc50c8691f9d16a5be`, Zaporizhzhia | `zabor.zp.ua` | `GOOGLE_RPC_TARGET_NOT_ALLOWED` | Exact RPC destination NOT retained; weekly *oblast-wide* figure (approx. 60), not Zaporizhzhia city event | Keep `NEEDS_REVIEW`; no event attribution from title. |
| `93607059f26871023b56195f`, Odesa | `suspilne.media` | `HTTP_STATUS_403` | Publisher fetch returned 403; underlying cause, exact final path and redirect chain unknown | `SOURCE_ACCESS_BLOCKED`; do not use headline alone. Earlier #57 direct Suspilne Odesa page was reachable but matching this candidate to the exact same page is unproven. |
| `5e46ae290e43745fc4b827fa`, Kharkiv | `suspilne.media` | `HTTP_STATUS_403` | Publisher fetch returned 403; underlying cause, exact final path and redirect chain unknown | `SOURCE_ACCESS_BLOCKED`; weekly Kharkiv **and oblast** aggregation needs individual city/event breakdown. |

## Code boundaries

1. New `casualty_transport_policy.py` supplies the bounded technical HTTPS/host gate. Host set is **identical** to the existing previous allowed set. No proposed publisher was approved for live capture.
2. Existing `casualty_evidence_capture.py` imports the transport gate without importing `ALLOWED_HOSTS` from reviewer. Its Google RPC rejection now retains only sanitized `resolved_host`, `transport_reason`, SHA-256 of final URL, and the existing stable error code. HTTP failure also records `resolved_host`, final URL SHA-256 and redirect count, without any raw path/query/HTML.
3. Existing `casualty_auto_review.py` remains byte-identical. Separate reviewer host policy, underlying official attribution, civilian status categories and duplicate safeguards are unchanged. Successful technical fetch must **not** be interpreted as trustworthy death evidence. Unknown source facts remain outside accepted evidence or `NEEDS_REVIEW`.
4. No added alias/subdomain/wildcard, private IP, non-HTTPS, unsafe redirect, request-size/time/budget, resolver behavior or publisher-block bypass. No RSS headline accepted as an article-body proof.

## Minimal next acceptance gate (NOT authorized here)

Run **only the same five pinned RSS URLs once**, after separate owner authorization, with an explicit five-candidate and request-budget ceiling. Capture safe final DNS hostname + SHA256 URL (no raw URL path/query in failure logs), HTTP status, redirect count; retain existing excerpt/body hashes and original publisher metadata. Compare resolved host with RSS homepage **without assuming equality**. Allowing new fetch hosts needs its own review of exact final HTTPS domain, ownership/legitimacy, SSRF protections and no open-redirect chain; reviewer credibility remains independent. For HTTP 403: stop, retain `SOURCE_ACCESS_BLOCKED`, and prefer already recorded accessible official publication or openly available alternative article with full factual and origin attribution; no CAPTCHA/login/paywall circumvention.

**Success criterion of the next live test:** all five have verified destination-host diagnostics; at least one new publisher article body yields a complete, attributed usable evidence package, while 403/unknown hosts remain fail-closed, unchanged reviewer produces no unsupported proposal, replay adds zero duplicate deaths, and all operational input hashes remain unchanged. A zero-evidence result is BLOCKED, not PASS.

**Remaining blocker:** the five real publisher bodies were not captured and full 23-city coverage is still unproven. Research/offline policy validation does not authorize live enablement.
