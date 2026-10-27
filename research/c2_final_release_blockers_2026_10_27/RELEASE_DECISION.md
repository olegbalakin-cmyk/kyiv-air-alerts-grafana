# C2 final release blockers — research-only, 2026-10-27

## Boundary and pins
- Current coordination baseline: `main@461514b75a2bba660ed9c73c650cbef636c2786a`; `site-prod@056668981b59194d95386eac4c236f569ffffe17`. Both exact refs verified unchanged at inspection. No modifications to either operational ref.
- Previous candidate: `924c3c311c22781c415d13edd06b131e1842f1db`; accepted staging: `ce0976eeefa6180525303d031760c73f8ae73049`.
- Exact migration source: `site-prod:kyiv-air-alerts-grafana/db/migrations/001_phase1_core.sql`, blob `3b8af7940b23aae03a4f6b434d90d97dde10bfc0`.
- This branch is based on C2 staging candidate, which in turn is based on site-prod: NEVER merge it wholesale into main. **No production deploy. C2 production FAIL.**

## Current Neon catalog, bounded read-only
Verified Neon control-plane project `green-cake-44216048`, branch `br-bold-mode-b5rub8pq`, database `neondb`, unpooled read-only compute `ep-calm-rice-b5073ypp`. Server reported PostgreSQL `18.6 (fd34222)`, `transaction_read_only=on`, `pg_is_in_recovery=true`. Catalog inspected via transaction explicitly set READ ONLY with 5-second statement timeout and 1-second lock timeout, reading pg_catalog objects only, never application data. One preliminary malformed catalog SELECT was rejected by parser; corrected read-only catalog SELECTs succeeded. No Neon DDL/DML, passwords, role creation or secrets.

| Object | Current catalog | Difference vs Phase-1 migration |
| --- | --- | --- |
| `alert_episodes` | 12 columns, expected defaults/NOT NULL; PK, unique legacy key, unique exact interval; partial unique open interval and city/start index all valid | No missing/extra local columns, constraints or indexes |
| `ingestion_runs` | 23 columns; expected CHECK and PK/index valid | No missing/extra local columns, constraints or indexes |
| `alert_episode_sources` | 26 columns; expected unique source-record identity, CHECK, FK and indexes valid | No missing/extra local columns, constraints or indexes |
| `ingestion_checkpoints` | 18 columns, expected self-FK, sequence unique index, FK/checks valid | No missing/extra local columns, constraints or indexes |
| `current_ingestion_checkpoints` | view, 18 columns, standard `_RETURN` rule | Present, no unexpected custom rules |
| User-defined triggers / RLS / object ACL | No noninternal table triggers, RLS false, all inspected `relacl=NULL` | No custom triggers; ACL NULL is standard owner/default, not evidence of absent effective rights |

**Seven additional incoming FKs outside Phase-1 migration:** `alert_state_snapshots` has references to `alert_episodes.episode_uid` and `alert_episode_sources.source_observation_id`; `attack_event_classifications` has references to `alert_episodes.episode_uid` and `ingestion_runs.run_id`; `attack_events` has one reference to `alert_episodes.episode_uid` and two to `ingestion_runs.run_id`. All seven `ON DELETE RESTRICT`. These are expected operational dependent objects, not a reason to alter Phase-1 DDL. The view definition was not independently compared in literal SQL to the migration; do not claim byte-exact full-database parity.

Effective privileges sampled: `neondb_owner` has INSERT on `alert_episodes` and `ingestion_runs`; `h2_catalog_inspector_ro` has neither SELECT nor INSERT on those two objects. This C2-only check is **not** an H2 inspector runtime gate.

## Other writers and race
The current `site-prod:kyiv-air-alerts-grafana/scripts/db_phase1_persistence.py` `persist_phase1_payload()` writes `alert_episodes`, `ingestion_runs`, `alert_episode_sources`, `ingestion_checkpoints`; its advisory lock hashes `source_key,city_key,stream_key`. The C2 writer uses `multicity_canonical_shadow,all_cities,parents_v1`: **not the same lock**. Thus Phase-1 writers do not participate in C2 serialization; new Phase-1 writers may still race or abort on uniqueness. The other operational attack/snapshot tables have inbound FKs, but their write entrypoints were not exhaustively enumerated. No changes were made to WIP, C4, backfill, casualty, or Phase-1 policy.

Research-only minimal mitigation in `multicity_canonical_postgres.py`: retain C2 transaction advisory lock, apply `ON CONFLICT DO NOTHING` on C2 batch parent INSERT, compute actual inserted rows by `created_by_run_id`, re-read and semantically validate all canonical candidates; abort on mismatch or missing rows and return true exact-retry only with zero inserted. Prevents a false positive receipt on C2 side when another writer has inserted a compatible row. It does not guarantee that an unmodified Phase-1 writer never fails during a simultaneous race. No schema modifications.

