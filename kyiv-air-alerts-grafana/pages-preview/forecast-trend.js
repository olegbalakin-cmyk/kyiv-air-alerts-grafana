/* Research preview only. A flat EWMA level is not a predictive air-raid warning. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.ForecastTrend = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const ALPHA = 0.3;
  const MIN_HISTORY = Object.freeze({daily28: 10, calendarWeekly: 8, monthly: 6, allTime: 6});
  const MS_DAY = 86400000;

  function toDay(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date))) return null;
    const parsed = new Date(String(date) + "T00:00:00Z");
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date ? parsed : null;
  }
  function plusDays(day, count) {
    const date = toDay(day);
    if (!date) return null;
    date.setUTCDate(date.getUTCDate() + count);
    return date.toISOString().slice(0, 10);
  }
  function plusMonths(month, count) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(String(month))) return null;
    const date = new Date(String(month) + "-01T00:00:00Z");
    date.setUTCMonth(date.getUTCMonth() + count);
    return date.toISOString().slice(0, 7);
  }
  function keyOf(row, period) {
    if (period === "daily28") return String(row.date || row.time || "").slice(0, 10);
    if (period === "calendarWeekly") return String(row.week_end || "").slice(0, 10);
    return String(row.month || row.time || "").slice(0, 7);
  }
  function consecutive(prev, next, period) {
    if (period === "daily28") return plusDays(prev, 1) === next;
    if (period === "calendarWeekly") return plusDays(prev, 7) === next;
    return plusMonths(prev, 1) === next;
  }
  function nextPeriod(last, period, step) {
    if (period === "daily28") {
      const date = plusDays(keyOf(last, period), step);
      return date ? {date, time: date + "T00:00:00"} : null;
    }
    if (period === "calendarWeekly") {
      const week_start = plusDays(keyOf(last, period), 1 + 7 * (step - 1));
      const week_end = week_start && plusDays(week_start, 6);
      return week_end ? {week_start, week_end, time: week_end + "T00:00:00"} : null;
    }
    const month = plusMonths(keyOf(last, period), step);
    return month ? {month, time: month + "-01T00:00:00"} : null;
  }
  function ewma(rows, field) {
    let level = null;
    for (const row of rows) {
      const value = row[field];
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return null;
      level = level === null ? value : ALPHA * value + (1 - ALPHA) * level;
    }
    return level;
  }
  function build(rows, period) {
    if (!Object.hasOwn(MIN_HISTORY, period) || !Array.isArray(rows) || !rows.length) return null;
    const completed = rows.filter(row => row && !row.is_partial_period);
    const min = MIN_HISTORY[period];
    if (completed.length < min) return null;
    const tail = completed.slice(-min);
    for (let i = 1; i < tail.length; i++) {
      if (!consecutive(keyOf(tail[i - 1], period), keyOf(tail[i], period), period)) return null;
    }
    const hours = ewma(completed, "avg_daily_alert_hours");
    const alerts = ewma(completed, "alerts_per_day");
    if (hours === null || alerts === null) return null;
    const anchor = rows[rows.length - 1];
    const first = nextPeriod(anchor, period, 1);
    const second = nextPeriod(anchor, period, 2);
    if (!first || !second) return null;
    const forecastValue = {
      avg_daily_alert_hours: Math.max(0, Math.min(24, hours)),
      alerts_per_day: Math.max(0, alerts),
      is_forecast: true
    };
    return {
      alpha: ALPHA,
      model: "EWMA_LEVEL",
      completedPeriods: completed.length,
      excludedIncompletePeriods: rows.length - completed.length,
      forecasts: [Object.assign(first, forecastValue), Object.assign(second, forecastValue)]
    };
  }

  const barPlugin = {
    id: "forecastPreview",
    afterDatasetsDraw(chart, _args, options) {
      if (!options || !Number.isInteger(options.datasetIndex) || !Array.isArray(options.indices)) return;
      const meta = chart.getDatasetMeta(options.datasetIndex);
      if (!meta || meta.hidden) return;
      const ctx = chart.ctx;
      ctx.save();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#c5e1fa";
      ctx.setLineDash([5, 4]);
      for (const index of options.indices) {
        const el = meta.data && meta.data[index];
        if (!el || el.skip) continue;
        const {x, y, base, width} = el.getProps(["x", "y", "base", "width"], true);
        if (![x, y, base, width].every(Number.isFinite)) continue;
        const top = Math.min(y, base);
        const height = Math.abs(y - base);
        if (height < 1) continue;
        ctx.strokeRect(x - width / 2 + 1, top + 1, Math.max(0, width - 2), Math.max(0, height - 2));
      }
      ctx.restore();
    }
  };

  return {build, ewma, plusDays, plusMonths, barPlugin};
});
