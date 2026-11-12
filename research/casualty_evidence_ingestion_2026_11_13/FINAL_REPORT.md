# WORK E — CASUALTY evidence ingestion research

Decision: EVIDENCE_INGESTION_OFFLINE_PASS for saved sources only. Autonomous regular collection remains PARTIAL and unauthorized.

## Sources and pins

Read main:PROJECT_STATE.md, main:CHANGELOG.md, and PR #71 accepted note. This Draft PR is stacked on PR #105 at 6a0100b0937218c62c5c079fd46e80e5071783cb. Frozen WIP is 43b580491d54d1df3bd84a0ae59a6987f8ea4d03; frozen site-prod generator is d0a7d22de2828c93236562cccc9d2e68c6a66e3d; PR #88 matrix is 34bc539d0c7abb8af4f699b2e2c9ecec4b668397.

Previously approved original article evidence JSON SHA-256: 84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df (Actions 43053796144); 10 Oct Zaporizhzhia original text SHA-256: 011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259. PR #102 receipts SHA-256: 4c21321b8a75d57f60efc97f581e89604eaa03289bb64bfba26e491ac83a203b (Actions 43261676781). Fourteen HTTP transport receipts contain no original publisher or official page body.

## Adapter and handoff

research/casualty_evidence_ingestion_2026_11_13/ingest.py defaults to OFFLINE_REPLAY, reuses the existing Work A anchored_articles and casualty_auto_review.extract_cached_reports, validates queue fingerprints and preserved text SHA, and produces fact cards plus work_a_reports.json. Each card includes original URL, source type, attack identity/date/weapon, source-attributed official origin, cumulative reported totals and selected final count, short de-identified excerpts, text SHA and report hash. No full copyrighted article body is committed or uploaded.

The one optional --ingested-reports argument in the existing research Work A pipeline recomputes facts from pinned saved originals and fails closed on any mismatch in computed reports, queue, source evidence and PR #102 receipt pins. Old behavior stays unchanged when the option is omitted. There is no new reviewer, monitoring system or publisher.

Expected real case: 10 October guided-bomb attack in Zaporizhzhia, one cumulative incident 18 -> 20 -> 23, never 61. Work A's original generator receives one safe proposed +23 update in isolated temporary copies, not production data.

Five PR #102 clusters representing eleven candidates have transport receipts but no saved factual texts. They MUST stay NEEDS_REVIEW. Reprints with identical original URL are not independent evidence; September baseline incident allocation remains unknown; alleged post-5-October hospital death needs an independently retained official confirmation. HTTP 200 is transport success only.

## Future HTTP authorization specification (NOT APPROVED)

CONTROLLED_CAPTURE exists but requires explicit CLI --mode CONTROLLED_CAPTURE --enable-controlled-capture and a new written exact-target authorization JSON (authorization ID, approval and expiry UTC, exact HTTPS URL paths and scoped candidate IDs, publisher or official role, allowlisted domain subset, request count/size/rate). The prior one-time PR #102 permission is exhausted.

Permitted domain ceiling, not permission: suspilne.media, zprz.city, ukrinform.ua, mig.com.ua, zabor.zp.ua, shelter.in.ua, radiosvoboda.org, interfax.com.ua, 1news.zp.ua, spravzhne.media, zp.npu.gov.ua. Authorize an exact subset of at most 14 URLs, 30 requests including redirects, at least one second between all requests, response body at most 1 MB, timeout 15 seconds, at most three redirected URLs (all checked again against the allowlist), no retries, no login, paywall, access-block bypass, CAPTCHA solve or JS rendering. HTTP status, full redirect chain, UTC capture timestamp, bytes, content type, response SHA-256 and failures are auditable. Full responses are ephemeral in-memory only; keep very short factual excerpts and hashes. Separate official reports are linked by provenance and attack identity, never by summing duplicate articles. Unavailable, contrary or unverified content returns NEEDS_REVIEW. No connection to C2 or any regular workflow, so capture is disabled by default.

Before an unattended rollout, another explicit owner authorization must approve publisher domains, storage retention, refresh cadence, official confirmations and baseline reconciliation. Repeated updates must keep one incident_id and cumulative kind, validate prior credited deaths, and never sum successive updates.

## Offline physical proof

Research-only workflow research-casualty-evidence-ingestion.yml is branch-push-only, read-only GitHub permissions, downloads approved GitHub Actions artifacts (not publisher URLs), checks hashes and frozen commits, runs synthetic negative safety tests, then executes real offline ingestion -> existing Work A -> pinned production generator -> strict real-source assertions. No WIP mutation, casualty JSON change, merge, deployment, C2, Neon or production source change. October stays COVERAGE_INCOMPLETE.

The offline replay can validate a single archived original text, not precision/recall over all candidates or live regular autonomous ingestion. Do not claim release readiness based on offline PASS.

## Exact-HEAD physical verification (2026-11-12 UTC)

A complete physical offline execution succeeded: [Actions #43320160202](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320160202), at tested head `ee1b252cd8dbd9bc325bcc3387249315f01f50b9`. Both source JSON pins matched; 10/10 safety tests passed. The physical verification printed `EVIDENCE_INGESTION_OFFLINE_PASS` after the exact site-prod generator test. Proof [artifact #13989688155](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320160202/artifacts/13989688155) has GitHub uploader digest SHA-256 `56dc0e9c0308c4dc6b074bf9819d2a229ffc102a81a336fd0a754be32670effc`; not independently rehashed.

Real replay: 1,682 candidates, three with original texts; two parsable reports, **one** accepted auto-ready case. The saved 10 October Zaporizhzhia article yielded **18 -> 20 -> 23** as one cumulative incident and one +23 generator-safe shadow proposal; five further PR #102 groups (eleven IDs) remained `NEEDS_REVIEW` with no factual article bodies. Work A summary was 1 AUTO_READY and 1,681 NEEDS_REVIEW. No HTTP to publishers, no production writes, and no merge/deployment. October COVERAGE_INCOMPLETE.

**Final bounded decision: EVIDENCE_INGESTION_OFFLINE_PASS.** Regular autonomous HTTP capture and scheduled source ingest remain **PARTIAL / NOT AUTHORIZED**. This proves processing of previously saved originals, not readiness of unattended coverage or independent verification of new official source pages. Future capture requires a separate owner approval and a further end-to-end live-capture review.
