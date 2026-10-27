# C2 minimal release hardening — owner review (research only)

## Bounded inputs and prohibition
- Coordination `main@5fea9614313c2ad1b2332604c38a176575b5e559`, workflow blob `c34eda91540cd144142b58058012def45a0d6271`.
- Current `site-prod@056668981b59194d95386eac4c236f569ffffe17`.
- Research predecessor `935fc6b6684f879750cba8b881a7f61a42e1b291`, last accepted 12/12 CI `40491183020`.
- This is a research-only branch based on site-prod lineage and MUST NOT be merged into main wholesale. Neither main nor site-prod has been modified. No Neon production connection, deployment, schedule or secret change.

## Exact proposed selective release
- **main**, only `.github/workflows/update-netlify-site.yml`: candidate file on THIS branch, a selective replacement of the current main workflow only, not of the site-prod workflow; defer the early UkraineAlarm checkpoint Git push to the final publication stage; retain the existing checkpoint validation, site QA, 23-city validation and separate Phase-1 fail-open policy; add C2 fail-closed receipt gate; capture exact output digest; Git fetch/rebase and verify bridge and output bytes; after push (or no-op) compare actual remote against expected local staged/index outputs, then only report success on an exact match with a stable remote head; bound retries to three and fail explicitly otherwise.
- **site-prod**, selective replacements/additions ONLY:
  - `kyiv-air-alerts-grafana/scripts/multicity_canonical_shadow.py` (fail-closed writer receipt)
  - `kyiv-air-alerts-grafana/scripts/multicity_canonical_postgres.py` (advisory-lock + conflict-aware idempotent parent persistence)
  - `kyiv-air-alerts-grafana/scripts/verify_multicity_canonical_receipt.py` (new gate)
  - `kyiv-air-alerts-grafana/scripts/verify_c2_publication_snapshot.py` (new digest gate)
  - `kyiv-air-alerts-grafana/tests/test_multicity_c2_fail_closed.py`
  - `kyiv-air-alerts-grafana/tests/test_multicity_c2_release_stage.py`
  - `kyiv-air-alerts-grafana/tests/test_multicity_c2_final_blockers.py`
  - `kyiv-air-alerts-grafana/tests/test_multicity_c2_owner_release.py`
- Isolated research CI `.github/workflows/c2-pg18-concurrency-git-race-offline.yml` is NOT a production promotion.
- Diagnostic-only `verify_c2_release_dataset.py`, unrelated research, C3/C4, WIP, casualty, backfill files MUST NOT be promoted.

## Publication reconciliation contract
- A successful DB receipt is necessary, not proof of Git publication.
- Verify expected bytes of the 23-city QA output, all `data/` and `grafana/dashboard.json` before and after any rebase.
- Compare expected indexed content with freshly fetched remote; additionally query remote head with `git ls-remote`. Remote verified => success even if prior push acknowledgement was lost. If local has no changes and remote differs => explicit failure, not a false published receipt. If local has changes => bounded retry with fetch/rebase and re-verification or fail closed. Git and DB are non-atomic; divergence can temporarily remain after an aborted run.

## Phase-1 overlap
- The production C2 update job on main checks out site-prod and includes `PHASE1_DB_SHADOW=0` for `apply_ukrainealarm_bridge.py`, followed by C2 after the bridge step. The separate `main:update.yml` scheduled job is temporarily guarded to only execute on manual dispatch, and does not implement this C2 DB path. Existing Phase-1 write routines have distinct advisory keys from C2, so a manually initiated Phase-1 process targeting overlapping episodes is not serialized and may abort; current scheduled overlap has not been demonstrated. Do not rewrite Phase-1 as a C2 release prerequisite.

## Owner must choose site availability policy
- **Option 1 (candidate, NOT owner approved):** C2 Neon failure stops all publication. Accurate canonical status; site can remain stale while Neon is unavailable even though site data currently comes from files.
- **Option 2 (recommended for current shadow-stage):** permit controlled site-data publication with a **separate, explicit canonical-persistence FAILED status** and never emit a successful canonical receipt. Preserves availability while preventing false positive DB success. This requires a deliberately distinct publication gate/implementation and owner permission; do not silently deploy the fail-closed workflow as if option 2 were implemented.
- Owner approval is still required before promotion. No production deploy authorized.

## Remaining risk and boundary
- The no-op path intentionally fails on remote divergence rather than rewriting ambiguous remote state. Git/DB cross-system atomicity remains impossible. Concurrent manual or external writers with distinct locks are not guaranteed to complete successfully, though C2 independently verifies conflicts. One-time staged PG18 Git proof is NOT a real first live production cycle. If any deployment is authorized, queue after a scheduled data-collection cycle, then separately verify first live receipt/QA/publication.