## CI evidence
Independent GitHub Actions [run 40490775851](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40490775851), job `122143860878`, ran at research code commit `ce48c2154b428669097b057224d79a6520c55233`, SUCCESS on isolated `postgres:18` with service log `PostgreSQL 18.6`. Test log: existing exact-migration/lock/rebase cases `Ran 8 tests ... OK`, new targeted cases `Ran 4 tests ... OK`. No ZIP Actions artifact from that run; the immutable GitHub job log is the proof. Earlier intermediate new-branch runs `40490679719` and `40490754129` failed before final test corrections; do not count them as PASS.

New test cases: Phase-1-before-C2 (8 preexisting/15 inserted), C2-before-Phase1 exact retry, conflicting same-ID interval rejected, and a synthetic DB commit + 23-row readback + minimal QA + isolated Git bare-remote rejected push/fetch/rebase/successful retry. These are **sequential** mixed-writer tests, not a deterministic simultaneous Phase-1/C2 interleaving, and test_04 is a **reduced** publication simulation rather than execution of production workflow YAML.

## Integrated publication gate — evidence matrix
| Requested scenario | Evidence | Remaining limitation |
| --- | --- | --- |
| Successful publication | Partial: synthetic PG 23-row commit, minimal QA, isolated Git remote push | Not actual complete 23-city updater and all dashboard QA |
| PostgreSQL failure before COMMIT | Older 10/8 tests prove rollback and fail-closed writer | Not exercised in one integrated publication chain |
| Lost response after COMMIT | Older exact retry tests PASS | No full workflow end-to-end recovery journal |
| Output mutation during rebase | Existing snapshot digest test rejects changed bytes | Not combined with live publication chain |
| Concurrent Git push | Real isolated two-clone rejected push, fetch/rebase and retry PASS | May still race on next retry; bound attempt count matters |
| Rejected publication and safe retry | New test verifies remote remained old and then safely retried, C2 already-persisted | Git push lost-ACK, no-change remote validation, recovery across workflow runs not fully proven |

**Important workflow issue to resolve before promotion:** In research YAML the `if git diff --cached --quiet; then` path prints "No production data" and does not revalidate the current remote state against the database/canonical output. For uncertain prior push/ACK, this no-op is not proof that current remote contents match the committed DB corpus. The Git push/DB commit non-atomic gap needs a durable reconciliation/owner-approved recovery contract.

## Selective, two-ref release instructions — proposal ONLY
Baseline confirmed `main` workflow blob `c34eda91540cd144142b58058012def45a0d6271`, research YAML blueprint blob `606a3ab12c819255a714921cef26f1425533a4e6`; active `site-prod` unchanged at `05666898...`. Re-pin heads/blobs immediately before any separately approved promotion.

1. **main** — only `.github/workflows/update-netlify-site.yml`: replace early `Persist verified UkraineAlarm bridge checkpoint` (previous lines 218–240, early git push) with deferred combined publish after DB receipt and dataset QA, set only `MULTICITY_CANONICAL_DB_SHADOW_FAILURE_POLICY=fail_closed` (previous line 261), add `verify_multicity_canonical_receipt.py` gate, ensure snapshot SHA256 capture and verify across fetch/rebase/retry and nonzero final push failures (candidate lines 233, 273–274, 381–425). **Do not alter** `PHASE1_DB_SHADOW_FAILURE_POLICY=fail_open`, currently line 149; retain existing fetch, source freshness, WIP guard, casualty, schedules and QA boundaries.
2. **site-prod** — selective files only: `kyiv-air-alerts-grafana/scripts/multicity_canonical_shadow.py` (fail-closed; accepted blob `03407aa393f5abfa04bd1e584e8b859c1861b707`), `multicity_canonical_postgres.py` (this branch mixed-writer mitigation), add `verify_multicity_canonical_receipt.py` (blob `94271238a5453bc387bcc03d28b19677758e1373`), `verify_c2_publication_snapshot.py` (blob `cd222471df8d85be645b4c0462fdbc4df03f8507`), and bounded regression tests `test_multicity_c2_fail_closed.py`, `test_multicity_c2_release_stage.py`, `test_multicity_c2_final_blockers.py`. `verify_c2_release_dataset.py` remains research-only until separate authorized DB readback contract.
3. Never full-merge this research branch into main; preserve independent two-ref owner approval, queue deployment **after** scheduled collection if a conflict is possible; independently confirm successful working cycle before marking C2 PASS.

## Owner decision still required
- Whether partial mixed-writer race coverage is acceptable or requires deterministic simultaneous Phase1/C2 barriers.
- Whether to add an explicit full updater-chain integration harness with all six scenarios rather than treating existing component-level tests as sufficient.
- Recovery after DB COMMIT vs Git push failure/lost ACK and no-change-path remote reconciliation; define readback and retry policy.
- Exact live privileges for any other actual writer roles and full view/RLS/default ACL dependencies if desired; no H2 interpretation.
- Revalidate both current heads, selective two-ref diff, review changes, explicitly authorize and schedule deployment; then observe first successful 23-city post-deploy cycle.

**Current status: C2_STAGING=PASS_BOUNDED (supplementary checks); C2_INTEGRATED_FULL_CHAIN=NOT_PROVEN; C2_PRODUCTION=FAIL; C2_CUTOVER_GATE=FAIL.** No Neon mutation or production deployment; do not update coordinator docs until result accepted.
