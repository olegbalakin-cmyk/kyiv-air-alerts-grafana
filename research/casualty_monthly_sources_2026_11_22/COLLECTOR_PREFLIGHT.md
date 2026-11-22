# Monthly 23-city casualty-source capture: research-only preflight

Checkpoint: `CASUALTY-MONTHLY-COLLECTOR-OFFLINE-CI-PASS-2026-11-22-01`  
Status: **OFFLINE PASS / PUBLISHER GET=0 / MANUAL NETWORK GO NOT ISSUED / PROMOTE OFF**

## Exact technical design

* Existing default-branch manual workflow path: `.github/workflows/test-explosion-monitor-wip.yml`. `main` is a registration-only fail-closed stub and does not host the network runner. A separate version of the same workflow exists only on `research-casualty-monthly-collector-2026-11-22`.
* Branch **push** runs only `monthly_offline`; manual capture requires **all**: `workflow_dispatch`, exact research ref, approved exact HEAD SHA, owner actor/triggering actor `olegbalakin-cmyk`, attempt 1, `article_go=OWNER_APPROVED_ONE_SHOT`, fresh canonical grant SHA-256, the exact `owner_go_id`, and 24-hour-or-less expiry.
* The grant must specify the **byte SHA-256 of the committed `approved_sources_manifest.json`** and `get_budget=27` for its 27 exact URLs (never the looser ceiling of 50). The previously given **up-to-50 GET audit authorization is not a complete execution grant**: do not infer an approved exact head, grant digest or expiry. Separate explicit owner confirmation required before physical collector GET.
* Atomic `POST /repos/.../git/refs` creates `refs/tags/casualty-monthly-go-consumed/<go_id>` BEFORE first publisher request. The manual job alone gets `contents:write` for the tag; offline job is read-only; no Git checkout credentials persist. Replay, rerun or uncertain tag-create failure aborts before publisher GET.
* Each request: exact HTTPS domain/URL allowlist, public DNS IP validation and pinned socket with TLS hostname verification; no redirect, retry, cookie, browser proxy or authentication; **2 MiB raw and decompressed limits**, 8 s connect and 20 s total timeout; one attempt per URL, at most 27 attempts, and response URL/type/status/content hash are included in the proof. A failed publisher response is a candidate failure, not a positive source fact.
* Input sources may be wrong, stale or return redirects; success of the CI test **does not** mean they are live/parseable. PDF reports get hash-only receipts, not extracted text; HTML gets bounded 150-character context. This is **not** event identity, dedup or a casualty revision.
* Output in isolated `/tmp/casualty-monthly-oneshot` only; `capture_report.json` and `sha256_manifest.json` uploaded as a 30-day review-only Actions artifact, with no full publisher text/HTML/PDF. On an individual failure, continue to next URL but never retry same URL; the report distinguishes 200 versus failed. No source GET on offline or default-OFF execution.
* Explicit run invariants: `automatic_credits=0`, `production_writes=0`, `wip_writes=0`, `promotion=OFF`. No writes to `site-prod`, Netlify, Neon, or casualty data. The already-locked production deploy policy stays unchanged.

## Physical offline tests

- [Run #45046656778](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45046656778): **FAIL** in overly strict test asserting even a tiny allowed evidence excerpt was absent; code intentionally saves a short context. No publisher GET, network job SKIPPED.
- [Run #45046702280](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45046702280): **SUCCESS**, 12/12 offline tests after clarifying the evidence-excerpt assertion. No network.
- [Run #45046713958](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45046713958): **SUCCESS** on `a6915b047fdf2f0982a8f4afaf2c7f30dfd2f86d`, same 12/12; manual job SKIPPED, only tag-permission gate adjusted. This proves offline tests, not source capture.

The tests cover manifest and exact-scoped grant, expiration, head and actor, trigger and rerun, atomic tag-spend replay, unsafe URLs, private-IP DNS answers, no capture without approval, mock 27/27 source receipts, bounded snippets, PDF hash-only, network failure no retry, and zero credits. Mock responses are synthetic, not real publisher evidence.

## Next gate (requires separate owner-approved one-shot)

1. Check current research branch commit, exact URL manifest hash, Actions test success, permissions for one-shot tag, and PR file diff against parent; no new unreviewed changes or tests since pinning.
2. Produce a **fresh** (expiry <=24 h) grant containing `owner_go_id`, `approved_head`, `source_manifest_sha256`, `get_budget:27`, `allowed_methods:["GET"]`, `expires_at`. Compute SHA256 of canonical JSON: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`. Do not assume the dated manifest ID is already approved for live execution.
3. Present exact grant JSON and SHA-256 to owner; obtain explicit GO to spend one-time tag and fetch 27 URLs. Do not do this solely because earlier <=50 GET audit was authorized. Only then ask owner to run the existing manual workflow on the **research** branch; the default `OFF` must remain selected until GO.
4. Verify Actions exact job and tag, attempt count, per-URL HTTP status, redirect/invalid-type failures, body/hash receipts and any redacted fragments; mark evidence quality and missing cities without turning UNKNOWN into zero.
5. Separately reconcile verified **city + aerial attack** figures, attack-month attribution, existing baseline credits, dedup and late deaths, before proposing site changes. A new owner release GO is required. No auto PROMOTE.

Never merge this workflow or pilot script to `main` or `site-prod` as part of this research preparation.
