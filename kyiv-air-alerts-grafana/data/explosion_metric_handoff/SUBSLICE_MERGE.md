# Parent-slice merge from two subslices

Use this only after both child subslices (`a` and `b`) of one `parent_task_id` are complete.

## Read only

1. the two child rows in `RESEARCH_SUBSLICES_2026-09-19.csv`;
2. the one parent row in `RESEARCH_SLICES_2026-09-18.csv`;
3. the two child result JSON files;
4. this file.

Do not reopen Telegram/media archive and do not redo web research unless the two child results directly conflict.

## Guard

If a canonical or legacy parent result already exists with `status = complete`, stop and keep that existing parent result. The child merge is no longer needed.

## Validate

- both child statuses are `complete`;
- child denominators sum exactly to the parent's frozen denominator;
- child date ranges are contiguous, non-overlapping, and together equal the parent's original date range;
- assignment is by alert start date in Europe/Kyiv;
- no matched alert episode appears in both children.

Same calendar date may appear more than once only when separate alert episodes on that date are retained.

## Merge

- concatenate and sort strict, sensitivity-only, and review events;
- sum `strict_n`;
- sum `sensitivity_n`;
- sum `local_web_only_retained`;
- preserve the original parent's part number and full parent date range;
- add a short QA line saying the parent was reconstructed from the two named children.

Write exactly one canonical parent result:

`data/explosion_research/<city_key>/<city_key>_P<parent_part>_result.json`

Use the normal parent-slice schema expected by `CITY_MERGE.md`.

## Write-safety

Write only the canonical parent result JSON. Do not update either CSV, preview/status/handoff files, city final evidence, or deployment/config files.

Stop after this parent slice. Do not start a city merge.
