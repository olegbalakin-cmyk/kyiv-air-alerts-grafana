# Minimal C6 pre-cutover preparation

`GLOBAL_CUTOVER=NO`. This draft prepares an **isolated static source switch**;
it does not wire or enable production publication, a new writer or a scheduler.
Main coordination was read at `0546986e69f2bbd4d5507f80dada426775eb1489`.
PRs #42 and #44 are untouched. Main still records the older checkpoint; #44
separately proposes acceptance of the physical PASS. The updates on this branch
are proposals until reviewed, not an assertion that main has accepted them.

## What is ready

- Physical [run 42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608),
  research `38539e51`, artifact **13619973574**: 23 cities, four generated JSON
  plus two Git auxiliaries, **14/14** hashes independently checked. No repeat
  proof or generation. See [verified input evidence](evidence/verified_inputs.json).
- Existing scheduled [production run 42452793451](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42452793451)
  already committed C2 on `br-bold-mode-b5rub8pq`: 32,656 corpus episodes,
  34 inserted, 32,622 existing; independent classifier `NEON_SUCCEEDED`.
  Existing history diagnostic proves **21/21** bridge continuity through
  `2026-11-08T06:23:07.719975Z`. These are existing operations, not runs started here.
- The production frontend is unchanged between proof input `f60214c6` and
  observed `site-prod@ba2ebe2a`. CSV, link sharing, styles and rendering code
  are reused. Casualty JSON objects and both auxiliaries must remain equal to
  the **same-run built Git outputs**, not the earlier input checkout.
- Same-run Git and Neon Kyiv display sets both have **2,819 intervals**, with
  zero missing/extra UTC pairs. New staging refuses any mismatch. Cause JSON is
  copied byte-for-byte; classifications are not rebound.

## Actual cutover blockers and minimum changes

| Blocker | Concrete dependency | Minimum resolution |
| --- | --- | --- |
| Wrong historical intervals | The physical candidate's `projection_lineage.json` still includes the three known bad parent UUIDs for Kharkiv, Poltava and Zhytomyr. Cherkasy's missing interval remains covered by the accepted four-case evidence, not a new readback here. | Resolve exactly those four cases before publishing affected metrics; do not hide a city/date while claiming full 23-city history. Use the narrow plan below. |
| Historical source evidence is not bound to the Neon candidate | Existing C2 `_provenance()` declares `source_provenance_coverage=partial`; generator `source_report()` deliberately supplies no verified capture times. A successful DB write/build timestamp cannot replace source currency. Latest bridge receipt covers 21 cities, not independent Kyiv/Sevastopol source currency for this candidate. | Reuse existing same-run capture/checkpoint metadata; add per-city historical coverage/capture bindings to the existing corpus receipt and validate them on readback. No additional GET and no new writer. |
| Production wiring and promotion are not enabled | `app.js:RAW_DATA_BASE` points at GitHub `site-prod`; current Netlify build copies a separate `data.json`, which that app does not read. This PR stages a complete local `data/` route, not a deployment. | After the two data blockers pass, promote the accepted generator and source selector through a separate reviewed change; feed one complete six-file set into the existing Git publication, preserving the previous Git set. Require owner GO and the deployment-specific rollback gate. |

The regular collector and C2 writer **already exist**: production workflow
`15 */4 * * *` → existing builders/bridge → same-run canonical payload →
`multicity_canonical_shadow.py` → receipt classifier → Git QA/publication.
Do not create another poller or writer. GitHub schedule timing can drift; check
actual source timestamps, not the cron alone.

For this historical site, keep the current `reconcile_bridge_freshness.py`
**36-hour hard ceiling**, target the existing four-hour cadence, and require
completed-history coverage through the previous successful poll for each city.
Do not infer staleness from the date of the last alert in a quiet city.
Do not require a new live-status feature or all-clear/ancestor certification.
Inherited `effective_freshness.fresh` is not evidence: staging reports unproven
captures as blocked even if that old dashboard flag says true.

