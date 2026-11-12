# Holt damped versus EWMA 0.3 — held-out 23-city backtest (2026-11-12)

Research only. No production or frontend change.

## Immutable proof

- Source: `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22`.
- `dashboard_data.json` SHA-256: `ea01943609fb4e8adc64450181cc1a94d7438507db7898fc78f99ab177d188fe`.
- GitHub Actions: [#43184581159](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43184581159) SUCCESS.
- Machine-readable proof: artifact `13928266055` (download through the Actions run).
- Script: `research/forecast_holt_damped_2026_11_12/backtest.py`.

## Method

23 production city series. From the existing, verified historical daily index, use actual daily alert starts and overlap-deduplicated time-under-alert (seconds / 3600). Build full Monday–Sunday calendar weeks (seven observed days); monthly values use published complete rows whose months appear in `verified_metric_months`. Forecast both variables as per-day rates, not raw weekly/monthly totals. The live incomplete month is excluded.

Per city, chronological first 60% used for initial fitting, 60–80% for common grid search and final 20% held out for model testing. Same forecast origin for horizon +1 and +2; the observed +1 is not incorporated into the +2 forecast. Models: full-history EWMA alpha 0.3; additive damped Holt with alpha in 0.2/0.4/0.6, beta in 0.1/0.2/0.4, phi in 0.8/0.9/0.98. Select Holt parameters by pooled city-balanced validation MAE across both horizons, and report equally weighted 23-city holdout MAE for each horizon. Negative Holt forecasts are floored at zero; daily time-under-alert forecasts capped at 24 hours.

## Full held-out MAE results

| Period | Target / day | Test origins | EWMA +1 | Holt +1 | Holt vs EWMA +1 | EWMA +2 | Holt +2 | Holt vs EWMA +2 | Holt parameters |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Daily | Alerts | 2494 | 1.857559 | 1.883469 | +1.39% | 1.967912 | 1.977526 | +0.49% | 0.2/0.1/0.8 |
| Daily | Hours | 2494 | 2.180699 | 2.235813 | +2.53% | 2.353717 | 2.385113 | +1.33% | 0.2/0.1/0.8 |
| Weekly | Alerts | 322 | 1.172962 | 1.222981 | +4.26% | 1.439086 | 1.462871 | +1.65% | 0.2/0.1/0.98 |
| Weekly | Hours | 322 | 1.504800 | 1.623915 | +7.92% | 1.824778 | 1.908885 | +4.61% | 0.2/0.1/0.8 |
| Monthly | Alerts | 44 | 0.608207 | 0.405394 | -33.35% | 1.296587 | 1.089453 | -15.98% | 0.4/0.4/0.98 |
| Monthly | Hours | 44 | 0.999263 | 0.866657 | -13.27% | 2.065893 | 2.097903 | +1.55% | 0.4/0.2/0.8 |

A positive Holt change indicates *worse* MAE. Weekly/monthly are non-overlapping complete calendar periods (not sliding seven-day or 30-day windows). The macro metric gives each city equal weight, so Kyiv's longer history cannot dominate.

## Decision

- **Days:** keep EWMA 0.3. Holt is worse on both horizons for both targets.
- **Weeks:** keep EWMA 0.3 provisionally. Holt is worse on both horizons for both targets.
- **Months:** Holt is a candidate for alert-count forecasts (both horizons) and for hours +1, but hours +2 is slightly worse and the holdout has only 44 total origins (often very few per city). An independent longer history or future prospective testing is needed before promoting a mixed model.
- The fact that EWMA +1 and +2 are identical is a defining property of its level-only projection, not a frontend bug. Do not artificially separate them.
- No automated switch, production release, or new site preview was made by this test. The existing [preview PR #80](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/80) stays a research-only EWMA preview.

## Boundaries and limitations

This validates average historical forecast error, not future strike timing. The daily index covers unequal periods across cities; rolling-origin test avoids leakage but may not be representative of the future. Short monthly histories limit confidence; metrics are not direct counts or durations for a whole week or month, but per-day averages. A true directional forecast is not guaranteed to beat a flat, smoothed level.
