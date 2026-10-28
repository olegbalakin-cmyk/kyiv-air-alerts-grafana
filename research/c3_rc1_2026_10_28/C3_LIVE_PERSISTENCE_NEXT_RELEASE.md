# C3-RC1: Live Persistence Next Release (RECONSTRUCTED 2026-10-28)

This is a recreated minimal release design, not an exact copy of the prior unsaved local artifact.

## Frozen inputs
- main preflight: 26504ef8fbae5e620a1a4bc531751380b745ca5a
- site-prod preflight: a2d593c51830a62516d8907b6f55aae1b05e8948
- operational WIP base: 08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d
- PG16 accepted partial research: b1036d43ebd9b2df15eb58fce2192f67eb30ee68; receipt commit ced9406aa24dc056de5ac8fafa912c1032260062; Actions 38127425160 SUCCESS.
- Cutoff is exclusively config/live_persistence_activation.json: 2026-10-07T19:05:00Z; canary 10.

## Small integration
Reuse live_canonical_queue.py from PG16 proof rather than redesign. The journal is a work-obligation cache, not DB authority. Register exact state identities, retain source evidence, complete due checks only after coverage, compare desired classification key with current canonical DB tip, select <=10 unmet obligations, ensure exact parent and stale-tip CAS, persist classification/event/source transaction, verify post-COMMIT in separate session and ACK only after verified. On crash or readback failure retry and reconcile next run. Never equate checked_at or an orphan alert_episodes row to classification success.

## Boundaries
Research-only. No operational WIP / main / site-prod changes, Neon DML/DDL, UkraineAlarm requests, cutoff/canary increase, historical C4/backfill or cutover. Use cached inputs for staging. Current multi-city and source policies must remain unchanged. Tests must run against disposable PostgreSQL; prior claimed 8/8 synthetic C3 test is NOT independently established by this reconstructed artifact.

## Initial known limitations
PG16 470/47 proof predates RC1; full 23-city regression, original 29 Kyiv source/evidence and operational-hold containment are separate release gates. Updated results appear in C3_RC1_INTEGRATED_OWNER_REVIEW.md only after a real CI run and exact Git readback.
