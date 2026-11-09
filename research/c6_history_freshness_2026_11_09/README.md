# C6-HISTORICAL-FRESHNESS-BINDING-01

Research checkpoint, 2026-11-09. **BLOCKED; GLOBAL_CUTOVER=NO.**
Main coordination was read first; its latest accepted checkpoint remains
C6-UA-CURRENT-ONEGET-01. This result does not update that accepted state.

## Result

| Evidence | Bound historical source checkpoints | Passing 36h gate |
| --- | ---: | ---: |
| C2 export 42297035421 → physical readback 42487688608 | 21/23 | 0/23 |
| Later bridge diagnostic 42452793451 | 21/21 continuity, different corpus | Cannot attach to the older readback |

The original bundle contains per-city bridge `last_checked_at` and
`history_reaches_previous_poll`. Its manifest hashes the dashboard, C2 receipt
and payload. Recomputed C2 corpus SHA and the readback receipt SHA match.
The physical artifact digest was verified against GitHub's retained artifact.
At its readback time, those source checkpoints were **40.12–40.51 hours old**.
A current offline revalidation also rejects them. An inherited dashboard
`effective_freshness.fresh=true` is ignored.

Kyiv and Sevastopol have no equivalent independent capture timestamp/hash plus
history-overlap checkpoint in this same-run bundle. Their last event dates,
JSON generation times and DB commit times cannot fill that gap. Earlier
isolated-child captures do not bind this parent-branch corpus.

## Patch

The existing receipt orchestrator accepts optional `--history-bundle` and
`--history-bundle-sha256`. The digest must come from a trusted retained export.
It reuses the current production receipt verifier, snapshot/C2-row checks and
existing bundle verifier. The new freshness component binds source metadata to
corpus SHA, workflow/input SHA, GitHub run/attempt, canonical run, branch and the
exact readback metadata/table fingerprints. It recomputes source age and stops
before generation on missing coverage/provenance, stale captures or mismatch.
Blocked attempts retain diagnostic reports and no candidate directory.

The existing generator receives historical source fields and a binding digest.
Its current/live certification fields remain separate. Historical readiness
does not require a live-alert feature. The default path and six-file JSON
contract remain unchanged; publication authority remains false in every mode.

## Missing links

1. For the later corpus `2c65be15…` / input `fc56e2d5…`, retain its exact
   same-run payload/dashboard/receipt metadata and matching readback.
   The older physical proof binds `f8d29705…` / input `f60214c6…`.
2. At the existing Kyiv and Sevastopol request sites, retain independent
   capture/checkpoint receipts in the same hashed source report:
   source identity/hash, `last_checked_at`, previous checkpoint, and completed
   history reaching that checkpoint. The patch accepts these as optional
   `multicity_meta.historical_source_receipts`; existing data has none.
3. Feed these receipts through the existing regular collector/writer/export
   and readback under a separate integration scope, within 36 hours.
   No additional collector, writer, scheduler or source request is introduced.

## Validation and scope

**35 offline tests PASS:** 17 new binding/gate/orchestration checks and
18 existing receipt/JSON contract checks. New tests block outbound sockets;
orchestration tests stub the expensive frontend builder. No full generator,
physical proof, C2 export, browser, historical audit or DST tests were rerun.

[Machine checkpoint](checkpoint.json) records exact identities, hashes and all
23 city verdicts. No new source HTTP, Neon SQL/write/DDL or deployment.
DST files, PRs #42/#44/#45 and root coordination documents are unchanged.
No physical owner action is needed for this research result.
