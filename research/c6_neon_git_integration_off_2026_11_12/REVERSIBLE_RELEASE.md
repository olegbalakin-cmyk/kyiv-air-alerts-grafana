# C6/C3 minimum reversible release — NOT AUTHORIZED

Status: `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. This document is an offline procedure, **not** a certified operational rollback or an owner grant.

## Before any GO

1. Confirm fresh independent Work A readback for the **exact latest regular C2 run/attempt**, 23 historical source receipts, manifest and six SHA-256, historical freshness at the instant of consumption, source branch/corpus and no active-alert certification. PR #94's `publication_allowed=false` cannot itself grant production authority.
2. Pin current `site-prod` commit and six target Git paths (blob + SHA-256), the latest C2 source generation, all casualty/auxiliary JSON and Kyiv intervals. Save a *fresh Git-only* recoverable snapshot, not the old October Netlify deploy.
3. Pin an independently validated Git-only frontend + matching root static KPI package, the seven static asset digests, Netlify deployment ID, and exactly the equivalent dashboard generation; prove that the operator can restore an **inactive** previously deployed immutable package. Otherwise rollback stays BLOCKED.
4. Obtain owner authorization separately for code merges, a single controlled Netlify production deploy, exclusive one-shot Git publication, and rollback authority. Confirm the existing scheduled C2 Git-only writer is paused **without disabling casualty monitoring or C2 source capture unnecessarily**. Ensure only one process can write the five runtime paths.
5. Lock Netlify auto-production publication for the switch window. A new proof run alone must never enable a publisher.

## Release order (not executed)

1. Deploy the dual-compatible approved frontend with the **exact** approved root `historical-daily-kpi.json` as static Netlify asset; verify Netlify deploy ID and HTTP SHA. The Git-only frontend fallback must remain functional while the old Git runtime generation is active.
2. Re-check Work A freshness and the six-file SHA manifest. Verify the pinned Git-only backup remains recoverable.
3. Re-read current `site-prod` HEAD. Reject unexpected ancestry, changed data, casualty/auxiliary mismatches or interval loss. Publish exactly five runtime JSON plus the root KPI via one normal, fast-forward, allowlisted Git commit; never reset or force-push. Verify remote commit and served five SHA-256.
4. Verify source and generation alignment across Netlify static and Git runtime: 23 cities, CSV, Kyiv intervals, casualty and auxiliary continuity. No unsupported “alert now” claims. Resume **only** the authorized Neon publisher after success; do not resume regular Git-only C2 writes on those five paths.

## Rollback (not executed)

1. Stop Neon Git publisher and prevent Netlify auto-deploy from racing.
2. Reconcile any newer C2 observations, casualty, Kyiv intervals and auxiliary bytes against the current remote; **do not restore old JSON blindly**. Rebuild Git-only JSON from the existing collector and preserve all newer updates in an allowlisted fast-forward commit. Verify 23/23 and expected generation.
3. Restore the pinned *compatible Git-only* Netlify frontend/root static KPI package using the existing authorized Netlify mechanism. Test the inactive-deploy re-publish privilege **before relying on it**; current production deploy does not expose the needed permission.
4. Verify exact served static/Git SHA and matching generation, 23 city charts, CSV, casualty, auxiliary, and monitor continuity; only then resume one Git-only publisher. Keep Neon publisher OFF.
5. If any approval, grant, matched generation, inactive-deploy permission, proof artifact or expected remote SHA is missing, **BLOCK** rollback rather than risk a destructive reset.

## Evidence boundary

PR #95 initially provided only a detached local candidate; no live publisher. The experimental one-shot publisher module is not wired to an executable approved GitHub release job. Work A acceptance, Netlify operational restore authority and exact-head release validation remain outstanding. No CI-only proof constitutes a production rollback test.
