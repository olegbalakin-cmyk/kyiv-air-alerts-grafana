# Generic explosion-metric slice task

Use this file together with exactly one row from `RESEARCH_SLICES_2026-09-18.csv`.

## Scope

Work only on the city/date slice in that row.

Assign an alert episode by its **start date in Europe/Kyiv**. A cross-midnight episode belongs to the slice containing its start date. Never split or duplicate one episode across slices.

The row's `frozen_denominator` is fixed. Reconstruct/retrieve only the production/WIP alert episodes for that slice. If the retrieved count differs, record the mismatch and stop before changing the denominator.

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

- Read only this file and the one active CSV row.
- Retrieve/filter only the active date slice.
- Search exact-city web/local sources narrowly.
- Use the large Telegram/media archive only for one specific unresolved date/candidate. Do not bulk-unpack or bulk-scan it.
- Do not inspect completed cities, other slices, casualty data, `explosions_test.json`, or full dashboard data.
- Do not print raw denominator rows, large JSON/CSV, search dumps, or broad rejection logs into chat.
- Keep only numerator-relevant evidence.

## Output

Write one compact result JSON named:
`<city_key>_P<part>_result.json`.

Required fields:
```json
{
  "status": "complete",
  "city_key": "...",
  "city": "...",
  "part": 1,
  "parts_total": 3,
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

Stop after this slice. Do not start the next slice in the same chat.
