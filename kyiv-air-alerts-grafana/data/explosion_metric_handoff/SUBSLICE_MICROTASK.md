# Explosion-metric subslice task

Use this file together with exactly one row from `RESEARCH_SUBSLICES_2026-09-19.csv`.

## Guard

This is a child of one original parent slice. Before research, check whether a canonical parent result already exists for `parent_task_id` with `status = complete`.

Canonical parent path:
`data/explosion_research/<city_key>/<city_key>_P<parent_part>_result.json`

Legacy parent results may also exist in:
`data/explosion_metric_handoff/<city_key>_P<parent_part>_result.json`

If a complete parent result already exists, stop: this subslice is obsolete. Do not overwrite the parent.

## Scope

Work only on the city/date range in the active subslice row.

Assign an alert episode by its **start date in Europe/Kyiv**. A cross-midnight episode belongs to the subslice containing its start date. Never split or duplicate one episode across subslices.

The row's `frozen_denominator` is fixed. Reconstruct/retrieve only the production/WIP alert episodes for this subslice. If the retrieved count differs, write a compact result with `status = denominator_mismatch`, record the retrieved count in QA, and stop before numerator research.

## Metric

Strict requires:
- exact-city evidence;
- confirmed aerial-war context;
- one concrete matched alert episode;
- exact/approximate event time inside that episode, or explicit wording that the explosion happened during the alert.

Sensitivity may also include strong `inferred_same_attack` or `near_boundary` cases.

No automatic +/-5 or +/-10 minute tolerance. Publication time is not event time. Region/district/oblast wording is a lead, not exact-city evidence.

Count one numerator event per matched alert episode.

## Token limits

- Read only this file and the one active subslice row.
- Retrieve/filter only the active date range.
- Search exact-city web/local sources narrowly.
- Telegram/media archive is in ChatGPT Library at `/міста/Telegram Desktop.zip`. Search/use it only for one specific unresolved date/candidate. Do not bulk-unpack or bulk-scan it. If Library access is unavailable, record that fact and continue without inventing evidence.
- Do not inspect completed cities, sibling parent slices, casualty data, `explosions_test.json`, or full dashboard data.
- Do not print raw denominator rows, large JSON/CSV, search dumps, or broad rejection logs into chat.
- Keep only numerator-relevant evidence.

## Write-safety

Do not modify shared files. Create or update **only your own subslice result JSON**.

Write only:
`data/explosion_research/<city_key>/<city_key>_P<parent_part><subpart>_result.json`

Do not edit the parent result, either CSV, preview/status/handoff files, other results, or deployment/config files.

## Output

Required compact schema:

```json
{
  "status": "complete",
  "task_id": "city-P1a",
  "parent_task_id": "city-P1",
  "city_key": "...",
  "city": "...",
  "parent_part": 1,
  "subpart": "a",
  "subparts_total": 2,
  "episode_start_range": ["YYYY-MM-DD", "YYYY-MM-DD"],
  "denominator": 0,
  "strict_events": [],
  "sensitivity_only_events": [],
  "review_events": [],
  "strict_n": 0,
  "sensitivity_n": 0,
  "local_web_only_retained": 0,
  "qa": "one line"
}
```

For each retained/review event keep only:
- matched alert episode start date/time;
- event time/interval if known;
- source URL;
- one short evidence sentence;
- decision/basis.

Do not include all rejected candidates. A review item belongs in the result only if it could materially change the numerator.

Stop after this subslice.
