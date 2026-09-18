# Explosion metric review queue

This queue is populated automatically after newly completed alert episodes for every city present in `explosion_audited_baseline.json`.

## Statuses

- `needs_review` — discovery only; never counted.
- `approved_strict` — count the matched alert episode in strict and sensitivity. It can be set automatically only for the narrow high-confidence rule below, or manually after review.
- `approved_sensitivity` — count only in sensitivity.
- `rejected` — do not count.

Any approved item must have `matched_episode_id` set to one concrete alert episode from
`explosion_candidate_monitor_state.json`.

## Frozen rules

Strict still requires:
- exact-city evidence;
- confirmed aerial-war context;
- exact event time inside the alert or explicit wording that the event happened during the alert.

Publication time is not event time. Do not use automatic +/-5 or +/-10 minute tolerance.

Multiple reports for one alert episode count once. Separate alert episodes on the same day may count separately.

The scheduled rebuilder deduplicates approved items by `matched_episode_id` and updates
`explosions_test.json` on the next monitor run.


## Automatic strict rule

A candidate may be promoted automatically to `approved_strict` only when all of these are true:

- exact-city wording is present;
- aerial-war context is explicit;
- the text explicitly says the explosion happened during the alert;
- this is the immediate follow-up for the alert;
- publication time falls inside that unique alert interval, with at most 30 minutes after the end.

This is deliberately narrower than the full manual strict methodology. Publication time by itself is never treated as event time. Everything else stays `needs_review`.


## Adding another audited city

Do not edit the monitor's city list. Freeze the city's audited result in
`explosion_preview_input.json`, including `strict_episode_start_dates`.
The scheduled WIP monitor automatically adds the city to
`explosion_audited_baseline.json`, builds its rolling-window denominator seed,
and starts monitoring new completed alerts on the next run.
