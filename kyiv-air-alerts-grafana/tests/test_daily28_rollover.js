const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

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
const evalJS = expression => vm.runInContext(expression, context);
const asDate = (start, offset) => {
  const value = new Date(start + "T00:00:00Z");
  value.setUTCDate(value.getUTCDate() + offset);
  return value.toISOString().slice(0, 10);
};
const keys = Array.from({ length: 23 }, (_unused, i) => "city_" + i);
const full = (end = "2026-10-19") => Array.from({ length: 28 }, (_unused, i) => ({
  date: asDate(end, i - 27), total_alert_duration_hours: 2,
  alerts_started: 2, avg_alert_duration_minutes: 33
}));
const makeCities = (end = "2026-10-19") => Object.fromEntries(keys.map(k => [
  k, { daily28: full(end), weekly: [{ week_start:"2026-10-12",week_end:"2026-10-18",time:"2026-10-18T00:00:00",alerts_per_day:1 }],kpis:[{alerts_28d:56}] }
]));
const envelope = (sourceDay = "2026-10-20") => ({
  meta: {
    timezone: "Europe/Kyiv", current_day: sourceDay,
    current_day_is_partial: true, kpi_period_unchanged: true
  },
  cities: Object.fromEntries(keys.map(k => [k, {
    date: sourceDay, is_partial_period: true, partial_through: sourceDay,
    total_alert_duration_hours: 4, alerts_started: 3,
    avg_alert_duration_minutes: 80
  }]))
});
const merge = (cities, source, day) => {
  context.testCities = cities; context.testEnvelope = source;context.testDay = day;
  return evalJS("mergeCurrentDayDaily28(testCities, testEnvelope, testDay)");
};
let cities = makeCities();
assert.equal(merge(cities,envelope(),"2026-10-20"),true,"existing same-day behavior");
assert.equal(cities.city_0.daily28.length,28);
assert.equal(cities.city_0.daily28[0].date,"2026-09-23");
assert.equal(cities.city_0.daily28[27].date,"2026-10-20");
assert.equal(cities.city_0.daily28[27].is_partial_period,true);
assert.equal(cities.city_0.kpis[0].alerts_28d,56,"completed-only KPI unchanged");

