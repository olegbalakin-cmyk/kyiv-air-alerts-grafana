# CASUALTY-MAIN-DEDUP-ADOPTION-2026-11-12

## Scope
Historical `main` at `375e69351e6a5aee1be16892821f7cdde2a8f21a` contains the Kyiv-only 441-line generator and an empty eight-column revisions.csv. Production `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` contains a different, multicity generator; copying that whole file would import unrelated behavior.

This patch transplants the verified incident reconciliation contract from PR #91 into the frozen Kyiv-only generator. No other city can be inserted through main's Kyiv baseline. New incident evidence columns are additive and optional at CSV-read time, but **mandatory for any newly confirmed revision**. No existing main revision is modified.

## Current execution boundary
The regular 4-hour `update-netlify-site.yml` workflow is defined on main but checks out `site-prod`, where PR #91 already landed. The separate old `update.yml` job on main is gated by `if: github.event_name == 'workflow_dispatch'`. Its push and schedule events currently skip the data-collector job. A future change to this guard would alter the risk and requires re-verification.

## Exact offline tests
The new workflow runs the adapted Kyiv-only generator against immutable main inputs, compares zero-revision output with original main, and tests incident totals, provenance requirements, isolated monthly updates, rollback, and unchanged JSON keys. It additionally checks out immutable `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` in a temporary directory and re-runs PR #91's original 25-case physical regression, including Sumy +1 and 22 other cities. Both suites are strictly offline.

## Merge plan (separate owner approval only)
Check the live main/site-prod HEADs and all relevant workflow guards immediately before merge. Verify the production 4-hour collector has fully finished and its Git publication and any deploy are complete. Merge the reviewed, exact green SHA only after that; observe the main push-triggered `update.yml` run (expected skipped while guard remains), and monitor the next scheduled C2 run and site-prod output. Do not cancel a scheduled run, modify schedules, manually dispatch, or publish any revisions.

## Rollback
Use a narrow `git revert` of the adoption commit through a new PR based on the then-current main (avoid reset/force-push). Do not revert changes in site-prod or casualty CSV/JSON. Recheck the default workflow gate and rerun offline parity. The existing frozen main source remains retrievable at `375e69351e6a5aee1be16892821f7cdde2a8f21a`.

## Limits
No casualty counts approved for publication. No new source verification, no October completeness conclusion, no Neon/C6/DST modification. This is code adoption only; original Sumy compatibility remains verified in the unchanged production branch.
