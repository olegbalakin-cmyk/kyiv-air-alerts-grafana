# C6 Neon JSON publication preflight (2026-11-12)

## Scope and release boundary

This Draft PR is a **read-only, fail-closed staging gate** for the accepted six-file physical Neon JSON proof. It neither publishes Git JSON nor changes the scheduled C2 updater or Netlify. It does not install a new service, perform source HTTP or access Neon credentials.

Accepted evidence: GitHub Actions #43187464328 / artifact #13929117121, physical six-file generation PASS. C3 live browser QA #43218752830 PASS. Owner-approved C2 Sevastopol fix PR #93 merged into site-prod@6704c483; first post-merge 23/23 C2 run has not yet been certified.

## What this gate verifies

- An exact 18-file source SHA manifest and six candidate JSON files with SHA-256, no extra, omitted or symlinked files.
- Physical, read-only Neon readback tied to the C2 corpus and same branch, with no writer, source HTTP or production file writes.
- All 23 historical source receipts and continuity, including Kyiv and Sevastopol; recomputes the 36-hour source-age ceiling **at consumption time**.
- Frontend shape, 23-city historical KPI index and matching dashboard generation, non-certified current alerts and DST OFF.
- Git auxiliary source hashes, Kyiv interval JSON presence and casualty metadata presence. Does not claim to prove casualties are unchanged against a new live Git baseline.

## Why publication is still deliberately blocked

The accepted generator's verdict and publication authority explicitly say `publication_allowed=false`, `PRODUCTION_PUBLICATION_NOT_AUTHORIZED` and `RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION`. A passing historical freshness proof is **not** a release authorization. This script has no publish command, no Git credentials, no deployment tool and no code path that flips the flag.

A structurally valid pinned proof returns `PASS_SCOPED_PROOF_NO_PUBLICATION` and `production_publication_allowed=false`; invalid files, absent receipts, stale checkpoint, inconsistent index, forged permission or missing auxiliary fail closed with `BLOCKED`.

## What remains for the separate live integration PR

1. Confirm the next scheduled C2 reached 23/23 full same-run historical receipts after PR #93, preserving Sevastopol open #25100 and unresolved 25006→25008.
2. Bind the existing read-only Neon generator to **that same C2 run** and re-evaluate historical freshness against the real current clock; no reuse of this frozen artifact as a live publication input.
3. Pin compatible Git JSON, Kyoto/Kyiv intervals, auxiliary and casualty baseline; obtain a separately accepted production publication authority and matching frontend/index semantics.
4. Integrate atomic six-file Git replacement behind a default-OFF switch and fail-closed release gate into existing delivery, prove no change on failure, preserve Netlify rollback and obtain owner approval before any deployment.

**This PR is the testable preparatory gate, not the final integration.** Do not merge into main solely to enable Neon publication. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