cities = makeCities();
assert.equal(merge(cities,envelope(),"2026-10-21"),true,"20 October survives midnight");
for(const key of keys) {
  assert.equal(cities[key].daily28.length,28);
  assert.equal(cities[key].daily28.at(-1).date,"2026-10-20");
  assert.equal(cities[key].daily28.at(-1).is_partial_period,true);
  assert.equal(cities[key].daily28.at(-2).date,"2026-10-19");
  assert.equal(cities[key].daily28.at(-1).partial_through,"2026-10-20");
}
assert.equal(new Set(cities.city_0.daily28.map(r => r.date)).size,28);
context.merged = cities;
assert.equal(evalJS("derivedCalendarWeeks(merged.city_0).at(-1).week_end"),"2026-10-25");
assert.equal(evalJS("derivedCalendarWeeks(merged.city_0).at(-1).partial_through"),"2026-10-20");
assert.equal(evalJS("partialPeriodFooter(merged.city_0.daily28.at(-1))"),"Дані станом на 20.10");
assert.equal(evalJS("chartOptions('hours').plugins.tooltip.callbacks.footer([{dataset:{_exportRows:merged.city_0.daily28},dataIndex:27}])"),"Дані станом на 20.10");
// No invented October 21 date when the source has only October 20.
assert.ok(!cities.city_0.daily28.some(r => r.date === "2026-10-21"));
cities = makeCities();
assert.equal(merge(cities,envelope(),"2026-10-23"),true,"still shown as explicitly partial while waiting for a completed version");
cities = makeCities("2026-10-20");
const beforeCompleted = JSON.stringify(cities);
assert.equal(merge(cities,envelope(),"2026-10-21"),false,"completed October 20 wins over stale partial");
assert.equal(JSON.stringify(cities),beforeCompleted,"old overlay does not mutate complete data");
assert.equal(merge(cities,envelope("2026-10-21"),"2026-10-21"),true,"new partial October 21 replaces old snapshot");
assert.equal(cities.city_0.daily28.at(-2).date,"2026-10-20");
assert.equal(cities.city_0.daily28.at(-1).date,"2026-10-21");
cities = makeCities();
const beforeFuture = JSON.stringify(cities);
assert.equal(merge(cities,envelope("2026-10-21"),"2026-10-20"),false,"never show future-dated observation");
assert.equal(JSON.stringify(cities),beforeFuture);
assert.equal(merge(makeCities(),envelope("2026-10-21"),"2026-10-21"),false,"missing completed October 20 is not silently interpolated");
// Fail closed atomically across all 23 cities.
cities = makeCities();
const missing = envelope();
delete missing.cities.city_22;
assert.equal(merge(cities,missing,"2026-10-21"),false);
assert.equal(JSON.stringify(cities),beforeFuture);
const invalid = envelope();
invalid.cities.city_22.total_alert_duration_hours=-2;
assert.equal(merge(cities,invalid,"2026-10-21"),false);
assert.equal(JSON.stringify(cities),beforeFuture);
const inconsistent = envelope();
inconsistent.cities.city_22.partial_through="2026-10-19";
assert.equal(merge(cities,inconsistent,"2026-10-21"),false);
assert.equal(JSON.stringify(cities),beforeFuture);
const missingDay = makeCities();
missingDay.city_0.daily28[21].date="2026-10-04";
assert.equal(merge(missingDay,envelope(),"2026-10-21"),false,"completed daily28 must be contiguous");
const wrongZone = envelope();
wrongZone.meta.timezone="UTC";
assert.equal(merge(makeCities(),wrongZone,"2026-10-21"),false);
const malformed= envelope();
malformed.meta.current_day="2026-10-32";
assert.equal(merge(makeCities(),malformed,"2026-11-01"),false);
assert.equal(evalJS("kyivCalendarToday(new Date('2026-10-20T20:30:00Z'))"),"2026-10-20");
assert.equal(evalJS("kyivCalendarToday(new Date('2026-10-20T21:30:00Z'))"),"2026-10-21");

