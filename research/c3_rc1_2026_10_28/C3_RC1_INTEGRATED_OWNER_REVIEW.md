# C3-RC1 INTEGRATED OWNER REVIEW — PARTIAL (2026-10-28)

## Evidence and exact refs
- Research branch: `research-c3-rc1-live-queue-2026-10-28-gpt6`, staged integration `ff93eea396868b62c3cab2c332b551eb16ff5fd7` (PG16 predecessor `b1036d43ebd9b2df15eb58fce2192f67eb30ee68`).
- Preflight at start: main `26504ef8fbae5e620a1a4bc531751380b745ca5a`, site-prod `a2d593c51830a62516d8907b6f55aae1b05e8948`, operational WIP `08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d`.
- Original earlier five C3 files were unavailable; reconstructed research variants in `research/c3_rc1_2026_10_28/` are NOT byte-identical previous local files. Earlier claimed synthetic 8/8 is NOT independently demonstrated.
- Accepted prior PG16 run 38127425160 SUCCESS at b1036d43...; accepted PARTIAL, 470 committed classifications / 47 batches, cap 10.

## New isolated integration proof
- GitHub Actions [40733060266](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40733060266), exact executed `ff93eea396868b62c3cab2c332b551eb16ff5fd7`, job 122974225818 SUCCESS, PostgreSQL 16 (disposable), [artifact 12835587047](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40733060266/artifacts/12835587047), GitHub metadata ZIP SHA-256 `683fd0a91693b49aa92cbbd0be6a62ba0624727b3af30200c09882aecced3e6e`. Job logs independently read; ZIP contents not independently downloaded or rehashed.
- `prove_pg16_canonical_pipeline.py`: existing PG16 matrix rerun against staged code, SUCCESS: 470 classifications, 47 capped batches, retry/idempotency and source/parent transaction checks. This rerun alone is not the full new RC1 safety suite.
- `prove_pg16_monitor_main.py`: actual `monitor.main()` invoked twice with frozen offline source responses; one STRICT_EVENT_POSITIVE, one source link, one independent post-COMMIT verification, second invocation zero committed writes; 23 cities CONFIGURED, NOT 23 independently regressed. No UkraineAlarm HTTP or Neon connection.

## Code delta and boundaries
Future selective promotion consists ONLY of these three runtime paths relative to operational WIP base: `kyiv-air-alerts-grafana/scripts/live_canonical_queue.py` (new), `kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py`, `kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py`. Exact stage diff in `C3_RC1_RESEARCH_DIFF.patch`; tests/fixtures/workflow are staging-only, not production payload. Cutoff remains config `2026-10-07T19:05:00Z`, canary max 10. Verdict/event/source policies not intentionally altered, but full regression is pending. No production JSON/publishing changes.

## Outstanding narrowly scoped release blockers
1. **23-city genuine regression incomplete:** current tests configure 23 but actually exercise one Kyiv end-to-end. Run frozen cached bridge and exact-city source coverage/due/geography through all 23; explicitly compare with pinned baseline, including raion proxy and Sevastopol. Confirm source errors do not become false negative ACK.
2. **Additional RC1 injection coverage incomplete:** concurrent workers, post-COMMIT/pre-ACK interruption, independent verification failure, source-link and identity conflicts, stale current tip, retained review/nonpositive revision, event-stage rollback against *staged* integrated monitor require acceptance at exact SHA. Earlier separate T1-T8 PG16 transaction proof remains accepted but has not been connected to this full workflow and exact release source.
3. **Journal retention and readiness gate require repair/proof:** currently `register_state` runs after `process_events` retention truncation, so unseen superseded/pruned obligations can be lost; no per-city coverage-completeness replay for old checked_at rows. Need register before truncation using durable cutoff, and verify no ACK from checked_at alone.
4. **Operational hold is only partial:** main's `explosion-monitor-wip.yml` job has `if: false`, but WIP copy has unguarded dispatch; independent `update-explosion-wip.yml`, `test-explosion-monitor-wip.yml`, `full-site-wip.yml`, historical/temporary and workflow_run paths are documented in main PROJECT_STATE.md. Cannot claim all-ref/all-workflow hold. Avoid operational WIP push entirely pending separate containment approval.

## Release / rollback plan (not authorized)
Re-pin three HEADs; finish the narrow tests; owner reviews the exact three-file patch, tests and hold, then separate approval for a scheduled selective WIP release after data collection (no production source/publisher changes). Observe one isolated live batch at cap 10 and durable independent SQL readback before accepting; revert exactly three promoted runtime files to pre-release blobs on failure, preserve the queue journal and re-read DB current tips; do not delete or replay committed classifications. No permission is implied for Neon writes, workflow activation, C4/backfill, cutover or canary increase.

**Verdict: C3_RC1_PARTIAL.** A genuine isolated PG16 re-execution is SUCCESS; full requested RC1 release gate is NOT PROVEN.
