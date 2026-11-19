/* Read-only weekday aggregation over the verified same-generation daily index. */
(function (root, factory) {
  const api = factory();
  if (root) root.WeekdayDistribution = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  const DAY_MS = 86400000;

  function dayMs(day) {
    if (typeof day !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
    const n = Date.parse(day + "T00:00:00Z");
    return Number.isFinite(n) && new Date(n).toISOString().slice(0, 10) === day ? n : null;
  }

  function isoDay(ms) { return new Date(ms).toISOString().slice(0, 10); }

  function validIndex(index) {
    if (!index || index.status !== "verified") return false;
    const start = dayMs(index.start), end = dayMs(index.end);
    if (start === null || end === null || end < start) return false;
    const size = Math.round((end - start) / DAY_MS) + 1;
    if (size < 1 || size > 6000) return false;
    const counts = index.counts, seconds = index.daily_total_alert_duration_seconds;
    return Array.isArray(counts) && Array.isArray(seconds) &&
      counts.length === size && seconds.length === size &&
      counts.every(n => Number.isSafeInteger(n) && n >= 0) &&
      seconds.every(n => typeof n === "number" && Number.isFinite(n) && n >= 0);
  }

  function preset(index, range) {
    if (!validIndex(index)) return null;
    const last = dayMs(index.end), first = dayMs(index.start);
    let start = first;
    if (range === "28d") start = Math.max(first, last - 27 * DAY_MS);
    if (range === "90d") start = Math.max(first, last - 89 * DAY_MS);
    if (range === "year") start = Math.max(first, dayMs(index.end.slice(0, 4) + "-01-01"));
    return { from: isoDay(start), to: index.end };
  }

  function summarize(index, from, to) {
    if (!validIndex(index)) return null;
    const initial = dayMs(index.start), last = dayMs(index.end);
    const fromMs = dayMs(from), toMs = dayMs(to);
    if (fromMs === null || toMs === null || fromMs > toMs || toMs < initial || fromMs > last) return null;
    const start = Math.max(initial, fromMs), end = Math.min(last, toMs);
    const bins = Array.from({ length: 7 }, (_, weekday) => ({ weekday, days: 0, starts: 0, seconds: 0 }));
    for (let ms = start; ms <= end; ms += DAY_MS) {
      const i = Math.round((ms - initial) / DAY_MS);
      const weekday = (new Date(ms).getUTCDay() + 6) % 7;
      const bin = bins[weekday];
      bin.days += 1;
      bin.starts += index.counts[i];
      bin.seconds += index.daily_total_alert_duration_seconds[i];
    }
    return {
      from: isoDay(start), to: isoDay(end), calendarDays: Math.round((end - start) / DAY_MS) + 1,
      weekdays: bins.map(bin => ({
        ...bin,
        averageStarts: bin.days ? bin.starts / bin.days : null,
        averageHours: bin.days ? bin.seconds / (3600 * bin.days) : null
      }))
    };
  }

  return Object.freeze({ validIndex, preset, summarize });
});
