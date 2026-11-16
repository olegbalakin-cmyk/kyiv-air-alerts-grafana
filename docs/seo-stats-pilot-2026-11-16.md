# Static historical statistics SEO pilot — test-only

**Status:** isolated Draft PR; **NOT deployed**, not merged, no Netlify unlock.  
**Git base:** `site-prod` at pilot branch creation (2026-11-16).  
**Prior audit:** [Draft PR #189](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/189).  
**Input:** [historical-daily-kpi.json](../../historical-daily-kpi.json), Git blob `5a88388445f0bb6c6ed58cb3972ca1b6bc577bc0`, generated `2026-11-13T10:08:11.334497+02:00`.  
**Machine-readable proof:** [verified_snapshot.json](../../research/seo_pilot_2026_11_16/verified_snapshot.json).

## What a user will see

At the **bottom** of the existing dashboard, alongside existing GitHub and feedback footer entries, one subtle link:

- Ukrainian: **Статистика у таблицях** → `/stats/`
- English: **Data tables** → `/en/stats/`

That link opens a compact read-only table of the **three pilot series**, with click-through pages:

- `/stats/kyiv/2026-10/` and `/en/stats/kyiv/2026-10/`
- `/stats/kharkiv/2026-10/` and `/en/stats/kharkiv/2026-10/`
- `/stats/lviv/2026-10/` and `/en/stats/lviv/2026-10/`

Each individual static page includes the completed-month alert-start count, unrounded occupied-time total shown in hours/minutes, mean **full** duration of alarms by start month, an ordinary 31-row HTML daily table, geographic coverage, source links, methods, source snapshot timestamp, canonical / `hreflang` and a `Dataset` JSON-LD descriptor. No JavaScript or live API is needed for reading.

## Historical data parity — October 2026

All values are sourced from the **same verified 23-city production Git JSON**, using the already verified `monthly_total_alert_duration_seconds` checksum/summary as an independent same-file consistency gate.

| Series | Geographic scope | Started | Occupied seconds | Occupied time, nearest minute |
| --- | --- | ---: | ---: | --- |
| Kyiv | City | 224 | 705013 | 195 h 50 min |
| Kharkiv | City | 326 | 1610340.554459 | 447 h 19 min |
| Lviv | **Lviv Raion**, not only Lviv city | 37 | 69463.697174 | 19 h 18 min |

**Methodology caution:** `daily_total_alert_duration_seconds` represents the union of actual time under alert split by local dates (Europe/Kyiv); `counts` records alarms by their start date. Mean complete duration comes from `daily_started_alert_duration_seconds`, which can differ from the within-month occupied time when incidents cross midnight/month boundaries. Rounding occurs only in visual display. Starting coverage dates and completeness differ by series; no fake zeroes before the verified date range.

**Currentness caution:** this intentionally **frozen** October 2026 snapshot reflects the November 13 source. Later accepted historical corrections or source revisions require an explicit regeneration/revalidation of these pages before production. It is not a 4-hour feed, live active-alert endpoint, or casualty series.

## What was changed on isolated branch

- Eight new **literal HTML** pages, with no reliance on JavaScript rendering for the figures.
- A low-prominence footer link on the dashboard; the existing bilingual HTML generator rewrites the EN link, preserving the prior `hreflang` behavior.
- The Netlify `_site` build command stages these already-authored static HTML pages; no new deployment workflow and no per-four-hour Netlify activity.
- `tests/test_seo_static_pilot.py`: fail-closed source coverage/month, monthly/daily parity, UA/EN canonical/alternate, table row and footer/build-path checks.
- The read-only snapshot receipt above. No change to charts, production data, timezone logic, Neon, C2 schedules, casualty sources or workflow triggers.

## Verification and open gates

**Completed offline checks in pilot preparation:** three city/month aggregates matched the same source file's canonical monthly values, all eight HTML files existed and contained a parseable table with the appropriate language/canonical/alternates, 31 daily rows on each city page, and numeric monthly values equal to the verified receipt (8/8 file checks and 3/3 source-month checks). Synthetic generator smoke and fail-closed source mismatch tests also passed locally. The committed repository unit test has been added for reruns.

**Not yet claimed:** GitHub Actions CI proof on this PR; exact built Netlify `_site` on a GitHub runner; graphical browser screenshot; public HTTP preview URL; production deployment; indexation; ChatGPT citation.

Before any release: run the committed tests on exact PR HEAD, build the `_site` output (including the existing bilingual generator), inspect desktop/mobile, verify the actual preview HTTP endpoints, reconcile latest published Netlify deploy with Git and the existing HTML QA harness, review the footer placement with the owner and obtain explicit production GO. **Do not merge this PR into `site-prod` without authorization**, because the site-prod deployment path is production-sensitive. The 4-hour Git-only data publication must remain unaffected.

**Out of scope in this pilot:** `robots.txt`, `sitemap.xml`, publication for all 23 cities, automated regeneration on every data change, search engine registration and search ranking tests. These belong to a later approved release.
