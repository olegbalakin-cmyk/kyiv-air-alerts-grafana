const assert = require("node:assert/strict");
const {build, ewma, plusDays, plusMonths, barPlugin} = require("../pages-preview/forecast-trend.js");

const day = (date, hours, alerts, partial = false) =>
  ({date, avg_daily_alert_hours: hours, alerts_per_day: alerts, is_partial_period: partial});
const dates = Array.from({length: 14}, (_, i) => plusDays("2026-10-01", i));
const history = dates.map((date, i) => day(date, i % 3 + 1, i % 2 + 1));
const f = build(history, "daily28");
assert(f, "daily forecast available with contiguous completed days");
assert.equal(f.model, "EWMA_LEVEL");
assert.equal(f.forecasts.length, 2);
assert.equal(f.forecasts[0].date, "2026-10-15");
assert.equal(f.forecasts[1].date, "2026-10-16");
assert.equal(f.forecasts[0].is_forecast, true);
assert.equal(f.forecasts[0].avg_daily_alert_hours, f.forecasts[1].avg_daily_alert_hours);
assert.equal(f.forecasts[0].alerts_per_day, f.forecasts[1].alerts_per_day);
assert.equal(ewma([day("2026-10-01", 2, 1), day("2026-10-02", 4, 2)], "avg_daily_alert_hours"), 2.6);
assert.equal(build(history.slice(0, 8), "daily28"), null, "minimum history");
assert.equal(build(history.slice(1, 3).concat(history.slice(5)), "daily28"), null, "gap guard");
assert.equal(build(history.map((row, i) => i === 4 ? {...row, avg_daily_alert_hours: -1} : row), "daily28"), null, "reject invalid values");
assert.equal(build(history, "rolling30"), null, "rolling windows disabled");
assert.equal(build(history, "weekly"), null, "rolling weekly disabled");
const partial = day("2026-10-15", 25, 999, true);
const withPartial = build([...history, partial], "daily28");
assert(withPartial, "partial observation excluded from forecast EWMA");
assert.equal(withPartial.excludedIncompletePeriods, 1);
assert.equal(withPartial.forecasts[0].date, "2026-10-16");
assert.equal(withPartial.forecasts[1].date, "2026-10-17");
assert.equal(withPartial.forecasts[0].avg_daily_alert_hours, f.forecasts[0].avg_daily_alert_hours);
assert.equal(withPartial.forecasts[0].alerts_per_day, f.forecasts[0].alerts_per_day);
assert.equal(plusDays("2026-12-31", 1), "2027-01-01");
assert.equal(plusMonths("2026-12", 2), "2027-02");
const weeks = Array.from({length: 12}, (_, i) => ({
  week_start: plusDays("2026-08-03", i * 7),
  week_end: plusDays("2026-08-09", i * 7),
  avg_daily_alert_hours: 2, alerts_per_day: 1
}));
const wf = build(weeks, "calendarWeekly");
assert.equal(wf.forecasts[0].week_start, plusDays(weeks.at(-1).week_end, 1));
assert.equal(wf.forecasts[1].week_start, plusDays(weeks.at(-1).week_end, 8));
const months = Array.from({length: 8}, (_, i) => ({
  month: plusMonths("2026-01", i), avg_daily_alert_hours: 3, alerts_per_day: 1
}));
const mf = build(months, "monthly");
assert.equal(mf.forecasts[0].month, "2026-09");
assert.equal(mf.forecasts[1].month, "2026-10");
assert.equal(build(months, "allTime").forecasts.length, 2);
assert.equal(typeof barPlugin.afterDatasetsDraw, "function");
console.log("PASS: research forecast helper, 20 assertions");
