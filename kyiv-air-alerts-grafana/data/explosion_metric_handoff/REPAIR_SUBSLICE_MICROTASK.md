# Repair-subslice explosion-metric task

Use this file with exactly one row from `REPAIR_SUBSLICES_2026-09-20.csv`.

## Scope

Work on exactly one repair-subslice. Do not work on its sibling, another parent, another city, or a city merge.

Assign each alert episode by its **start date in Europe/Kyiv**. A cross-midnight episode belongs to the child containing its start date. Do not split or duplicate an episode across children.

The row's `frozen_denominator` is fixed. Reconstruct the child alert episodes independently from the same production/WIP source logic recorded in the row and used for the parent.

- `exact_city`: use the exact-city production source for that city.
- `raion_proxy`: use the recorded proxy raion and the same production/WIP proxy assembly used for the parent.
- Do not replace the frozen denominator with a newly retrieved count.
- For `kharkiv-P6a` and `kharkiv-P6b`, the previous parent retrieval of 584 is diagnostic only. Do not derive either child denominator from 584.

## Denominator reconciliation first

Before any numerator research:

1. reconstruct the alert episodes for the child date range;
2. count episodes by alert start date in Europe/Kyiv;
3. verify the reconstructed count against the child's `frozen_denominator`;
4. verify every reconstructed episode belongs inside the child range;
5. check for duplicate episode signatures.

If the count does not match, write only this child's result with `status = "denominator_mismatch"`, record the reconstructed count and the discrepancy in `qa`, and stop. Do not change the frozen denominator and do not start numerator research.

If the count matches, set the denominator to the frozen value and continue.

## Numerator

After denominator reconciliation, use the same numerator methodology as `SLICE_MICROTASK.md`.

Keep its strict and sensitivity rules unchanged:
- exact-city explosion evidence;
- confirmed aerial-war context;
- one concrete matched alert episode;
- event timing inside that episode, or explicit wording that the explosion happened during the alert;
- one numerator event per matched alert episode.

Do not introduce an automatic time tolerance.

## Write safety

Write only this repair-subslice result:

`data/explosion_research/<city_key>/<city_key>_P<part><subpart>_result.json`

Examples:
- `kharkiv-P6a` -> `data/explosion_research/kharkiv/kharkiv_P6a_result.json`
- `sumy-P4b` -> `data/explosion_research/sumy/sumy_P4b_result.json`

Never update:
- the parent result JSON;
- `REPAIR_SUBSLICES_2026-09-20.csv`;
- `RESEARCH_SLICES_2026-09-18.csv`;
- preview/status/handoff files;
- `explosion_preview_input.json`;
- `final_evidence.json`;
- deployment or configuration files.

Do not run a parent merge or city merge.

## Result schema

Use a compact child result:

```json
{
  "status": "complete",
  "task_id": "city-P4a",
  "parent_task_id": "city-P4",
  "city_key": "...",
  "city": "...",
  "parent_part": 4,
  "subpart": "a",
  "episode_start_range": ["YYYY-MM-DD", "YYYY-MM-DD"],
  "denominator": 0,
  "strict_events": [],
  "sensitivity_only_events": [],
  "review_events": [],
  "strict_n": 0,
  "sensitivity_n": 0,
  "local_web_only_retained": 0,
  "qa": "denominator reconciliation and one-line result QA"
}
```

For a denominator mismatch, keep the same file path and set `status = "denominator_mismatch"`. Leave numerator arrays empty and record the frozen and reconstructed counts in `qa`.

Stop after this one repair-subslice.
