# Generic city merge task

Run only when every slice for one city in `RESEARCH_SLICES_2026-09-18.csv` is complete.

## Read only

1. that city's slice result JSON files;
2. that city's rows in `RESEARCH_SLICES_2026-09-18.csv`;
3. `data/explosion_preview_input.json`;
4. this file.

Do not reopen the Telegram/media archive and do not redo web research unless two slice results directly conflict.

## Validate

- slice denominators sum to the city's frozen denominator;
- slice date ranges are contiguous and non-overlapping;
- assignment is by alert start date in Europe/Kyiv;
- no matched alert episode appears in more than one slice.

Same calendar date may appear more than once in the strict list only when separate alert episodes on that date are strict.

## Merge

- sum `strict_n`;
- sum `sensitivity_n`;
- calculate percentages over the frozen full-city denominator, rounded to 2 decimals;
- concatenate and sort retained/review events;
- derive `strict_episode_start_dates` from matched strict episodes, keeping duplicate dates when separate episodes on the same day are strict.

Write:
`data/explosion_research/<city_key>/final_evidence.json`.

Then add the city to `data/explosion_preview_input.json` with:
- label;
- frozen coverage start/end from the slice table;
- full frozen denominator;
- strict / strict_pct;
- sensitivity / sensitivity_pct;
- `trend_available = true`;
- `strict_episode_start_dates`.

Update the city row in the research status CSV to `complete_audited`, mark its slice rows complete, and advance to the next unfinished city.

No production deploy. No merge to main.
