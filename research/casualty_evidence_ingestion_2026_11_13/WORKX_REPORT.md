# Work X — reliable retained source evidence (research only)

**Mode:** OFFLINE; no external source GET, no production publication, no WIP state mutation,
no C2/Neon, no casualty revisions/JSON, no PROMOTE or merge. This branch is not the
scheduled `main` workflow nor the operational WIP branch.

## Existing source and checkpoint contract

- `main:PROJECT_STATE.md` / `CHANGELOG.md` checked; track state in coordination
  Draft PR #71/#117, not root historical C6 checkpoint.
- Work P saved three source excerpts/receipts, NOT full publisher/official HTML.
  Work Q independently parses a local fatality 2, a later additional death
  (not total), and official 3, but cannot establish that all claims are the
  same event. Work R leaves T03–T05 unlinked.
- PR #140 Work V physical offline reviewer/operator → pinned actual generator
  proves **18 + 2 + 3 = 23**, replay +0. Does not authorize live credits.
- Main `.github/workflows/casualty-monitor-wip.yml` runs
  `45 */4 * * *`, checks out `multicity-wip-2026-09-16` and
  searches sources only for due completed-alert followups. The new research
  option does NOT enable a live workflow or new publisher requests.

## Minimal change and fail-closed proof boundary

1. Existing `monitor_casualty_candidates.py` gains
   `plan_source_scans(..., independent=True)`: all 23 city feeds are eligible
   even with no completed alert. After first scan, next search overlaps the
   last **successful** scan by 48 hours, with an 8-day RSS query bound.
   A failed/disabled scan never advances the cursor.
2. `--independent-source-check` selects independent source scans;
   `--source-http` is a **separate explicit research opt-in**. With no opt-in
   or `--local-only`, source HTTP is OFF. The scheduled live main/WIP
   workflow is unchanged. The path reuses the existing Google News RSS parser,
   filter, city configuration, state and queue, and never captures media pages.
   A recurring live 23-city source request requires a new owner decision.
3. The existing `run_capture.retain_results` receives a small
   `workx_review_index` from already redacted Work J/R cards. No additional
   parser or new fetcher: retained URL/source type, separate publication and
   attack dates (unverified unless source provides it), claimed place/time,
   count type, SHA-256 of response/extracted body/excerpts and short context
   tags; same-URL replay and change hints. The index cannot independently
   verify same attack identity, source attribution or prior credited deaths.
4. Same URL/body SHA = duplicate publication (zero credit); changed body =
   possible update, NEEDS_REVIEW. Different URL, same date/place/count/ages
   does **not** merge incidents. Added death requires an explicit verified
   prior event and baseline. A multi-attack article cannot assign one total
   to one event. Missing text, unsafe excerpt, contradiction or only HTTP200
   stays blocked. No AUTO_READY produced by this layer.
5. The existing Work O offline workflow is extended on this **single**
   research branch to run existing tests and Work X tests. Previous Work P
   archive and Work V artifact are downloaded from existing Actions (not
   sources), their inner SHA-256 manifests checked, and real saved results
   evaluated without reconstructing missing article text.

## Scenario-level acceptance contract

| Scenario | Evidence class | Expected outcome |
|---|---|---|
| 10 October 18→20→23 | Retained Work V actual pinned-generator proof | final 23, replay +0; no new credit |
| T03/T04/T05 | Work P saved short original excerpts, Work Q/R review | three NEEDS_REVIEW; zero automatic incident links |
| After 5 October hospital death | Work #102 research note; synthetic safety regression | NEEDS_REVIEW; no automatic new attack |
| Two attacks in same city/day | Synthetic offline safety regression only | remain distinct, no auto merge |
| Multi-attack article | Synthetic offline parser regression only | no death total assigned to single event |
| Repeated publication | Synthetic offline URL/body-SHA regression | no new credit |
| Missing text/conflicting claims | Saved Work Q excerpt diagnostics + synthetic failures | fail-closed |

**Proof limits:** the synthetic examples are contract tests, not fabricated real
historical event evidence. No full T03–T05 HTML is retained; the historical
attack identity therefore remains unresolved regardless of green CI.

## One possible owner-approved future physical source pilot (NOT AUTHORIZED)

Reuse *only* these three original URLs; the old single-use grant is spent:

1. T03: https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
2. T04: https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
3. T05: https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

At most 3 initial GETs / 6 total including strictly allowlisted redirects,
at least one second apart, 15 s timeout, one million bytes max per response,
zero retries, no follow-ups outside the allowlist, immediate stop on unsafe
redirect, changed grant/HEAD, budget overrun, data inconsistency or
privacy/source-body retention failure. Never treat an HTTP200 as factual proof.
Transient parse in memory; retain only short privacy-screened sentences (each
<=170 chars), tagged evidence and response/body/excerpt SHA-256, request
metadata and unresolved gates. No full article HTML, identities or addresses.
One separate, expiring exact-HEAD owner authorization needed before any GET.

Future live integration: after independent offline approval, explicitly update
the existing WIP scheduler invocation with the selected flags and rerun
continuity/idempotency guard against unchanged WIP state. **Not performed.**
