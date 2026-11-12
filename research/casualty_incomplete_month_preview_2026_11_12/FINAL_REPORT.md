# CASUALTY — incomplete-month display preview (research only)

**Decision at creation: `INCOMPLETE_PREVIEW_BLOCKED` pending a real browser/export run.** Offline unit tests are not release permission. No production data mutation, PR merge, deployment or Netlify action.

## Evidence and scope

- Source: `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` (site frontend), main coordination `PROJECT_STATE.md` and `CHANGELOG.md`.
- PR #85: Zaporizhzhia October 2026 `COVERAGE_INCOMPLETE`, ≥23 confirmed deaths in one attack (10 October), not a final monthly total.
- PR #88: 11 additional candidate source bodies unavailable; zero additional *confirmed* is not zero actual deaths.
- Fixture ONLY: `fixture.json`, Zaporizhzhia `2026-10`, `deaths:null`, `confirmed_minimum:23`, `coverage_status:"INCOMPLETE"`. No published casualty JSON changes.

## Recommended one-point display

On existing monthly casualty Chart.js graph: shade/diagonal hatch over the October bar, yellow `≥23` on the bar, a small chart legend `≥ — підтверджений мінімум; дані неповні`, hover `щонайменше 23 загиблих (дані неповні)`, and an accessible one-line note below the **existing** graph card: `жовтень 2026 — щонайменше 23 загиблих. Дані неповні.` Uses pattern + symbol + words, never color alone. No new card, section, or standalone statistics subsystem. Chart canvas includes the ≥ marker and legend so existing PNG export retains the qualification; existing embed moves the whole chart card, so it retains the note. Toolbar and links remain untouched.

The test overlay `coverage-preview.js` wraps `setChart`, `renderCasualties`, `renderComparison` and `exportChartCsv` **in a localhost-only copy**, not in production `app.js`. It preserves original chart setup for all non-casualty IDs. It attaches metadata only to casualty chart datasets.

## Minimum data contract (fixture-only; not a production schema proposal)

| status | `deaths` | `confirmed_minimum` | Meaning |
|---|---:|---:|---|
| `COMPLETE` | nonnegative integer | omitted | Explicitly verified final monthly value (0 is a real confirmed zero) |
| `INCOMPLETE` | null | positive integer | Confirmed lower bound, final monthly total unknown |
| `UNKNOWN` | null | omitted | Insufficient evidence for any minimum |
| absent / legacy | existing nonnegative integer or null | omitted | Existing reconstructed presentation preserved; **not silently certified COMPLETE** |

A yearly total is `COMPLETE` only if all 12 months are present and explicitly `COMPLETE`. A mix of known and incomplete months yields a **lower bound** with status `INCOMPLETE`, not a precise total. All unknown → unknown (never 0). Existing ungraded historical records retain the prior approximate reconstructed appearance; their epistemic completeness is not retroactively certified. Aggregate/published chart source-note with incomplete months explicitly says no final overall total is known.

CSV: casualty charts with classified rows append per-series `coverage_status`, `value_kind`, and `confirmed_minimum`. For the October fixture, numeric 23 is explicitly `confirmed_lower_bound_not_final`; an `UNKNOWN` is blank, not 0. For pre-existing legacy-only charts, CSV passes through to the original exporter unchanged. Comparison and yearly chart metadata use the same classifier.

## Reproduce offline

On the research branch, from repository root:

```bash
node research/casualty_incomplete_month_preview_2026_11_12/test_offline.js
node --check research/casualty_incomplete_month_preview_2026_11_12/coverage-preview.js
```

## Reproduce browser without deployment

Use a **local** installed Chart.js 4.4.7 UMD asset (no download performed by the builder), e.g. `node_modules/chart.js/dist/chart.umd.js`. From this branch's checkout:

```bash
python research/casualty_incomplete_month_preview_2026_11_12/prepare_local_preview.py --chart-js node_modules/chart.js/dist/chart.umd.js --output /tmp/casualty-incomplete-preview
python -m http.server 8765 --bind 127.0.0.1 --directory /tmp/casualty-incomplete-preview
```

Open `http://127.0.0.1:8765/?coverage_fixture=1&city=zaporizhzhia&casyear=2026`.

The builder copies original `site-prod` frontend and data into an ephemeral directory, changes only the copied app's remote data base to localhost and the copied HTML to load the local overlay. It also replaces the Chart.js CDN dependency with a local exact-version script. `local-fixture-loader.js` intercepts the local dashboard GET and changes **only the in-memory** 2026-10 row for Zaporizhzhia; the underlying Git JSON and source file are untouched. Local server binds `127.0.0.1`. If the site schema or asset locations differ, the builder fails rather than modifying production.

Suggested manual browser checks: hover October bar; use keyboard focus to read inline note; switch city Kyiv and back; switch month/year; export CSV with and without the fixture; use PNG/share and embed on the localhost copy; view at 375px; compare alert statistics before/after; remove fixture scripts and reload to demonstrate rollback. No live deployment is necessary.

## Proof boundary

The offline test covers normalization, unknown-vs-zero, annual lower-bound semantics, file isolation, target functions, CSV hooks and static export mechanisms. **It does not establish visual browser QA, actual PNG semantics, clipboard/share, generated CSV byte parity, mobile accessibility, or full dataset parity.** These must be independently verified in the isolated local browser before `INCOMPLETE_PREVIEW_PASS`. The untouched legacy frontend can be restored by simply not injecting local preview scripts; no production rollback is needed.

Do **not** import any fixture or status keys into production JSON before separate owner approval of the display and generator contract.
