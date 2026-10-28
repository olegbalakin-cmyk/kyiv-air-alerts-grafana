# C3-RC3 OWNER REVIEW — EXECUTED RESEARCH PARTIAL (2026-10-28)

## Decision
**PARTIAL.** Release gate CLOSED. The new research CI executes real frozen-source comparison and disposable PostgreSQL 16 operations, but this is **not** a complete release proof, owner release approval, or real Neon persistence test. No operational WIP, `main`, `site-prod`, credentials or real Neon modified by this research task.

## Source and code pins
- Coordination preflight: `main@3b43a588f31bf806514ee11cf8c153c039256905`. Read `main:PROJECT_STATE.md` and `main:CHANGELOG.md` before changes.
- Frozen 23-city inputs: `site-prod@a2d593c51830a62516d8907b6f55aae1b05e8948`, filenames and measured SHA-256 in `sha_manifest.json`, locked on exact CI after first SHA probe.
- Original baseline: operational-WIP pre-RC1 `08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d`.
- Staged runtime: `ff93eea396868b62c3cab2c332b551eb16ff5fd7`. Three runtime files' original blobs remain unchanged. No selective executable runtime fix or promotion was attempted.
- WIP branch had advanced to `6071cd7d2398a5b85bcb0637575038c5faafbc25` at preflight, independently from staged research.

## Real executed proof (CI, not inference)
- First run: [40774253415](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40774253415), SHA `16a2d129`. Measured actual SHA-256 on Git-frozen inputs; source hash lock was deliberately unset and failed safely.
- Second run: [40774390818](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40774390818), SHA `4ca4882f`. Actual source-hash gate **PASS**, per-city staged vs pre-RC1 source/identity comparison **23/23 PASS**. Totals **8,444 source episodes, 2,884 eligible post-cutoff, 2,884 journal obligations, 2,884 pending, 0 acknowledged**. Outer runner PARTIAL because RC2's original harness lacked the frozen-dir manifest required for its independent invocation.
- Third run: [40774505090](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40774505090), SHA `fc7884c8`. Disposable PostgreSQL 16 with actual monitor.main() twice and independent SQL SELECTs: **PASS** repeated normal execution, two concurrent workers, post-COMMIT pre-ACK recovery, classification semantic conflict, stale current tip CAS, pruned legacy `checked_at` journal. Four scenarios remain **NOT_PROVEN**: post-commit independent readback failure, source identity conflict, source failure/retry, and positive-event-stage rollback (a negative-event SQL rollback is narrower evidence).
- RC2 harness manifest handoff repaired in research-only workflow at commit `a58dfe807a9337b78edc0dc14d231e2ed356afcf`, requiring new exact-SHA CI. Do not cite earlier success for changed test code.

## Limits / blockers
1. Finish the four unproven integrated PG16 failure cases; require independent row/tip/source/journal SQL evidence and one final actual `monitor.main()` integrated fault proof, not mocks of persistence transaction logic.
2. Original RC2 harness replay must succeed with frozen sha_manifest; record any remaining semantic mismatch independently. Positive eligible and source freshness checks have actual measurable denominators but 2,884 pending initial obligations do not prove ACK after live persistence.
3. Workflow hold not certified. Main monitor has `if:false` but default-branch `update-explosion-wip.yml` has unguarded `workflow_dispatch` and operational WIP push. WIP copy unguarded in source but do NOT treat its non-default branch presence as proof of runnable schedule. Review `c3_rc3_workflow_containment.json` (explicitly non-exhaustive) and complete trigger/runs checks before any release.
4. Full exact-SHA Actions artifact ZIP/source hashes and completed job must be checked after the last research commit. No conclusion from an in-progress run.

## Minimal next move
Keep release CLOSED. Fix only the specific outstanding four PG16 fault proofs and the audited GitHub Actions containment issue in research. Rerun exact-SHA CI, inspect frozen results and artifact digest, and seek a *separate* owner authorization for containment before any operational C3 selective promotion. Runtime candidate is exactly three staged files, with no full branch merge; isolate source, fixture, test and workflow changes. Canary remains <=10. No A5, H1/H2, C4/C6, casualty/backfill changes or real Neon access.

## Authority
`C3_RC3=PARTIAL`, `C3=PARTIAL`, `STAGING_PASS_CANDIDATE=NO`, `RELEASE_AUTHORIZED=NO`, `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`.
