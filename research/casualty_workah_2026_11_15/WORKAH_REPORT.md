# CASUALTY — Work AH: guarded article executor, strict-offline only

**Scope:** Work AG's parser and Work AF's existing atomic GitHub GO mechanism, in a stacked research-only draft branch. No media HTTP authorized; PROMOTE OFF. No production workflow, schedule, WIP, revisions or dashboard data touched.

## Changes
- Existing `casualty_go_guard.ClaimedGo`: deep-copies the grant and consumes each approved URL **once**, before attempting HTTP; an exhausted per-kind budget is fail-closed.
- Existing Work AC retains numeric HTTP status in blocked capture reasons (e.g. `HTTP_STATUS_NOT_200_403`), without retries or redirected requests.
- Existing Work AG `article_oneshot.py`: explicitly restricts URLs to the saved Work X T03/T04/T05; requires HTTPS, exact owner dispatch/actor, exact branch, exact SHA, one run attempt, a canonical approved grant digest, expiry and one GitHub atomic spent-GO create-ref **before** the first publisher request. Older research runners are not given this new GO via the workflow.
- Existing `.github/workflows/test-explosion-monitor-wip.yml`: added the isolated `casualty_workah_offline` job on this research branch and a separate **manual only** `casualty_workah_one_shot` job. The latter cannot execute on push; it is gated by `workflow_dispatch`, owner actor, branch, run attempt 1 and explicit owner input `article_go=OWNER_APPROVED_ONE_SHOT`. No scheduled source fetch.

## Exact retained Work X article URL list

1. T03 Ukrinform: https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
2. T04 MIG: https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
3. T05 Zaporizhzhia Police: https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

Literal URL identity is locked in the guarded executor, not inferred from RSS. These are historical saved URLs; availability and actual article contents are unknown.

## Physical preflight contract

Run the strict-offline `test_workag.py` + `test_workah.py` suite in the existing research workflow. Mocked HTTP only; no real publishers. Tests include two simultaneous synthetic claims, replay rejection, rerun prevention, scope/head/digest/expiry mutation rejection, failed atomic GitHub ref creation, duplicate URL, extra request, transport metadata and response hash, HTTP 403, JS/empty body, numeric outcome, review-only index, SHA-256 proof without HTML, no WIP writes. Prior Work AF successfully tested **real GitHub atomic create-ref against two simultaneous requests**, distinct from Work AH's mocked concurrency test. Work AH does not claim a new independent real GitHub collision test.

The designated live job is **not activated** and no owner GO is granted by this PR. Claiming a GO is irreversible; therefore preflight uses mocks and does not consume a real owner grant.

## Proof output

`/tmp/workah/offline-article-proof.json`, `offline-blocked-proof.json`, `offline_proof.json` and `sha256_manifest.json` (all bounded). In the eventual real pilot only `/tmp/casualty_workah_article_proof.json` is uploaded; no full publisher HTML or body. HTTP, body and numeric stages are separately reported. Short excerpts, URL, response SHA, title, publication-time source, count kind, unverified attack date and review/dedup status are available where successfully extracted. An inaccessible source must remain blocked, not claimed as an absent fatality.

**Critical limitation:** Work X never automatically establishes cross-publisher incident identity. Matching city/date/count/victim ages is insufficient. All T03/T04/T05 remain `INSUFFICIENT_EVIDENCE` pending real source text and reviewer reconciliation. Live output has `automatic_credits=0`, `publication_allowed=false`, `promote=OFF`.

## Owner GO gate

Approve only an exact **final** research HEAD and canonical JSON grant digest, with a unique `owner_go_id`, short expiry, literal URL list above, zero RSS budget and three article GET attempts. No owner GO is implied by test success or this report. Workflow dispatch with explicit owner approval is required; branch push never calls the publishers. No global protection is claimed for old unrelated research workflows. This specific executor uses the shared spent-GO tag to prevent concurrent double consumption.

**Production:** main, site-prod, active WIP, casualty revisions/JSON, C2/Neon/Netlify and four-hour schedule remain untouched. This Draft PR must not be merged without a separate authorization.
