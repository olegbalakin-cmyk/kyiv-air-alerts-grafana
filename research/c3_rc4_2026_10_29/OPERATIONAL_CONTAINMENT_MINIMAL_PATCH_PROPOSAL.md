# C3-RC4 — minimal operational containment patch proposal (NOT APPLIED)

This is a research-only owner proposal. No operational workflow has been changed.

## Root blocker
Default branch `main:.github/workflows/update-explosion-wip.yml` has `workflow_dispatch` and an unguarded `jobs.update`. The job checks out operational `multicity-wip-2026-09-16`, runs `monitor_explosion_candidates.py --local-only`, and pushes generated state to operational WIP. The existing `main:explosion-monitor-wip.yml` job-level `if: ${{ false }}` does not guard this independent entry point.

## Proposed minimal owner-authorized change (separate subsequent PR)

File: `main:.github/workflows/update-explosion-wip.yml`:

```diff
 jobs:
   update:
+    # C3 release hold: owner authorization required for removing this guard.
+    if: ${{ false }}
     runs-on: ubuntu-latest
```

Retain the existing hold in `main:.github/workflows/explosion-monitor-wip.yml`.
Do not alter or activate `live-due-orchestration-readback.yml`; first document its workflow_run trigger, hardcoded source SHA, and downstream writer, and enforce a separate event-derived exact SHA gate if the listener is ever reenabled or repurposed.

## Gate policy
`all_entry_containment_pass` is derived from machine-checked workflow matrix assertions on the *actual operational main* plus effective default-branch, manual, scheduled, push, reusable and downstream entry points. A patch that exists only on research branch does not satisfy the production/operational containment assertion. Never flip prior `safe=false` to literal `true`.

No casualty workflow changes. No automatic research branch merge. Do not run operational WIP or real Neon. Separate owner approval and independently executed post-patch containment proof are required.
