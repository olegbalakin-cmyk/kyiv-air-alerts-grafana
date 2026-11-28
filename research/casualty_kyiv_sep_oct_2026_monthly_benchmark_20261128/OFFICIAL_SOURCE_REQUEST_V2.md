# #263 follow-up — official source request (NO EXECUTION)

**Request only; PROMOTE=OFF.** Supersedes the unexecuted #258 proposal, not a grant. Previous live GO is spent. No publisher contacted, no casualty credit or production writes.

## Scope and budget

Preserve all 12 official URL leads from #258 at `d8e280d9aaf220de67d91d3e4f32fb09058eadcd` and all 9 indexed references from #263 at `2aeb68435debf2bf3cacbfc67941b47b0893e6d3`. Exact URL deduplication merges two pairs (weekly Kyiv bulletin and police cumulative update), producing **19 distinct URLs: 17 local official sources and two UN monthly landing pages**, on five exact hosts. Every original reference remains attached to its one URL.

Manifest: `official_source_request_v2.json`. Exact SHA-256: `4e8e072316fdf64e7906e52470c896266b5be18388295d63f4af023daee55f91`. This digest is for the **request-only** JSON, not an executable manifest or authorization. No redirects, linked PDFs or additional URLs, retries or RSS. Proposed max one GET per URL, 19 total, sequential, HTTPS/public IP only, 15s, 2 MiB raw and decoded cap.

## Methodology comparison (provisional; source bodies not captured)

| Dimension | OHCHR monthly reference as recorded in #263 | Website rule and evidence requirement |
|---|---|---|
| Population and geography | Documented civilian fatalities; Kyiv city as stated in indexed reference | Civilian deaths inside Kyiv city administrative boundary; exclude oblast-only reports; verify each source's geography. |
| Causation | Conflict-related harm across weapon categories | Only deaths attributable to air attacks; prove causal link. |
| Time attribution | Exact assignment policy and late-revision cutoffs still to be checked in original methodology | Date of underlying incident, not report date; hold unresolved date and late-death cases. |
| Ascertainment | Documented minima, not an upper bound; coverage limitations and verification rules need primary review | Unknown days stay unknown; no zero or full-month certification from absence of reports. |
| Deduplication | Individual/event linkage and revisions not supplied by monthly headline alone | Reconcile local cumulative updates, baseline and confirmed revisions; never add monthly aggregate to incident records. |

Do not use benchmark minus candidate sum as a missing-person count, duplicate count, or release approval. Monthly benchmarks prioritize gaps; they are not air-only totals or certified coverage. Confirm original geographic definitions, dating, weapon breakdown and revision policy after capture. If linked PDF or additional methodology source is needed, report separately as unapproved; do not follow links automatically.

## Required handoff

1. Integrate exact 19-target request into existing research-only collector with #259 private full-body archive; no parallel pipeline. Its executable manifest schema differs. Preserve exact URL set and provenance; test fail-closed URL, DNS/IP, redirect, retry, budget, one-shot, key and replay checks, including UN content type.
2. Pin executable HEAD and SHA-256 of executable source manifest; prove exact same URL set and budget; verify private encryption key and archive retention. Current Draft #259 is not proof of deployed executable.
3. Only then request fresh explicit owner GO naming executable HEAD, manifest digest, budget, unique grant ID and expiry. Request ID is not a grant. No capture now.
4. For each returned document record exact URL, HTTP result, capture time, MIME, raw/decoded SHA-256 and encrypted receipt; independently verify methodology and local attribution, identity, civilian, cause and territory scope. Hold all candidate credit.
5. Re-pin site-prod and baseline/revisions blobs, reconcile duplicates and city-month coverage, then prepare separate release proposal. Separate owner release GO is mandatory.

## Tests

`python -m unittest discover -s research/casualty_kyiv_sep_oct_2026_monthly_benchmark_20261128 -p 'test_*.py' -v` (offline stdlib). Existing benchmark tests unchanged. Request tests are not collector or release tests.
