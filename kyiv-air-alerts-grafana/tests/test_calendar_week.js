const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const code = fs.readFileSync(path.join(__dirname, "../pages-preview/app.js"), "utf8");
const marker = "\napplyStaticLanguage();\n\ninit().catch(err=>{";
assert.ok(code.includes(marker), "expected guarded browser entrypoint");
const context = {
  URLSearchParams, Date, Intl, console,
  location: { search: "?lang=uk" },
  localStorage: { getItem() { return null; } },
};
vm.createContext(context);
vm.runInContext(code.slice(0, code.indexOf(marker)), context);
const evaluate = expression => vm.runInContext(expression, context);
const baseWeek = {
  week_start: "2026-10-12", week_end: "2026-10-18",
  time: "2026-10-18T00:00:00", alerts_per_day: 1,
  avg_daily_alert_hours: 1, avg_alert_duration_min: 15,
  alerts_started: 7
};
const monday = {
  date: "2026-10-19", alerts_started: 2,
  total_alert_duration_hours: 1, avg_active_alert_duration_minutes: 20
};
const tuesday = {
  date: "2026-10-20", alerts_started: 4,
  total_alert_duration_hours: 3, avg_active_alert_duration_minutes: 40,
  is_partial_period: true, partial_through: "2026-10-20"
};
const city = { weekly: [baseWeek], daily28: [monday, tuesday] };
const keys = Array.from({ length: 23 }, (_, index) => "city_" + index);
const cities = Object.fromEntries(keys.map(key => [key, city]));
context.cities = cities;
evaluate("state.data = { cities, multicity_meta: { weekly_mode: 'rolling_7d' } }");
const weekly = evaluate("derivedCalendarWeeks(state.data.cities.city_0)");
assert.equal(weekly.length, 2);
const current = weekly[1];
assert.equal(current.week_start, "2026-10-19");
assert.equal(current.week_end, "2026-10-25", "week_end must be calendar Sunday");
assert.equal(current.time, "2026-10-25T00:00:00");
assert.equal(current.is_partial_period, true);
assert.equal(current.partial_through, "2026-10-20", "freshness date stays Tuesday");
assert.equal(current.alerts_started, 6);
assert.equal(current.alerts_per_day, 3, "divide by two available days, not seven");
assert.equal(current.avg_daily_alert_hours, 2);
assert.ok(Math.abs(current.avg_alert_duration_min - (200 / 6)) < 1e-10);
assert.equal(evaluate("calendarWeekLabel(derivedCalendarWeeks(state.data.cities.city_0)[1])"), "19–25.10");
assert.equal(evaluate("calendarWeekLabel(derivedCalendarWeeks(state.data.cities.city_0)[0])"), "12–18.10");
assert.equal(evaluate("periodDisplayLabel(derivedCalendarWeeks(state.data.cities.city_0)[1], 'calendarWeekly')"), "19–25.10");
assert.equal(evaluate("periodDisplayLabel(derivedCalendarWeeks(state.data.cities.city_0)[1], 'daily28')"), "2026-10-25");
assert.equal(evaluate("calendarWeekLabel({week_start:'2026-09-28',week_end:'2026-10-04'})"), "28.09–04.10");
assert.equal(evaluate("calendarWeekLabel({week_start:'2026-12-28',week_end:'2027-01-03'})"), "28.12.2026–03.01.2027");
const common = evaluate("commonPeriodTimes(Object.keys(state.data.cities), 'calendarWeekly')");
assert.equal(common.length, 2, "all 23 cities share exactly two distinct week keys");
assert.equal(common[1], "2026-10-25");
assert.equal(evaluate("partialPeriodFooter(derivedCalendarWeeks(state.data.cities.city_0)[1])"), "Дані станом на 20.10");
assert.equal(evaluate("partialPeriodFooter(derivedCalendarWeeks(state.data.cities.city_0)[0])"), "");
assert.equal(evaluate("chartOptions('h').plugins.tooltip.callbacks.footer([{ dataset: { _exportRows: [derivedCalendarWeeks(state.data.cities.city_0)[1]] }, dataIndex: 0 }])"), "Дані станом на 20.10");
assert.equal(evaluate("seriesDataset('City', [1,2], '#123456', false, derivedCalendarWeeks(state.data.cities.city_0)).pointRadius[1]"), 4);
assert.equal(evaluate("seriesDataset('City', [1,2], '#123456', false, derivedCalendarWeeks(state.data.cities.city_0)).segment.borderDash({p1DataIndex:1})[0]"), 3);
context.inputs = {
  compareDateFrom: {value:"2026-10-19"}, compareDateTo: {value:"2026-10-20"},
  cityDateFrom: {value:"2026-10-19"}, cityDateTo: {value:"2026-10-20"}
};
context.document = { getElementById(id) { return context.inputs[id] || null; } };
assert.equal(evaluate("sharedRows(Object.keys(state.data.cities), 'calendarWeekly').length"), 1,
  "comparison must include partial week even when selected to-date is Tuesday");
