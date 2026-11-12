# CASUALTY-SAME-INCIDENT-DEDUP-2026-11-12

**Research decision: `DEDUP_FIX_PASS` for the tested, explicit-provenance contract only. Production publication remains `NO-GO`.**

Frozen production: `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22`.
Research-only branch: `research-casualty-same-incident-dedup-2026-11-12`; Draft PR #89.
Initial fully passing exact-HEAD physical test: [Actions #43200729249](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43200729249) at `c512181530dddaaeb9c1bbcd2eb9d2455854311a`.
Checks: **25 PASS, 0 FAIL**, including the actual pinned generator, controlled rollback, frontend function probe and all protected inputs.
Artifact: [#13934299630](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43200729249/artifacts/13934299630); ZIP SHA-256 `a257ccf5f05c1c59366cbe52f2dcae452ef47aab189e95b27d9ba1c1c76b693c`, 4630 bytes.
A separate final-HEAD workflow check is required after this documentation commit, and its run ID/digest must be pinned in the PR conversation.

## Root cause and code changes

`load_revisions()` enforced uniqueness only for `record_id`. For the same incident with a new `record_id`, `apply_city_revision_overlay()` incremented month deaths again without tracking cumulative official totals or already-credited deaths.

Smallest scoped fix in `kyiv-air-alerts-grafana/scripts/update_casualties.py`:
- Five **optional** new CSV input columns: `incident_id`, `count_kind`, `baseline_credited`, `identity_proof`, `credited_proof`; existing column names and all outgoing JSON structures remain unchanged.
- Require explicit canonical incident identity and immutable evidence handles, distinguish cumulative count from verified delta, group confirmed same-event reports, and take the latest non-decreasing cumulative total minus evidence-backed baseline credit.
- Reject missing/ambiguous incident identity or prior credit, conflicts, reused candidate or URL across different incidents, missing proof, and unverified baseline claims. Never infer event-level credit from monthly aggregates.
- Permit only the **exact pinned existing legacy Sumy +1** revision without new columns; new legacy-format confirmed rows fail closed.
- Keep the existing missing-month creation mechanism unchanged; no frontend or reviewer changes.

The proof URI or digest format is a **traceability handle**, not automated confirmation that the referenced evidence actually proves identity or credited amount. A human must verify that link before entering confirmed revisions. A genuine historical baseline credit without incident-level evidence remains blocked, not guessed.

## Physical test results

| Test | Result |
|---|---|
| Pinned control source parity | PASS |
| 0 credited → cumulative 23 | +23 PASS |
| 18 credited through confirmed same-event revision → 23 | +5 PASS |
| 23 credited through confirmed same-event revision → 23 | +0 PASS |
| 18 → 20 → 23 cumulative snapshots | total 23 PASS |
| Downward correction | fail-closed PASS |
| Independent same-day attacks (23+7) | 30 PASS |
| Reused candidate across different incident IDs | fail-closed PASS |
| Missing incident identity | fail-closed PASS |
| Missing prior-credit provenance | fail-closed PASS |
| Baseline credit 18 in a month with no baseline deaths | fail-closed PASS |
| Missing immutable identity proof | fail-closed PASS |
| Duplicate record_id | rejected PASS |
| Ambiguous multiple incremental records | fail-closed PASS |
| Re-run same input | idempotent PASS |
| Rollback to pinned original input | exact semantic baseline PASS |
| Sumy existing +1 | unchanged PASS |
| Other 22 cities / pre-October months | unchanged PASS |
| Protected SHA-256 inputs | unchanged PASS |
| Original frontend chart function in Node | PASS |
| October created / Zaporizhzhia 316→339 | PASS |
| Full suite | **25/25 PASS** |

The artifact includes `checks.json`, `scenarios.json`, `input_sha256.json`, `control_summary.json`, generated `FINAL_REPORT.md`, and `SHA256SUMS`. Physical generator execution uses immutable original data copied to temporary directories. No media HTTP, changes to main/site-prod/WIP, merge, deploy, Neon or publication.

## Remaining boundary

The protected monthly source does not itself establish incident-by-incident historical credit. New revisions therefore need independently documented incident identity, credited count, and source provenance before being accepted. This is intentional fail-closed behavior; no claim is made that old baseline data has been retrospectively reconstructed.

Separate Work B checkpoint: October 2026 coverage remains incomplete. This dedup PASS is **not** permission to publish the Zaporizhzhia +23 revision or any October total.
