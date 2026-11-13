# C6 pilot capture: archived-input offline replay (2026-11-14)

## Status

**RECONSTRUCTED_CAPTURE_PASS; ORIGINAL_FAILURE_CAUSE_UNPROVEN; ZERO_PRODUCTION_PUBLICATION.**

This is a **reconstruction**, not replay of the original GitHub Actions runner worktree, which was not preserved. No original `capture()` rejection code or unarchived source-worktree files are recoverable from these artifacts.

## Immutable inputs and physical evidence

- Original failed one-off production pilot: [Actions #43510482714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714), `main@05e39b79dd5992ccdb8fb5d3f8168f7dc7c40ea9`, failed at step 46, `Freeze same-run C2 checkpoint delta`.
- Original C2 frozen-input artifact [#14079597881](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714/artifacts/14079597881), with 8 member SHA-256 verified from `manifest.json`; nested `c2-shadow-inputs.zip` SHA-256 `e7fc0c6efe460d9457c3c8a055c4422680ba125968c6dbb4680ae5383e5ff7b5` matches its sidecar.
- Original status artifact [#14080066623](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714/artifacts/14080066623) exactly matches nested `status.json`: `NEON_SUCCEEDED`, `canonical_receipt_validated=true`, expected input and workflow SHA.
- Original writer receipt: 33,444 canonical episodes, +129 new, 23 cities, persisted.
- Read-only frozen Git baseline: `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb`.
- Diagnostic script: accepted `main@9576dd06beb6b905f5fc4001672e524ed0ba5d0b`.
- Research-only exact-head [offline Actions #43518179594](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43518179594), `SUCCESS`. Output [artifact #14081467090](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43518179594/artifacts/14081467090).

## Reconstruction / what PASSED

The isolated workflow checks out the exact frozen baseline with `persist-credentials=false`, creates a local `site-prod` branch (no remote push), downloads both immutable artifacts, verifies their original SHA-256 and run identities, overlays only the five archived `site_data` JSON files, then calls `c6_neon_auto_git.py capture` once. It performs **no** C2 source collection, writer, Neon read/write, HTTP to source APIs, Git push, or Netlify build/deploy.

The function returns exit **0** and writes a `c6-neon-auto-c2-delta-v1` manifest with the exact five archived file SHA-256. The manifest explicitly states `git_publication_performed=false`, `netlify_deployments_per_update=0`. This confirms these five archived file changes, frozen identities, checkpoint-file presence and standard Git statuses are sufficient to pass under an isolated reconstructed checkout.

## Limitations and next decision

- The original runner may have contained other generated/modified/untracked/deleted files and differing worktree status. Original exact repository state and rejection reason are not in the archived C2 ZIP, so **none** can be named as the proven cause.
- The original generic exit code 2 is therefore **not** reproduced by the archived-input reconstruction.
- This **does not** prove Neon → Git publication, later proof gates, or readiness to enable any production workflow.
- Keep both production workflows disabled, `C6_AUTO_NEON_GIT_ENABLED` OFF, Git-only legacy publisher paused, and Netlify production locked. Any new production pilot requires a separate owner grant.
- A later dry run that needs to distinguish hidden worktree statuses must capture an allowlisted local status summary **before** `capture()` or independently test specific problematic cases offline; do not weaken fail-closed guards.

## Branch scope

Research-only archived-input replay workflow and this receipt. Do **not** merge the workflow into `main`, dispatch production workflows, promote, or interpret the proof as a production PASS.
