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
    if (range === "180d") start = Math.max(first, last - 179 * DAY_MS);
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


  // Snapshot-only exact day-part seconds; fail closed if they do not match the
  // same-generation verified daily union. Never infer 09:00 from 06-hour totals.
  function splitHours(index, source, from, to, mode) {
    if (!validIndex(index) || !source || source.schema !== "weekday-dayparts-test-v1" ||
        source.meta?.timezone !== "Europe/Kyiv" || source.meta?.test_only !== true ||
        !["four", "daynight"].includes(mode) || !Array.isArray(source.rows)) return null;
    const start = dayMs(from), end = dayMs(to), base = dayMs(index.start);
    if (start === null || end === null || start > end || start < base ||
        end > dayMs(index.end) || to > source.max_day) return null;
    const dates = new Map();
    for (const row of source.rows) {
      if (!Array.isArray(row) || row.length !== 6 || dayMs(row[0]) === null ||
          dates.has(row[0]) || !row.slice(1).every(v => typeof v === "number" &&
          Number.isFinite(v) && v >= 0)) return null;
      dates.set(row[0], row.slice(1));
    }
    const bins = Array.from({length:7},(_,weekday)=>({
      weekday, days:0, seconds:0, parts:mode==="four"?[0,0,0,0]:[0,0]
    }));
    for(let ms=start;ms<=end;ms+=DAY_MS){
      const date=isoDay(ms), offset=Math.round((ms-base)/DAY_MS);
      const actual=Number(index.daily_total_alert_duration_seconds[offset]);
      const parts=dates.get(date)||[0,0,0,0,0];
      const seconds=parts.reduce((sum,n)=>sum+n,0);
      if(Math.abs(seconds-actual)>1) return null;
      const weekday=(new Date(ms).getUTCDay()+6)%7, bin=bins[weekday];
      bin.days++;
      bin.seconds+=actual;
      const values=mode==="four"
        ?[parts[0],parts[1]+parts[2],parts[3],parts[4]]
        :[parts[2]+parts[3],parts[0]+parts[1]+parts[4]];
      values.forEach((n,i)=>{bin.parts[i]+=n;});
    }
    return {mode,from,to,weekdays:bins.map(bin=>({
      ...bin,
      averageParts:bin.parts.map(n=>bin.days?n/(3600*bin.days):null)
    }))};
  }

  // A C6 release has one immutable identity, even though the Neon readback
  // and the same-run C2 derived payload have different generated_at clocks.
  // Trust neither clock alone: dashboard, KPI index and derived JSON must all
  // carry the exact published release manifest binding.
  function sameVerifiedRelease(index, ctx) {
    const id = ctx?.dashboardReleaseId;
    return typeof id === "string" && /^[a-f0-9]{64}$/.test(id) &&
      ctx.derivedReleaseId === id &&
      index?.meta?.release_manifest_sha256 === id;
  }

  function splitDerivedHours(index, ctx, from, to, mode) {
    if (!sameVerifiedRelease(index, ctx) ||
        ctx.schema !== "weekday-local-five-bands-union-v1" ||
        !Array.isArray(ctx.city?.daily)) return null;
    const rows = ctx.city.daily.map(day => [
      day.date, ...(Array.isArray(day.weekday_time_band_seconds)
        ? day.weekday_time_band_seconds : [])
    ]);
    const source = {
      schema: "weekday-dayparts-test-v1",
      meta: { timezone: "Europe/Kyiv", test_only: true },
      max_day: ctx.city.analysis_end,
      rows
    };
    // The immutable verified historical daily index remains the final
    // per-day parity gate; no proportional estimation or stale fallback.
    return splitHours(index, source, from, to, mode);
  }

  return Object.freeze({ validIndex, preset, summarize, splitHours,
    sameVerifiedRelease, splitDerivedHours });
});