Minimum pending metadata patch, **not activated**: retain the existing
`ukrainealarm_bridge_fetch.json` per-city `last_checked_at` / `continuous` values;
emit equivalent metadata at the existing Kyiv and Sevastopol request sites;
bind the city metadata hash to C2 `corpus_sha256`, workflow/input SHA and run ID.
Extend the existing readback/source report to check that same binding and
recompute age. Keep the writer's identities and requests unchanged. Activating
this additional receipt persistence or running sources/writes needs owner scope.

## DST and Kyiv scope

Reuse `C6-DST-UTC-01@7265e40a`, the seven source witnesses at `741f277f`, and
the preflight branch's fixture/machine diff at `04b0938d`. No new historical audit.
The proposed writer repair is only UTC sort and both UTC comparisons in
`apply_ukrainealarm_bridge.py:union_alerts`; the current site-prod still uses
wall-time comparisons. The proof generator already uses UTC union, but cannot
split an incorrect physical parent back into its original source intervals.

Before any DML: one bounded read-only dependency check for the three exact old
UUIDs and the seven expected intervals; confirm current row values, legacy IDs,
FKs/triggers and lineage. Then prepare a conditional transaction that preserves
old identities, supersedes the three bad parents and creates six split rows plus
one Cherkasy row. Preserve valid Cherkasy UID
`ff046d6c-fc7e-4cd2-9470-3e5433c3d582`. Abort on drift or unknown dependencies.
Post-write verification, if later authorized: seven new intervals, three
superseded identities, no unrelated changes, **+4 episodes / −9,059,359,958 µs**;
reverse supersession from a before-image for rollback. No SQL write is run here.

For Kyiv, retain exact current same-run Git membership over exact Neon intervals
and the same-run cause auxiliary. The 28 unresolved classifications on suppressed
parents can be investigated **after cutover** while this frontend contract holds.
No automatic alias/classification reassignment is needed for this route.
Full current-status semantics, replacing Git auxiliaries with database features,
and removing the Git collection path can also wait.

## Reproduce this isolated preview

Use the already retained C2 bundle from run **42297035421**, artifact
**13543497560**, inner SHA-256
`2e56e3af58b28ddb9450930f201c5a81f41a39327a0da57a1d6c913f0981c501`.
Use the physical proof artifact above. No fresh export, generator or DB access.

```bash
python -m scripts.c6_json_source_preview \
  --site /path/to/pinned-site/kyiv-air-alerts-grafana \
  --bundle /path/to/existing-c2/c2-shadow-inputs.zip \
  --proof /path/to/physical-proof --source neon --output /tmp/c6-preview
```

`--source git` (or absent `C6_JSON_SOURCE`) is the default/OFF and the explicit
rollback. Rebuild at the same marked preview directory; the original inputs are
never overwritten. Invalid/missing proof, mismatched JSON/auxiliaries/Kyiv set,
unowned output or changed hashes stop before replacing the previous preview.
All outputs are permanently marked `publication_allowed=false`, with a visible
frozen-data banner and noindex. The preview command has no production mode.

The manual-only `c6-json-source-preview.yml` packages the same artifact without
secrets, source collection, DB access or deployment. It has **not been dispatched**
or registered in main. It may require separate workflow registration for GitHub's
UI; local reproduction works now. Expired input artifacts fail closed; never
silently manufacture a new export. The source selector tests use retained files,
block outbound sockets and do not repeat prior browser/CSV/PG17/parity proofs.

**Next owner step:** authorize only the bounded read-only four-case DST dependency
preflight using the established reader. This is not permission for data repair,
new source HTTP, new writes, production preview hosting or cutover. The marked
static preview and local source-switch rollback are already reviewable.

Validation: **11 new routing/rollback tests PASS**, with outbound sockets blocked;
JavaScript syntax checks PASS. [Dry-run result](evidence/dry-run.json) records the
Git → Neon → Git equality and preview ZIP digest.
[Download the frozen Neon preview](https://chatgpt.com/library?file_id=libfile_89e0f798f1708191871fb47043771705&account_id=bf2c5f82-0793-4d7d-91ed-e342d9a12e23), extract it, then
serve that directory with `python -m http.server 8000 --bind 127.0.0.1`.
The banner remains visible; the archive is an isolated artifact, not a deployment.