assert.equal(evaluate("sharedRows(Object.keys(state.data.cities), 'calendarWeekly')[0].rows.length"), 23);
assert.equal(evaluate("filterRowsByDateRange(derivedCalendarWeeks(state.data.cities.city_0), 'calendarWeekly', 'cityDateFrom', 'cityDateTo').length"), 1,
  "city filter must include a calendar week intersecting the selected to-date");
const sunday = {
  date:"2026-10-25", alerts_started:1, total_alert_duration_hours:2,
  avg_active_alert_duration_minutes:20, is_partial_period:true,
  partial_through:"2026-10-25"
};
context.sundayCity = {
  weekly: [baseWeek], daily28: [
    monday, tuesday, ...["21","22","23","24"].map(day=>({
      date:"2026-10-"+day, alerts_started:1,
      total_alert_duration_hours:1, avg_active_alert_duration_minutes:20
    })), sunday
  ]
};
assert.equal(evaluate("derivedCalendarWeeks(sundayCity)[1].week_end"), "2026-10-25");
assert.equal(evaluate("derivedCalendarWeeks(sundayCity)[1].is_partial_period"), true,
  "Sunday must remain incomplete while the latest Sunday is partial");
context.completedSunday = {
  weekly: [baseWeek], daily28: context.sundayCity.daily28.map(r=>({
    ...r, is_partial_period:false
  }))
};
assert.equal(evaluate("derivedCalendarWeeks(completedSunday).length"), 1,
  "completed Sunday is not generated as a fake partial week");
context.oneDayCity = { weekly:[baseWeek], daily28:[monday] };
assert.equal(evaluate("derivedCalendarWeeks(oneDayCity)[1].week_end"), "2026-10-25");
assert.equal(evaluate("derivedCalendarWeeks(oneDayCity)[1].partial_through"), "2026-10-19");
assert.equal(evaluate("derivedCalendarWeeks(oneDayCity)[1].alerts_per_day"), 2);
context.Chart = class {
  constructor(_element, config) { this.options = config.options; }
  destroy() {}
};
context.testRows = weekly;
evaluate("setDurationChart('weeklyDuration', ['12–18.10','19–25.10'], [seriesDataset('City',[1,2],'#ffffff',false,testRows)], 'minutes')");
assert.equal(evaluate("state.charts.weeklyDuration.options.plugins.tooltip.callbacks.footer([{dataset:{_exportRows:testRows},dataIndex:1}])"), "Дані станом на 20.10");
evaluate("currentLanguage = 'en'");
assert.equal(evaluate("partialPeriodFooter(derivedCalendarWeeks(state.data.cities.city_0)[1])"), "Data as of 20.10");
assert.match(code, /const labels = rows\.map\(r => periodDisplayLabel\(r, period\)\)/);
assert.match(code, /const labels = shared\.map\(x => period === "calendarWeekly"/);
console.log("calendar week end/label/as-of/day divisor/23-city alignment/Sunday/date filters/chart tooltips PASS");
