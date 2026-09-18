# KROPYVNYTSKYI MERGE — no re-research

Run only after both K1 and K2 are complete.

## Read only

1. `kropyvnytskyi_K1_result.json`
2. `kropyvnytskyi_K2_result.json`
3. `data/explosion_preview_input.json`
4. this file

Do not open the large Telegram/media archive. Do not redo web search unless K1 and K2 directly conflict.

## Validate

- K1 range: 2025-09-01..2026-04-28, denominator **582**
- K2 range: 2026-04-29..2026-09-17, denominator **579**
- full denominator: **1161**
- assignment is by alert **start date in Europe/Kyiv**
- no matched alert episode appears in both halves

Same calendar date may contain multiple strict events only when they match different alert episodes.

## Merge

- `strict_n = K1.strict_n + K2.strict_n`
- `sensitivity_n = K1.sensitivity_n + K2.sensitivity_n`
- percentages = numerator / 1161 * 100, rounded to 2 decimals
- concatenate and sort retained/review events
- derive `strict_episode_start_dates` from matched strict alert episodes; keep duplicate dates if separate alert episodes on the same day are strict

Write a compact combined evidence file under:
`data/explosion_research/kropyvnytskyi/final_evidence.json`.

Then add Kropyvnytskyi to `data/explosion_preview_input.json` with:
- label;
- coverage_start = 2025-09-01;
- coverage_end = 2026-09-17;
- alerts_total = 1161;
- strict / strict_pct;
- sensitivity / sensitivity_pct;
- trend_available = true;
- strict_episode_start_dates.

Update the status CSV to `complete_audited` and advance `next_priority` to Kherson.

Do not deploy Netlify/Grafana and do not merge to main.