// Render both 28-day charts with actual Chart.js config captured (headless).
context.Chart = class {
  constructor(_canvas, config) { this.config = config; this.options=config.options; }
  destroy() {}
};
const outputElements = {
  daily28Range: { textContent:"" },
  daily28HoursChart: { id:"daily28HoursChart" },
  daily28AlertsDurationChart: { id:"daily28AlertsDurationChart" }
};
context.document={getElementById: id => outputElements[id] || null};
evalJS("syncDateRange = (_from, _to, _times) => ({from:'',to:'',min:'',max:''})");
context.testCities = makeCities();
assert.equal(evalJS("mergeCurrentDayDaily28(testCities, testEnvelope, '2026-10-21')"),false,"earlier malformed fixture stays rejected");
context.testEnvelope = envelope();
assert.equal(evalJS("mergeCurrentDayDaily28(testCities, testEnvelope, '2026-10-21')"),true);
evalJS("state.data = {cities: testCities, multicity_meta:{weekly_mode:'rolling_7d'}};state.features.attack_events=false;renderShortHorizon('city_0')");
const hours=evalJS("state.charts.daily28HoursChart.config");
const alert=evalJS("state.charts.daily28AlertsDurationChart.config");
assert.equal(hours.data.labels.at(-1),"2026-10-20");
assert.equal(alert.data.labels.at(-1),"2026-10-20");
assert.equal(hours.data.datasets[0].data[27],4);
assert.equal(alert.data.datasets[0].data[27],3);
assert.deepEqual(Array.from(hours.options.plugins.partialPeriodBar.datasetIndices),[0]);
assert.deepEqual(Array.from(alert.options.plugins.partialPeriodBar.datasetIndices),[0]);
assert.equal(typeof hours.plugins[0].afterDatasetsDraw,"function");
assert.equal(typeof alert.plugins[0].afterDatasetsDraw,"function");
assert.deepEqual(Array.from(hours.options.plugins.tooltip.callbacks.footer([
  {dataset:hours.data.datasets[0],dataIndex:27}
])),["Почалося тривог: 3","Активних відрізків: —","Час під тривогою: —","Дані станом на 20.10"]);
assert.deepEqual(Array.from(alert.options.plugins.tooltip.callbacks.footer([
  {dataset:alert.data.datasets[0],dataIndex:27}
])),["Почалося тривог: 3","Активних відрізків: —","Час під тривогою: —","Дані станом на 20.10"]);
assert.match(outputElements.daily28Range.textContent,/Останній доступний день \(20\.10\) неповний/);
assert.match(outputElements.daily28Range.textContent,/Дані станом на 20\.10/);
assert.ok(!outputElements.daily28Range.textContent.includes("Сьогоднішній день"));
assert.equal(hours.data.datasets[0].borderWidth.at(-1),0);
assert.equal(alert.data.datasets[0].borderWidth.at(-1),0);
assert.equal(alert.data.datasets.at(-1).pointRadius.at(-1),4);
// Completed version removes partial annotations.
context.testCities=makeCities("2026-10-20");
evalJS("state.data.cities=testCities;renderShortHorizon('city_0')");
assert.match(outputElements.daily28Range.textContent,/Лише завершені дні/);
assert.equal(evalJS("state.charts.daily28HoursChart.config.data.labels.at(-1)"),"2026-10-20");
assert.equal(evalJS("state.charts.daily28HoursChart.config.data.datasets[0].borderWidth.at(-1)"),1);
evalJS("currentLanguage='en'");
context.testCities=makeCities();
context.testEnvelope=envelope();
evalJS("mergeCurrentDayDaily28(testCities, testEnvelope, '2026-10-21');state.data.cities=testCities;renderShortHorizon('city_0')");
assert.match(outputElements.daily28Range.textContent,/latest available day \(20\.10\) is incomplete/);
assert.match(outputElements.daily28Range.textContent,/Data as of 20\.10/);
// Frozen, unmodified source shapes from the real 2026-10-20 site-prod blobs:
// dashboard_data.json (28 completed daily rows) and
// site_derived.json (23 precise ISO8601 partial-through timestamps).
evalJS("currentLanguage='uk'");
const snapshot = JSON.parse(fs.readFileSync(path.join(
  __dirname, "fixtures/daily28_20261020_live.json"), "utf8"));
assert.equal(snapshot.provenance.dashboard_blob, "bcd96b56129e804a84cc50b064de6cb3d1d410f4");
assert.equal(snapshot.provenance.derived_blob, "035d592494240d9539b0649c83a50d7974e5e283");
assert.equal(snapshot.current_day.meta.current_day, "2026-10-20");
assert.equal(Object.keys(snapshot.complete_daily28).length, 23);
assert.equal(Object.keys(snapshot.current_day.cities).length, 23);
const productionCities = Object.fromEntries(Object.entries(snapshot.complete_daily28).map(
  ([key, rows]) => [key, {daily28:rows, weekly: [], kpis:[{alerts_28d:56}]}]
));
assert.equal(snapshot.current_day.cities.kyiv.partial_through, "2026-10-20T23:25:39.257068+03:00");
const liveBefore = JSON.stringify(snapshot.current_day);
assert.equal(merge(productionCities, snapshot.current_day, "2026-10-21"), true,
  "must accept actual ISO8601 timestamp from the live production payload");
