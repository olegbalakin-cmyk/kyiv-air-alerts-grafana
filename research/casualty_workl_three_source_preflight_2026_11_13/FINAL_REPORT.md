# WORK L — THREE-SOURCE LIVE PILOT PREPARATION (OFFLINE ONLY)

**Verdict:** PARTIAL until exact-HEAD GitHub Actions offline proof succeeds and artifact is inspected. No HTTP consent is currently in force.

## Recovered source of truth
Read main PROJECT_STATE.md and CHANGELOG.md (2026-11-11 roots) and newer coordination PR #71, PR #117, and Work K/J/I/G proof descriptions. The latter are separate unmerged research checkpoints; no change to them is proposed.

Work K PR #122 exact HEAD `69e7d023b4104c3583943eaf59f38b1d05ee32e5`, GitHub Actions #43439055939 SUCCESS attempt 1 at same SHA, 59/59 + 10/10 offline PASS, artifact #14044811680, GitHub-reported ZIP SHA-256 `369c98cce533fe7e4fac0032d9f80b48b0c03cd86da578bce8f6bac2cfcbc766`. This is an existing proof, not a live T03–T05 capture.

## Scope
T03 Ukrinform: `https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html`

T04 MIG: `https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/`

T05 Zaporizhzhia police: `https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv`

Exactly these three initial URLs. Zero approved redirect URLs. Domains: ukrinform.ua, mig.com.ua, zp.npu.gov.ua. Overall max 6 GET including approved redirects, >=1 s spacing, body max 1,000,000 bytes, timeout 15s, <=3 redirects per initial URL, retries 0, grant validity <=24 h, publication/PROMOTE forbidden.

## Minimal execution mechanism
A single special owner-approval launch.json-only commit on this research branch is required **after** a separately recorded approval. No launch.json exists in this PR. The live workflow is push path-filtered exclusively to that file on this dedicated branch; ordinary code pushes and PR events cannot invoke it. The existing Work K runner validates scope, pinning, owner approval window and prior commit; Work L adds exact T03–T05 URL/limits/redirect comparison, owner GitHub actor, immutable HEAD+parent, launch.json-only commit, no previous launch in branch history and first Actions attempt only. Every fail-closed gate runs before the first source GET. Workflow runs under an exclusive concurrency group. A re-run attempt >1 cannot execute the source step. Do not use an earlier PR #118 authorization ID.

Caveat: GitHub Actions workflow availability/activation on a non-default research branch may require a separately authorized administrator action; this PR does **not** enable an active launch by itself. A valid commit must be made by the intended GitHub actor with a fresh owner grant; commit identity and approval text are separate checks, not cryptographic proof of the human's consent. The owner must verify the commit and approval record before permitting it.

## Output and fact retention
The original Work K `run_capture.py` remains the only runner. It invokes unchanged Work J `minimal_capture_facts()` and Work E/I CONTROLLED_CAPTURE. On a permitted live run it will generate `capture_receipts.json`, `minimal_capture_facts.json`, `fact_preview_unverified.json`, `summary.json`, and `manifest.json` with SHA-256 hashes of the four data files.

Evidence cards retain URL, claim origin, claimed dead, total kind, short excerpts and reasons, original response digest and fail-closed NEEDS_REVIEW. Work L removes unsafe short excerpts in full when names, addresses or contact details might be present and adds `PRIVACY_REVIEW_EXCERPT_WITHHELD`. The source-body hashes remain but source bodies never go to the artifact. It also omits transport page titles and raw candidate parser-rejection data to avoid unnecessary personal details. Excerpt length stays <=170 characters.

Synthetic facts T03=2, T04=3, police T05=3 remain **three independent unverified cards**, never 5, never three additional deaths. The official source is not automatically linked to the publisher claims. Prior credited deaths and event identity remain unverified; zero automatic credits and no PROMOTE. Live texts may parse differently from synthetic inputs.

## Physical offline proof
The branch's offline workflow uses the retained Work E/G/I/J/K tests and synthetic three-card artifact, plus Work L launch-gate tests, hash verification, and retained original 18→20→23 generator regression. No external media or police request is permitted in this workflow. CI run, exact head, artifact ID and ZIP hash must be appended as a post-run PR description or comment, not presumed before execution. The CI artifact is research only.

## Prepared owner approval text (NOT YET GRANTED)
> I explicitly authorize **one** research-only HTTP pilot for T03 (Ukrinform), T04 (MIG), and T05 (Zaporizhzhia police), using the three exact URLs above and no others. Total GETs <=6 including redirects, approved redirect URLs empty (stop instead of following an unknown URL), >=1 second between requests, max 1,000,000 bytes per response, 15-second timeout, <=3 individually approved redirects per URL (currently none), zero retries, one execution, validity <=24 hours. I approve only the reviewed Work L exact HEAD and a subsequent launch.json-only commit on branch `research-casualty-workl-three-source-preflight-2026-11-13` with new unique authorization ID [OWNER MUST PROVIDE], approval time [UTC], expiration [UTC], and previous reviewed commit SHA [EXACT SHA AFTER OFFLINE CI]. No article bodies in artifact, no publication, PROMOTE, casualty JSON, WIP, production, C2, Neon, deployment or merge. Re-run is forbidden. This approval takes effect only after I send an explicit follow-up message supplying these values.

**This draft is informational, not authorization.** A later owner instruction must provide the new ID, UTC window, exact reviewed previous SHA and written consent. The unused launch shape must match the Work L validation fields; do not commit any fake or placeholder launch.json.

## Remaining gates
1. Exact-head Actions SUCCESS and synthetic artifact SHA / inner hashes.
2. Separate explicit owner consent with new ID, precise window, branch/HEAD and scope.
3. Verify that the special trigger is available to the repository only under approved administration, and the GitHub actor matches the grant.
4. Live text/safe quote and single-event attribution cannot be proven before a separately permitted source capture. If privacy-safe quoting is not possible, retain no quote and mark NEEDS_REVIEW.

**Even an offline preflight PASS does not authorize live HTTP.**
