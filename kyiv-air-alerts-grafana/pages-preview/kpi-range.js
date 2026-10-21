/* Date-range KPI aggregation. No network access; works with the existing site-prod JSON. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.KpiRange = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  function validDay(day) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(day || ""))) return false;
    const t = Date.parse(day + "T00:00:00Z");
    return Number.isFinite(t) && new Date(t).toISOString().slice(0, 10) === day;
  }
  function validMonth(month) { return /^\d{4}-(0[1-9]|1[0-2])$/.test(String(month || "")); }
  function plusDay(day, n = 1) {
    const t = Date.parse(day + "T00:00:00Z");
    return Number.isFinite(t) ? new Date(t + n * 86400000).toISOString().slice(0, 10) : "";
  }
  function monthEnd(month) {
    if (!validMonth(month)) return "";
    const year = Number(month.slice(0, 4));
    const m = Number(month.slice(5, 7));
    return month + "-" + String(new Date(Date.UTC(year, m, 0)).getUTCDate()).padStart(2, "0");
  }
  function spanDays(from, to) {
    return Math.round((Date.parse(to + "T00:00:00Z") - Date.parse(from + "T00:00:00Z")) / 86400000) + 1;
  }
  function dailyMean(row) {
    return Number(row.is_partial_period && row.avg_active_alert_duration_minutes != null
      ? row.avg_active_alert_duration_minutes : row.avg_alert_duration_minutes);
  }
  function dailyValid(row) {
    const n = Number(row?.alerts_started), h = Number(row?.total_alert_duration_hours);
    const m = row ? dailyMean(row) : NaN;
    return validDay(row?.date) && Number.isInteger(n) && n >= 0 &&
      Number.isFinite(h) && h >= 0 && (n === 0 || (Number.isFinite(m) && m >= 0));
  }
  function monthlyValid(row, month, latestDay) {
    const n = Number(row?.alerts_started), h = Number(row?.avg_daily_alert_hours);
    const m = Number(row?.avg_alert_duration_min);
    return validMonth(month) && row?.is_partial_period !== true &&
      (!latestDay || monthEnd(month) <= latestDay) &&
      Number.isInteger(n) && n >= 0 && Number.isFinite(h) && h >= 0 &&
      (n === 0 || (Number.isFinite(m) && m >= 0));
  }
  function historicalMax(history, from, to, recentRows = []) {
    if (!history || history.status !== "verified" || !validDay(from) || !validDay(to) ||
        from < history.start || from > to || !Array.isArray(history.counts) ||
        history.counts.length !== spanDays(history.start, history.end)) return null;
    const newer = new Map();
    for (const row of recentRows) {
      if (!validDay(row.date)) continue;
      const date = row.date;
      if (newer.has(date)) return null;
      newer.set(date, row.alerts_started);
    }
    // Recent daily source is independently reconciled against the historical
    // overlap before allowing it to extend the immutable preview snapshot.
    for (const [day,n] of newer) {
      if (!Number.isInteger(n) || n < 0) return null;
      if (day >= history.start && day <= history.end &&
          n !== history.counts[spanDays(history.start, day)-1]) return null;
    }
    const values = [];
    for (let day = from; day <= to; day = plusDay(day)) {
      let count;
      if (day <= history.end) {
        count = history.counts[spanDays(history.start,day)-1];
      } else {
        count = newer.get(day);
      }
      if (!Number.isInteger(count) || count < 0) return null;
      values.push({day,count});
      if (values.length > 36600) return null;
    }
    let maximum = null;
    const dates = [];
    for (const {day,count} of values) {
      if (maximum === null || count > maximum) {
        maximum = count; dates.length = 0; dates.push(day);
      } else if (count === maximum) dates.push(day);
    }
    return maximum === null ? null : {max:maximum, dates};
  }
  function bounds(city) {
    const days = (city?.daily28 || []).filter(row => validDay(row.date));
    const latest = days.map(row => row.date).sort().at(-1) || "";
    const months = (city?.monthly || []).filter(row => {
      const month = row.month || String(row.time || "").slice(0, 7);
      return validMonth(month) && row.is_partial_period !== true &&
        (!latest || monthEnd(month) <= latest);
    }).map(row => row.month || String(row.time || "").slice(0, 7));
    return [...months, ...days.map(row => row.date)];
  }
  function calculate(city, from, to) {
    const result = {
      from, to, complete: false, alerts: null, hours: null, avgDuration: null,
      maxDay: null, maxDayDate: "", hasMonthly: false, partialThrough: "",
      usedDays: 0, reason: "incomplete_data"
    };
    if (!validDay(from) || !validDay(to) || from > to) {
      result.reason = "invalid_range";
      return result;
    }
    const expected = spanDays(from, to);
    if (!Number.isInteger(expected) || expected < 1 || expected > 36600) return result;
    const daily = new Map();
    for (const row of city?.daily28 || []) {
      if (validDay(row.date)) daily.set(row.date, daily.has(row.date) ? null : row);
    }
    const latestDay = [...daily.keys()].sort().at(-1) || "";
    const months = new Map();
    for (const row of city?.monthly || []) {
      const month = row.month || String(row.time || "").slice(0, 7);
      if (validMonth(month)) months.set(month, months.has(month) ? null : row);
    }
    const dayRow = date => {
      const row = daily.get(date);
      return dailyValid(row) ? row : null;
    };
    // Prefer day-level precision if every selected date is available.
    const exactDaily = [];
    for (let date = from; date <= to; date = plusDay(date)) {
      const row = dayRow(date);
      if (!row) break;
      exactDaily.push(row);
    }
    const allDaily = exactDaily.length === expected;
    const slices = [];
    if (allDaily) {
      for (const row of exactDaily) slices.push({ row, monthly: false, days: 1 });
    } else {
      for (let date = from; date <= to;) {
        const month = date.slice(0, 7);
        const end = monthEnd(month);
        const row = months.get(month);
        if (date.endsWith("-01") && end && end <= to &&
            monthlyValid(row, month, latestDay)) {
          slices.push({ row, monthly: true, days: Number(end.slice(-2)) });
          date = plusDay(end);
        } else {
          const exact = dayRow(date);
          if (!exact) return result; // Never prorate a month or extrapolate a missing day.
          slices.push({ row: exact, monthly: false, days: 1 });
          date = plusDay(date);
        }
      }
    }
    let alerts = 0, hours = 0, durationNumerator = 0;
    for (const entry of slices) {
      const { row, monthly, days } = entry;
      const n = Number(row.alerts_started);
      alerts += n;
      hours += monthly ? Number(row.avg_daily_alert_hours) * days
        : Number(row.total_alert_duration_hours);
      if (n) durationNumerator += n * (monthly
        ? Number(row.avg_alert_duration_min) : dailyMean(row));
      result.hasMonthly ||= monthly;
      if (!monthly && row.is_partial_period && row.partial_through) {
        result.partialThrough = row.partial_through;
      }
      result.usedDays += days;
    }
    if (result.usedDays !== expected || !Number.isFinite(hours) ||
        !Number.isFinite(durationNumerator)) return result;
    result.complete = true;
    result.reason = "";
    result.alerts = alerts;
    result.hours = hours;
    result.avgDuration = alerts ? durationNumerator / alerts : null;
    if (allDaily) {
      for (const row of exactDaily) {
        const n = Number(row.alerts_started);
        if (result.maxDay === null || n > result.maxDay) {
          result.maxDay = n;
          result.maxDayDate = row.date;
        }
      }
    }
    return result;
  }
  return {calculate, bounds, validDay, monthEnd, historicalMax};
});
