# Repair-subslice parent merge

Use this only after both repair children (`a` and `b`) of one parent are successfully reconciled and complete.

## Read

Read only:
- the two child rows in `REPAIR_SUBSLICES_2026-09-20.csv`;
- the parent row in `RESEARCH_SLICES_2026-09-18.csv`;
- the two child result JSON files;
- the current problematic parent result only when needed for discrepancy diagnostics;
- this file.

Do not reopen broad web or Telegram research during merge.

## Required validation

Both children must have `status = "complete"`.

Check all of the following before writing the parent:

- the child ranges are contiguous and non-overlapping;
- the child ranges together exactly cover the parent range;
- assignment is by alert start date in Europe/Kyiv;
- each child denominator equals its frozen repair-subslice denominator;
- child denominators sum exactly to the frozen parent denominator;
- no matched alert episode appears in both children.

Expected denominator checks:

- `kharkiv-P6`: `293 + 300 = 593`
- `sumy-P4`: `288 + 285 = 573`
- `zaporizhzhia-P4`: `296 + 294 = 590`

If any check fails, stop. Do not write the canonical parent.

## Merge

When all checks pass:

- concatenate and sort `strict_events`;
- concatenate and sort `sensitivity_only_events`;
- concatenate and sort `review_events`;
- check duplicate matched alert episodes across the two children;
- sum `strict_n`, `sensitivity_n`, and `local_web_only_retained`;
- preserve the parent's original part number, full date range, and frozen denominator;
- add a short QA line naming the two children used for reconstruction.

Write the canonical parent result to:

`data/explosion_research/<city_key>/<city_key>_P<part>_result.json`

Use the normal parent schema expected by `CITY_MERGE.md`.

## Kharkiv discrepancy requirement

For `kharkiv-P6`, the merged parent QA must explicitly record where the previous `584 vs 593` discrepancy came from.

The child frozen denominators are 293 and 300 and were not derived from 584. Compare each child's independently reconstructed episode count with its frozen denominator and identify which child or source-retrieval segment caused the nine-episode gap. Record the concrete cause if established. Do not describe the discrepancy as resolved without that provenance.

## Write safety

During this merge, write only the canonical parent result JSON.

Do not update:
- either repair child result;
- either handoff CSV;
- `explosion_preview_input.json`;
- city status CSV files;
- `final_evidence.json`;
- deployment or configuration files.

Do not run city merge. Stop after this parent.
