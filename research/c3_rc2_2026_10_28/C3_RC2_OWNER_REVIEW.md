# C3-RC2 OWNER REVIEW — PARTIAL (2026-10-28)

## Verdict
**PARTIAL — NOT RELEASE-READY.** No operational WIP/production/Neon changes, deployment or live workflows. Do not treat this research report or test source as a successful execution receipt.

## Exact preflight
Read current `main:PROJECT_STATE.md` and `main:CHANGELOG.md` before repository work.
At read time: `main@539f75d4dbb8c8043ae460432133c7b55ca6f69d`, `site-prod@a2d593c51830a62516d8907b6f55aae1b05e8948`, operational `multicity-wip-2026-09-16@08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d`.
Staged runtime `ff93eea396868b62c3cab2c332b551eb16ff5fd7`, owner review `fd3b91b34150906fa35ce38e53315860675f3b98`.
Original Actions `40733060266` SUCCESS at exact `ff93eea`; durable 47x10 accepted prior proof `38127425160` SUCCESS at `b1036d43`. No new C3-RC2 Actions success or PostgreSQL 16 execution is claimed.

## Research change and test execution limitations
Added `research/c3_rc2_2026_10_28/prove_23_city_regression.py`: offline replay harness invoking actual staged `poll_cached_bridge`, `process_events`, `due_checks`, and queue registration, and pinned pre-RC1 Python from `08c1a0a9`; checks all 23 city sets, exact vs raion-proxy family, dedicated Kyiv and Sevastopol sources, episode identity, source/state/due parity and queue obligation denominators. This test **has not been executed in PostgreSQL or GitHub Actions**. It requires `C3_RC2_FROZEN_DIR`, with exact frozen bridge/alerts/sevastopol JSON and `sha_manifest.json`, and a local Git checkout containing the pinned operational-WIP ref. The frozen WIP bridge in the prior research tree has 417 events and September 17 last-poll times, so it is NOT a complete current October post-cutoff 23-city replay. Merely replaying that bridge does not close the gate. Production bridge blob `debfdf0e7ad9ce8e1f59dc0c05b75f7533b39ffc` is 1,446,898 bytes; connector did not return content, therefore no fabricated October replay denominator.

## Concrete remaining blockers
1. Need execute real, currently pinned and validated post-cutoff 23-city offline source replay, with all 21 UkraineAlarm cities, Kyiv exact-city and Sevastopol verified pairs, including cached timestamp freshness, proxy union, source failures, due coverage and city denominators. Verify exact pre-RC1 result and cut-off journal obligations, not just configuration.
2. Need execute actual staged monitor.main() on disposable PostgreSQL 16 for two simultaneous workers, COMMIT-to-ACK loss, independent readback failure, source / classification / identity conflict, stale-tip CAS, restart after pruned state with legacy checked_at, and event-stage rollback. Collect committed classifications, current tips, sources and checkpoint counts after each restart/retry; retain canary <=10. Existing RC1 happy path does not prove these.
3. Hold is incomplete. main explosion-monitor-wip.yml monitor job has `if: ${{ false }}`; WIP workflow copy is not guarded. Main update-explosion-wip.yml has unguarded manual workflow_dispatch against WIP. Additional WIP-affecting manual/test/full-site and workflow_run paths require explicit entry-point-by-entry-point read-only verification. Do not push runtime candidate to operational WIP until a separate owner-approved, cross-ref hold is installed and confirmed.

## Selective release diff (proposal only)
Promotable runtime: exactly
- `kyiv-air-alerts-grafana/scripts/live_canonical_queue.py`
- `kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py`
- `kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py`

Their Git blobs are identical in `ff93eea` and final `fd3b91b`: `68c31cec6316d236c6839a4f5bb29adec89ab0c9`, `d3ad61f9807c4dec2c6e3bf97a29d78af60500be`, `bc8a63ff52273e14f89dece4681abca4dedb8c53`. No RC2 runtime fix accepted: fault validation has not established one. Research tests and offline fixtures remain research-only; no wholesale research branch merge. Capture three exact operational-WIP predecessor blobs and generate a path-limited three-file diff after passing tests; freeze any change until independent approval after a collection cycle.

## Containment plan (not executed)
Keep `main` guard; separately require deny-by-default job conditions on **all** eligible dispatch/schedule/push paths that can check out or write operational WIP, including `explosion-monitor-wip.yml`, `update-explosion-wip.yml`, `test-explosion-monitor-wip.yml`, `full-site-wip.yml`, any `workflow_run` or auxiliary writer. Review each workflow at **every triggering ref**, not only main, and consider GitHub concurrency and in-flight runs. Add explicit release-token/owner-approved narrow activation only in a later authorized change, never here. Confirm no runnable unguarded route or still-running job; only then schedule selective release after a normal data collection. Preserve cap 10, journal, state and current tips; never reset due entries to make checks green.

## Status
`C3_RC2=PARTIAL`, `STAGING_PASS_CANDIDATE=NO`, `23_CITY_POST_CUTOFF_REGRESSION=NOT_EXECUTED`, `PG16_FAULT_MATRIX=NOT_EXECUTED`, `ALL_REF_OPERATIONAL_HOLD=NOT_PROVEN`, `RELEASE_AUTHORIZED=NO`, `NEON_WRITES=NONE`, `PRODUCTION_CUTOVER=NO`.
