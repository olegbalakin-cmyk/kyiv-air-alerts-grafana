# KROPYVNYTSKYI K1 — 582 alert episodes

Work only on this half.

## Scope

- City: **Кропивницький**
- Proxy denominator source: **Кропивницький район**
- Assign episodes by **alert start date in Europe/Kyiv**
- Range: **2025-09-01 through 2026-04-28**
- Frozen denominator: **582**
- Full-city denominator is 1161; do not touch K2.

If the retrieved production episodes for this slice do not equal 582, record the mismatch and stop before changing the denominator.

## Count rules

Strict event:
- exact-city evidence for Кропивницький;
- confirmed aerial-war context;
- matched to one concrete alert episode by event time/interval, or explicit wording that the explosion occurred during the alert.

Sensitivity may additionally retain strong `inferred_same_attack` or `near_boundary`.

No automatic time tolerance. Count one numerator event per matched alert episode.

Region/district-only wording is not enough.

## Token rules

- Retrieve/filter only this date slice.
- Search exact-city web/local sources narrowly.
- Use the large Telegram/media archive only for a **specific unresolved date or candidate**.
- Never dump the 582 alert rows into chat.
- Never preserve broad negative-search logs.
- Do not inspect completed cities or K2.
- If the chat gets heavy, save the compact result below and stop.

## Output

Write `kropyvnytskyi_K1_result.json` only. Keep it compact:

```json
{
  "status": "complete",
  "part": "K1",
  "episode_start_range": ["2025-09-01", "2026-04-28"],
  "denominator": 582,
  "strict_events": [
    {
      "matched_episode_start": "ISO timestamp or local date/time",
      "event_time": "time/interval if known",
      "source_url": "...",
      "evidence": "one short sentence",
      "basis": "exact_time_in_alert|explicit_during_alert"
    }
  ],
  "sensitivity_only_events": [],
  "review_events": [],
  "strict_n": 0,
  "sensitivity_n": 0,
  "local_web_only_retained": 0,
  "qa": "one line"
}
```

Do not include all rejected candidates. Add a review item only if it could materially change the numerator.

Stop after writing K1 result. Do not start K2.
