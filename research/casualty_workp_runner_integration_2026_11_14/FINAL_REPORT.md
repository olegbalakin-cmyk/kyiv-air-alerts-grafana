# WORK P — controlled runner / Work O integration

**Scope:** research-only; OFFLINE ONLY. No new owner authorization; no source/police HTTP; no merge, deployment, casualty JSON, WIP, C2, Neon, PROMOTE or publication.

- Exact Work O starting commit: `ff66bc6fbc9ae90bd4dfdb223821146a52b40a5f`.
- Work P branch: `research-casualty-workp-worko-runner-2026-11-14`.
- Draft PR: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/132 (target: Work O research branch).
- Final prelaunch HEAD: use **this branch's exact final HEAD after this report commit**, independently confirm exact-head CI and ZIP before any approval. This report itself is **not** an authorization.

## Verified implementation pins

| Runtime module | Previous runner Git blob SHA | Work O pinned Git blob SHA |
| --- | --- | --- |
| `research/casualty_evidence_ingestion_2026_11_13/ingest.py` | `a1af3457e0edbc23e3d23059a0256aebce10a2f5` | `86bc17b1112da1027fca4f0317534c322329b04f` |
| `kyiv-air-alerts-grafana/scripts/casualty_auto_review.py` | `19d0ed3911b62b7abc02700bd9f9a431e1d442e0` | `76518b35009615b5c29a4455bf0b9c3a3933cab7` |

The runner now rejects a mismatched Git tree blob, mismatched actual working file, or wrong loaded module path as `PINNED_SOURCE_BLOB_DRIFT`. Unchanged reference capture plan pin: `2f45d15b0e79cb11bf8ab605e314436dc0d3ed7c`. Immutable Work K provenance pin `69e7d023b4104c3583943eaf59f38b1d05ee32e5` and Work M ancestor `657fd70564bf5393d3fcd209e47d95fa986f3010` are unchanged.

## Integrated runtime route and safety boundary

In a future *separately authorized* launch, `run_capture.main` checks scope and signed-off one-shot identity, invokes `e.controlled_capture`, which calls the Work O `e._capture_once` HTML extractor; volatile text is passed into `run_capture.retain_results`, which calls `e.minimal_capture_facts` and the Work O-backed `e.extract_cached_reports`, then writes the safe research-only `minimal_capture_facts.json`, `fact_preview_unverified.json`, receipts, summary and digest manifest. The Work O parser functions come from `casualty_auto_review.py`.

Synthetic in-memory HTTP 200 and actual `_capture_once` extraction verify main-over-short-article and nav/aside skipping; word-number 2/3; 2-to-3 without additive 5; <=170 character snippets; privacy reasons; unknown count/date; independent police claim; `NEEDS_REVIEW`; 0 automatic credits; no full source in JSON; and manifest hashes. A source quote never constitutes a verified incident or cumulative correction on its own. Tests verify exact loaded blobs and deliberate tamper rejection. Historical tests remain; the one old Work K assertion for word-numeral omission now checks Work O's intended safe retention, not removal.

The original Work N pre-HTTP wrapper temporarily moves **synthetic** launch JSON out for both tests requiring launch absence, restores bytes exactly, checks the Git worktree, and must pass before a future capture can start. The live workflow still triggers **only** an exact-branch, launch.json-only push; no PR, dispatch or schedule trigger. `launch.json` was absent in Work O tree and historical changes through that base; Work P adds none.

Historical 18→20→23 evidence/generator regression remains run by both existing offline workflows. Five evidence-empty clusters stay blocked. The exact Work O code and historical frozen checkout are separate test groups.

## HTTP contract frozen, **not executed**

Exactly T03/T04/T05 in `research/casualty_one_time_capture_2026_11_13/capture_plan.json`, 3 initial GET maximum, 6 GET including exact owner-allowlisted redirects, 0 preapproved redirects, >=1s between requests, <=1,000,000 response bytes, 15s timeout, 0 retries, one execution, consent at most 24h. Outputs strictly fail-closed, no automatic source linkage or casualty credit, no production publish. No original article HTML or full source text persisted. Real T03–T05 source behavior **not yet retested**.

## Verification and approval boundary

GitHub Actions `CASUALTY Work O parser and evidence offline proof` and `CASUALTY Work L offline launch-safety and evidence proof` are bound to the Work P research branch. Inspect exact final HEAD runs, attempts, test counts, manifests, artifacts and zip SHA-256 in PR before declaring PASS. Any failed validation means PARTIAL/BLOCKED and no request for live permission.

### Draft owner approval (NOT GRANTED)

I authorize **one** controlled source HTTP pilot, solely on the exact fully verified Work P research branch and prelaunch HEAD specified in the final CI-verified PR #132 record, and solely for these URLs:

- T03 https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
- T04 https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
- T05 https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

Only three initial GET, at most six total incl redirects, **no preapproved redirect URL**, at least one second apart, 1 MB maximum per response, 15s timeout, zero retries, one execution, no more than 24h between approval and expiry. Retain only hashes, HTML scope/length, candidate-sentence and rejection diagnostic counts and safe anonymous excerpts <=170 chars. Every record `NEEDS_REVIEW`; no automatic matching, casualty credit, PROMOTE, publication, production, WIP, C2 or Neon changes. New explicit owner approval and distinct authorization ID and window must be separately created **after** validation. This draft has no authorization effect.

**Coordination:** PR #71 and PR #117 intentionally untouched. PR #127–129 untouched.
