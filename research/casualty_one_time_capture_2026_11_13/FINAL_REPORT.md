# WORK K — THREE SOURCE RUNNER (OFFLINE ONLY)

**Base:** Work J PR #121 at `a92e2ddb42060a77be966135c7fc0db9cca71c54`. **Branch:** `research-casualty-workk-three-source-runner-2026-11-13`. Research-only; no merge, publication, WIP, C2, Neon or source HTTP.

## Confirmed gap and change

PR #118 live attempt [#43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) retrieved 10/10 originals and stored only transport receipts, **zero structured reports and zero short factual evidence**. Work J [PR #121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/121), [Actions #43433677112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43433677112) implemented and tested `minimal_capture_facts(original, queue)`, but the old standalone runner did not call it.

This isolated Work K branch imports the *narrow* PR #118 runner code (without execution workflow or used authorization), pins Work J implementation, directly invokes the unchanged Work J `minimal_capture_facts()` after existing Work E/I `controlled_capture()`, and writes `minimal_capture_facts.json`, `capture_receipts.json`, `fact_preview_unverified.json`, `summary.json` and SHA-256 `manifest.json` to an ephemeral output directory. Parser diagnostics and reasons are retained. Publication and PROMOTE remain false. Missing evidence or document hash is marked for `NEEDS_REVIEW`; missing short excerpt has explicit `SHORT_EVIDENCE_NOT_EXTRACTED` reason.

The Work J format is unmodified; official police cards have an independent source role and null publisher candidate ID. Publisher citations of police do **not** become independent police originals. Full source text is never persisted. Work J excerpt length maximum remains 170 characters.

## Exact proposed T03–T05 source scope — NOT_AUTHORIZED

| ID | Source | Previous report, not current verification |
| --- | --- | --- |
| T03 | https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html | publisher; initial 2 |
| T04 | https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/ | publisher; later 3 |
| T05 | https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv | independent police original to examine |

`capture_plan.json` and `authorization_template.json` preserve **exactly 3 URLs**, max **6 HTTP requests total including permitted redirects**, minimum **1 second between requests**, **1 MB** response cap, **15 seconds** timeout, max **3 separately approved exact redirects per initial URL**, **zero retries**, max **24 hours** authorization, single run, default-deny all redirect paths, default-off capture, no publication or automatic PROMOTE. The authorization ID, timestamps and owner record are null. There is **no `launch.json`**, no active live workflow, and no automated source capture on branch push/PR.

**Source claims are separate and unconfirmed:** The October 22 attack identity and whether T03's 2 precedes T04's cumulative 3 require original text review. Never sum 2+3 into 5. T05's locality and precise event link must be verified separately. Any absence of evidence of prior credits keeps the proposal at `NEEDS_REVIEW`, never automatic PROMOTE or ledger increment.

## Offline physical proof

`.github/workflows/research-casualty-workk-three-source-offline.yml` repeats pinned Work E/G/I/J unit tests and retained Work J **18→20→23** actual-original generator proof. Work K adds 14 synthetic integration safety tests and a physical artifact generator writing 3 distinct mock evidence cards and a hash manifest. The test also verifies preflight without launch, changed-source drift, zero authorized publisher GET, rejection of wrong redirect/expired/reused consent, non-additive 2→3, report and card separation, and no source body persistence.

The physical workflow run and proof artifact must be independently checked. An offline PASS cannot establish that real T03/T04/T05 articles will parse, that they describe one event, that T05 confirms it, or that any new death count is owed.

## Owner consent required before a later real pilot

Owner must separately explicitly approve (1) exact T03, T04, T05 URLs only, (2) each precise permitted redirect URL or none, (3) aggregate 6 GET / 1 second / 1 MB / 15 seconds / 3 redirect / 0 retries / 24-hour / one-run bounds, (4) a **fresh unused** authorization ID and UTC window, (5) one approved live launch/action mechanism. A push or passing offline test is **not** such a grant. PR #118's consumed ID is forbidden. No HTTP request to T03/T04/T05 is authorized by this branch.

## Checkpoint

Provisional integration scope: `PARTIAL` until exact-head physical GitHub Actions succeeds, artifact content hashes are verified, and the synthetic report is checked. Following a successful proof only, use `THREE_SOURCE_RUNNER_OFFLINE_PASS`. No merge or coordination document changes.
