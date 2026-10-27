# C2 staged release review — no production change

## Reference pins
- Coordinator main at task start: `78cc93f88f8e4bea202c24f299fbea576dc73473`. C2 accepted coordination: `ca16847f62e8c562fe5ec254983788b212e37305`.
- Immutable original candidate: `924c3c311c22781c415d13edd06b131e1842f1db`, based on `site-prod@056668981b59194d95386eac4c236f569ffffe17`.
- New research branch is based on the exact candidate, not on main; **never merge it wholesale into main**.
- GitHub CI definition: `.github/workflows/c2-pg18-concurrency-git-race-offline.yml`, read-only checkout; localhost PostgreSQL 18 only; isolated temporary bare Git remote.

## Verified boundary and actual Neon schema limitation
- The **unmodified accepted** `kyiv-air-alerts-grafana/db/migrations/001_phase1_core.sql` was applied to a fresh isolated PostgreSQL 18 database, not the reduced tables of the 10-test baseline. The test verifies four application tables, canonical parent FK to ingestion run and PostgreSQL 18 version. It uses the actual canonical writer and PostgreSQL transaction/unique-index semantics.
- The independent 2026-10-10 Neon migration closure audit `research/neon_migration_closure_audit_2026-10-10.json` (commit `4cc20029466795f16b0c648d84acbf6d50e75c66`) observes the same four canonical tables, unique canonical episode key, exact interval unique constraint and ingestion-run FK. It **also** observes attack event classification/source/event tables and two differentiated alert tables in the operational shadow database, none created by 001. Thus this is **canonical parent-schema-equivalent staging**, not full Neon DDL/catalog parity. The current Neon schema has not been separately re-read or compared byte-by-byte; triggers, supplemental constraints, policies, indexes and default grants beyond migration remain unverified.
- A database *commit acknowledgment* and an internally valid JSON receipt are not independent production-Neon durability evidence. The new `verify_c2_release_dataset.py` supports independent isolated DB-to-canonical-payload consistency checking but must be separately reviewed/adapted for authorized production readback before deployment.

## Race condition and minimal fix
- Original `multicity_canonical_postgres.persist_canonical_episodes` classifies missing records before insertion without a serialization lock. With two concurrent writers, the unique indexes prevent duplicates, but a writer can lose the race with a SQL unique violation rather than return an idempotent existing receipt. This is a code-level race analysis; it was not demonstrated by the previous ten tests.
- Minimal research-only fix: acquire the established `db_phase1_persistence.acquire_stream_lock` PostgreSQL transaction-scoped advisory lock before the first read; after the first worker commits or rolls back, the second classifies against the new committed state. Existing uniqueness constraints remain in force. Only the multicity canonical writer is locked; other Phase-1, WIP, backfill and casualty writers unchanged.
- Tests in `test_multicity_c2_release_stage.py`: two actual independent PostgreSQL connections/processes for identical and partially overlapping corpora, no duplicate parent rows, succeeded-run counts, transactional rollback after a forced prefix, and exact retry after missing commit acknowledgment. This tests the new worker against Phase-1 DDL on isolated PG18, not mixed real-Neon writers.

## Git publication race and remediation
- The isolated bare-remote test exercises two independent Git clones, a rejected non-fast-forward push, real fetch/rebase/retry to the temporary `site-prod` branch and a subsequent upstream checkpoint change.
- Beyond the original candidate's remote UkraineAlarm checkpoint validation, the release-blueprint publication step now captures and rechecks SHA-256 digests of **the entire generated `data/` directory** and `grafana/dashboard.json` after every successful rebase before push. Any changed/missing/added data file fails closed; this protects the exact already-validated canonical/dashboard output bytes from rebase drift. An explicit `verify_c2_release_dataset.py` comparison of canonical payload/receipt to committed PostgreSQL episodes can be run separately in the isolated test harness; it is **not yet wired into the production updater**. A real production Git race remains untested.
- PostgreSQL COMMIT and Git publication are not atomic. A lost Git push/unknown acknowledgment still needs a targeted retry and independent readback. Never mark a Git push failure as successful publication.

## Selective two-ref release diff — **for separate owner approval, not executed**
1. Apply only the reviewed **workflow edits** from `research/c2_fail_closed_2026_10_27/update-netlify-site.candidate.yml` to **current** `main:.github/workflows/update-netlify-site.yml`. The reference blueprint is a research file, **not** an executable workflow. Keep `PHASE1_DB_SHADOW_FAILURE_POLICY=fail_open` unchanged. Preserve the scheduled updater concurrency, source freshness, WIP guard and downstream production QA.
2. Apply these files to **current** `site-prod`, after checking conflicts with its new HEAD:
   - modified `kyiv-air-alerts-grafana/scripts/multicity_canonical_shadow.py` (original bounded candidate);
   - modified `kyiv-air-alerts-grafana/scripts/multicity_canonical_postgres.py` (new transaction lock);
   - added `kyiv-air-alerts-grafana/scripts/verify_multicity_canonical_receipt.py`;
   - added `kyiv-air-alerts-grafana/scripts/verify_c2_publication_snapshot.py`;
   - added `kyiv-air-alerts-grafana/scripts/verify_c2_release_dataset.py` **research diagnostic only; do not require runtime installation until production DB readback design is accepted**;
   - added tests `kyiv-air-alerts-grafana/tests/test_multicity_c2_fail_closed.py` and `kyiv-air-alerts-grafana/tests/test_multicity_c2_release_stage.py` (test files, not runtime jobs).
3. Keep research CI workflow, old testing fixtures, research blueprints, proof artifacts and divergent full branch history off production refs. Review an actual two-ref `git diff` immediately before promotion; do not transplant unrelated files.
4. Release gate: owner approval of exact two-ref diff; independent review of current Neon catalog parent table/index/FK/triggers/permissions against migration; CI on the **final** research commit; validate real concurrent writer and failed-push scenarios in staging; wire and test full post-rebase DB-to-output readback or explicitly accept its residual risk; queue updater deployment after a scheduled data collection cycle when there is conflict risk; verify first normal post-deploy canonical commit, receipt, Git publication and 23-city dashboard/readback. Only then may a coordinator mark production C2 PASS.
5. Do not change `PROJECT_STATE.md` or `CHANGELOG.md` before the coordinator accepts the bounded final result. No Neon connection, branch, secret, production or site-prod mutation authorized by this document.

## Residual risks / current state
- Exact current Neon schema/catalog parity: NOT PROVEN (parent DDL matched migration; extra operational tables and runtime ACL/triggers not reviewed).
- Cross-writer coordination with non-C2 ingestion: NOT PROVEN.
- Real GitHub production updater race, DB durability readback and Netlify/23-city delivered data: NOT PROVEN.
- Two-phase DB/Git publication atomicity: NOT POSSIBLE with current topology; fail-closed detection + recoverable retry required.
- `C2_OFFLINE_RELEASE_STAGING` may be accepted boundedly on independent CI success; `C2_PRODUCTION_DEPLOYED=NO`; `C2_CUTOVER_GATE=FAIL`.
