# KROPYVNYTSKYI K2 — 579 alert episodes

Work only on this half.

## Scope

- City: **Кропивницький**
- Proxy denominator source: **Кропивницький район**
- Assign episodes by **alert start date in Europe/Kyiv**
- Range: **2026-04-29 through 2026-09-17**
- Frozen denominator: **579**
- Full-city denominator is 1161; do not touch K1.

If the retrieved production episodes for this slice do not equal 579, record the mismatch and stop before changing the denominator.

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
- Telegram/media archive is in ChatGPT Library at `/міста/Telegram Desktop.zip`. Search/use it only for a **specific unresolved date or candidate**. If Library access is unavailable in this chat, record that fact and continue without inventing archive evidence.
- Never dump the 579 alert rows into chat.
- Never preserve broad negative-search logs.
- Do not inspect completed cities or K1.
- If the chat gets heavy, save the compact result below and stop.

## Write-safety

Do not modify any shared files. Create or update **only your own slice result JSON**. In particular, do not edit `RESEARCH_SLICES_2026-09-18.csv`, `explosion_preview_input.json`, status/handoff files, other slice results, or deployment/config files.

## Output

Write `kropyvnytskyi_K2_result.json` only, using the same compact schema as K1:
- status / part / episode-start range / denominator;
- strict events;
- sensitivity-only events;
- review events;
- strict_n / sensitivity_n;
- local_web_only_retained;
- one-line QA.

Each event keeps only matched episode start, event time if known, source URL, one short evidence sentence, and basis.

Do not include all rejected candidates. Add a review item only if it could materially change the numerator.

Stop after writing K2 result.
