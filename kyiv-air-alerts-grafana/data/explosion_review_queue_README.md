# Explosion metric review queue

This queue is populated automatically after newly completed alert episodes for the 10 audited cities.

## Statuses

- `needs_review` — discovery only; never counted.
- `approved_strict` — count the matched alert episode in strict and sensitivity.
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
