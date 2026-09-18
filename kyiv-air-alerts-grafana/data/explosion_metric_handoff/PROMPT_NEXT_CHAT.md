# PROMPT — continue explosion-metric research

Work from the attached/current explosion-metric handover.

## Read first — and only these files

1. `NEXT_CHAT_HANDOFF_EXPLOSION_METRIC_2026-09-18.md`
2. `city_explosion_metric_status_2026-09-18.csv`
3. `repo_snapshot/explosion_preview_input.json` only to verify which cities are already complete.

Do **not** summarize the handover back to me.

Do **not** load `explosions_test.json`, large Telegram exports, or unrelated project files unless they are needed for the active city.

## Task

Process **exactly one next unfinished city**.

Choose it from the status CSV:
1. first any real unfinished checkpoint, if one exists;
2. otherwise the row marked `next_priority`;
3. otherwise the unfinished normal city with the smallest frozen denominator.

Do not reprocess rows marked `complete_audited` or `complete_reaudited`.

Current expected next city is **Zhytomyr / Житомир** unless the status file says otherwise.

## Method

### A. Denominator
- Use the production/WIP alert-episode denominator for the frozen coverage window.
- Work at **alert episode** level, not day level.
- Do not replace the denominator with a public alert counter.

**Frozen-vs-live guardrail:** for an unfinished city, the status CSV denominator is the research denominator. Do not replace it with a newer count from `dashboard_data.json`, Grafana city JSON, the live monitor, or another current proxy series. The post-2026-09-17 live updater is a separate pipeline for the 10 already audited cities.

### B. Candidate discovery
- Search Telegram first using exact grammatical forms of the **city name** plus auditory/explosion phrases.
- Region/district/oblast mentions are leads only.
- For Zhytomyr, do **not** treat `Житомирщина`, `Житомирський район`, or oblast-only wording as exact-city evidence.

### C. Verification and matching
For each candidate:
- verify `city_status = exact_city`;
- verify aerial-war context;
- deduplicate the logical event;
- match it to a concrete alert episode.

Strict numerator requires:
- `city_status = exact_city`
- `war_air_context = confirmed`
- `temporal_match = exact_time_in_alert` OR `explicit_during_alert`

Sensitivity may additionally include strong:
- `inferred_same_attack`
- `near_boundary`

Do **not** apply automatic +/-5 or +/-10 minute tolerances.

Publication time is not explosion time.

### D. Gap search
After Telegram discovery, do a targeted local/web search for missed exact-city reports.

Avoid broad searches when a narrow query is sufficient.

### E. Final QA
Return:
- city;
- denominator;
- confirmed/review events;
- strict numerator + %;
- sensitivity numerator + %;
- unmatched/boundary cases;
- number of retained events found only by local/web gap search.

## Context and chat-length control

Minimize context aggressively.

- Work on **one city only**.
- Do not inspect other cities in parallel.
- Do not print large CSV/JSON contents into chat.
- Open raw files only when required for the current step.
- If context is becoming large, save a checkpoint/result package and **stop** instead of continuing until the chat breaks.

Use phases:
**A denominator -> B discovery -> C verification/matching -> D gap search -> E QA**

If you cannot finish the city safely in this chat, produce a compact checkpoint package containing:
- current status;
- candidate list;
- verified matches;
- unresolved cases;
- exact next step.

## Safety / scope

This is the **explosion metric** only.

Do not:
- work on casualty/deaths data;
- modify `site-prod`;
- merge to `main`;
- deploy Netlify or Grafana;
- change the frozen methodology unless explicitly asked.

Start immediately. Do not ask for confirmation.

## Automatic onboarding after a city is completed

For a newly completed normal city, do **not** edit the scheduled monitor or its city list.
When freezing the result into `data/explosion_preview_input.json`, include:
- `coverage_start` / `coverage_end`;
- `alerts_total`;
- strict and sensitivity totals;
- `strict_episode_start_dates` with one date per strict alert episode (duplicates are allowed when separate alert episodes on the same day are strict).

The scheduled WIP monitor then automatically:
1. adds the city to `explosion_audited_baseline.json`;
2. reconstructs the rolling-window denominator seed from current production dashboard data;
3. begins alert-triggered candidate discovery for that city;
4. includes the city in the KPI and rolling-90 test series.

If dated strict episodes are missing or the production denominator cannot be reconstructed, onboarding fails loudly instead of silently publishing an incomplete city.