assert.equal(JSON.stringify(snapshot.current_day),liveBefore,"live envelope not mutated");
for(const key of Object.keys(productionCities)) {
  assert.equal(productionCities[key].daily28.length,28, key);
  assert.equal(productionCities[key].daily28.at(-1).date,"2026-10-20",key);
  assert.equal(productionCities[key].daily28.at(-1).is_partial_period,true,key);
}
context.productionCities=productionCities;
assert.equal(evalJS("periodRows(productionCities.kyiv, 'daily28').at(-1).date"),"2026-10-20");
assert.equal(evalJS("derivedCalendarWeeks(productionCities.kyiv).at(-1).partial_through"),"2026-10-20T23:25:39.257068+03:00");
assert.equal(evalJS("partialPeriodFooter(derivedCalendarWeeks(productionCities.kyiv).at(-1))"),"Дані станом на 23:25");
assert.equal(evalJS("partialPeriodFooter(productionCities.kyiv.daily28.at(-1))"),"Дані станом на 23:25");
assert.equal(evalJS("partialPeriodFooter({is_partial_period:true,partial_through:'2026-10-20T20:25:39.257068Z'})"),"Дані станом на 23:25",
  "UTC representation must be converted to Kyiv local time");
assert.equal(evalJS("partialPeriodFooter({is_partial_period:true,partial_through:'2026-10-20T23:30:00Z'})"),"Дані станом на 20.10",
  "wrong Kyiv date must fall back to day-only rather than attaching a misleading clock");
evalJS("currentLanguage='en'");
assert.equal(evalJS("partialPeriodFooter(productionCities.kyiv.daily28.at(-1))"),"Data as of 23:25");
evalJS("currentLanguage='uk'");
// The user-visible daily28 charts must use real full timestamp payloads too.
evalJS("currentLanguage='uk';state.data={cities:productionCities,multicity_meta:{weekly_mode:'rolling_7d'}};renderShortHorizon('kyiv')");
assert.equal(evalJS("state.charts.daily28HoursChart.config.data.labels.at(-1)"),"2026-10-20");
assert.equal(evalJS("state.charts.daily28AlertsDurationChart.config.data.labels.at(-1)"),"2026-10-20");
assert.match(outputElements.daily28Range.textContent,/Дані станом на 23:25/);
assert.deepEqual(Array.from(evalJS("state.charts.daily28HoursChart.config.options.plugins.tooltip.callbacks.footer([{dataset:state.charts.daily28HoursChart.config.data.datasets[0],dataIndex:27}])")),["Почалося тривог: 7","Активних відрізків: 7","Час під тривогою: 10 год 8 хв 00 с","Дані станом на 23:25"]);
assert.deepEqual(Array.from(evalJS("state.charts.daily28AlertsDurationChart.config.options.plugins.tooltip.callbacks.footer([{dataset:state.charts.daily28AlertsDurationChart.config.data.datasets[0],dataIndex:27}])")),["Почалося тривог: 7","Активних відрізків: 7","Час під тривогою: 10 год 8 хв 00 с","Дані станом на 23:25"]);
const mismatch = JSON.parse(JSON.stringify(snapshot.current_day));
mismatch.cities.kyiv.partial_through = "2026-10-19T23:25:39+03:00";
const mismatchCities = Object.fromEntries(Object.entries(snapshot.complete_daily28).map(
  ([key, rows]) => [key, {daily28:rows}]
));
assert.equal(merge(mismatchCities,mismatch,"2026-10-21"),false,
  "reject a timestamp whose local date disagrees with the row");
const malformedTime = JSON.parse(JSON.stringify(snapshot.current_day));
malformedTime.cities.kyiv.partial_through="2026-10-20T88:88:88+03:00";
assert.equal(merge(mismatchCities,malformedTime,"2026-10-21"),false,
  "reject syntactically invalid timestamps");

console.log("PASS: midnight carryover, 23-city atomicity, continuity, completed precedence, week, both 28-day charts, freshness UI and EN/UK");
