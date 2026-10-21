const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm"), path = require("node:path");
const KPI = require("../pages-preview/kpi-range.js");
const code = fs.readFileSync(path.join(__dirname, "../pages-preview/app.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../pages-preview/index.html"), "utf8");
const marker = "\napplyStaticLanguage();\n\ninit().catch(err=>{";
assert.ok(code.includes(marker));
assert.match(code,/if \(\$\("cityPeriod"\)\.value === "daily28"\) resetCityDisplayRange\(\);/);
assert.match(code,/const activeRange = syncDateRange\("cityDateFrom", "cityDateTo",\s*cityPeriodDateValues\(city, period, allRows\)\);/);
assert.ok(html.includes("app.js?v=20261021-cityperiod-kpi-test1"));
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,"fixtures/daily28_20261020_live.json"),"utf8"));
assert.equal(Object.keys(fixture.complete_daily28).length,23);
const rows = [...fixture.complete_daily28.kyiv.slice(-27),fixture.current_day.cities.kyiv];
assert.equal(rows.length,28);
const start = rows[0].date, end = rows.at(-1).date;
assert.equal(end,"2026-10-20");
const element = (id,value="") => ({
  id,value,min:"",max:"",textContent:"",title:"",
  classList:{add(){},remove(){}},
  removeAttribute(name){delete this[name]},
  closest(){return {querySelector(){return {textContent:""}}}}
});
const fields = Object.fromEntries(["citySelect","cityPeriod","cityDateFrom","cityDateTo",
  "kpiAlerts","kpiHours","kpiDuration","kpiMaxDay","kpiMaxDayDate","kpiRangeNote"]
  .map(id=>[id,element(id)]));
fields.citySelect.value="kyiv";fields.cityPeriod.value="monthly";
fields.cityDateFrom.value="2022-03-01";fields.cityDateTo.value=end;
const ctx={Date,Intl,URLSearchParams,console,location:{search:"?lang=uk"},
 localStorage:{getItem(){return null}},window:{KpiRange:KPI},
 document:{getElementById(id){return fields[id]||null}}};
vm.createContext(ctx);
vm.runInContext(code.slice(0,code.indexOf(marker)),ctx);
const e=js=>vm.runInContext(js,ctx);
ctx.city={daily28:rows,monthly:[
 {month:"2022-03",alerts_started:10,avg_daily_alert_hours:1,avg_alert_duration_min:40},
 {month:"2026-09",alerts_started:10,avg_daily_alert_hours:1,avg_alert_duration_min:40},
 {month:"2026-10",alerts_started:12,avg_daily_alert_hours:2,avg_alert_duration_min:30,is_partial_period:true}
],weekly:[]};
e("state.data={cities:{kyiv:city},multicity_meta:{production_city_keys:['kyiv']}}");
assert.equal(KPI.bounds(ctx.city)[0],"2022-03");
// Period changes other than the explicit 28-day preset preserve both dates.
e("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,"2022-03-01");
assert.equal(fields.cityDateTo.value,end);
// Explicit 28-day selection resets the two controls and their min/max.
fields.cityPeriod.value="daily28";
e("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,start);
assert.equal(fields.cityDateTo.value,end);
assert.equal(fields.cityDateFrom.min,start);
assert.equal(fields.cityDateTo.max,end);
const visible=e("periodRows(city,'daily28').filter(r=>dateKeyInRange(rowTime(r,'daily28'),document.getElementById('cityDateFrom').value,document.getElementById('cityDateTo').value))");
assert.equal(visible.length,28);
e("renderSelectedCityKpis(city,'kyiv',document.getElementById('cityDateFrom').value,document.getElementById('cityDateTo').value)");
const expected28=rows.reduce((s,r)=>s+r.alerts_started,0);
assert.equal(e("state.lastCityKpi.alerts"),expected28);
assert.equal(e("state.lastCityKpi.usedDays"),28);
assert.equal(fields.kpiAlerts.textContent,String(expected28));
assert.match(fields.kpiRangeNote.textContent,/Дані за 20\.10\.2026 станом на 23:25/);
assert.doesNotMatch(fields.kpiRangeNote.textContent,/Неповний день.*Дані станом на/);
assert.equal(fields.kpiRangeNote.textContent.endsWith(" · "),false);
// Narrow manually within 28 days => both plot and KPI use the subset.
fields.cityDateFrom.value="2026-10-01"; fields.cityDateTo.value="2026-10-10";
const narrowed=e("syncDateRange('cityDateFrom','cityDateTo',cityPeriodDateValues(city,'daily28',periodRows(city,'daily28')))");
assert.equal(narrowed.from,"2026-10-01");
assert.equal(narrowed.to,"2026-10-10");
const dates=e("periodRows(city,'daily28').filter(r=>dateKeyInRange(rowTime(r,'daily28'),'2026-10-01','2026-10-10'))");
assert.equal(dates.length,10);
e("renderSelectedCityKpis(city,'kyiv','2026-10-01','2026-10-10')");
const expected10=rows.filter(r=>r.date>="2026-10-01"&&r.date<="2026-10-10").reduce((s,r)=>s+r.alerts_started,0);
assert.equal(e("state.lastCityKpi.alerts"),expected10);
assert.equal(e("state.lastCityKpi.usedDays"),10);
assert.equal(fields.kpiAlerts.textContent,String(expected10));
// Weeks/months/rolling windows preserve custom From/To rather than acting as presets.
for(const period of ["monthly","calendarWeekly","weekly","rolling30","rolling90","rolling180"]) {
 fields.cityPeriod.value=period;
 e("resetCityDisplayRange()");
 const range=e("syncDateRange('cityDateFrom','cityDateTo',cityPeriodDateValues(city,document.getElementById('cityPeriod').value,periodRows(city,document.getElementById('cityPeriod').value)))");
 assert.equal(range.from,"2026-10-01",period+" from");
 assert.equal(range.to,"2026-10-10",period+" to");
 e("renderSelectedCityKpis(city,'kyiv','2026-10-01','2026-10-10')");
 assert.equal(fields.kpiAlerts.textContent,String(expected10),period+" KPI");
}
assert.doesNotMatch(fields.kpiRangeNote.textContent,/без повторного підрахунку|ковзні вікна/);
assert.doesNotMatch(code,/KPI підсумовані за датами|KPIs total the selected From.To dates without double-counting/);
// Deep-link custom subset must be preserved on refresh (without explicit preset click).
ctx.location.search="?lang=uk&period=daily28&cityfrom=2026-10-03&cityto=2026-10-08";
e("setDateInputFromParam('cityDateFrom','cityfrom')");
e("setDateInputFromParam('cityDateTo','cityto')");
fields.cityPeriod.value="daily28";
const bookmark=e("syncDateRange('cityDateFrom','cityDateTo',cityPeriodDateValues(city,'daily28',periodRows(city,'daily28')))");
assert.equal(bookmark.from,"2026-10-03");assert.equal(bookmark.to,"2026-10-08");
// Explicit re-selection resets it to full 28 days.
e("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,start);assert.equal(fields.cityDateTo.value,end);
// Stale data: derive 28 dates from the actual last completed day, not wall clock.
ctx.completeCity={daily28:fixture.complete_daily28.kyiv,monthly:[]};
const available=e("cityPeriodDateValues(completeCity,'daily28',periodRows(completeCity,'daily28'))");
assert.equal(available.length,28);
assert.equal(available[0],ctx.completeCity.daily28[0].date);
assert.equal(available.at(-1),ctx.completeCity.daily28.at(-1).date);
// Time is derived from the source timestamp in the Europe/Kyiv time zone,
 // not from the viewer's local clock, rendering date+time together.
ctx.freshCity={daily28:[{
  date:"2026-10-21",alerts_started:3,total_alert_duration_hours:2,
  avg_alert_duration_minutes:40,is_partial_period:true,
  partial_through:"2026-10-21T08:09:41+03:00"
}],monthly:[]};
e("currentLanguage='uk'");
e("renderSelectedCityKpis(freshCity,'kyiv','2026-10-21','2026-10-21')");
assert.equal(fields.kpiRangeNote.textContent,
  "Період: 21.10.2026 – 21.10.2026 · Дані за 21.10.2026 станом на 08:09");
e("currentLanguage='en'");
e("renderSelectedCityKpis(freshCity,'kyiv','2026-10-21','2026-10-21')");
assert.equal(fields.kpiRangeNote.textContent,
  "Period: 21.10.2026 – 21.10.2026 · Data for 21.10.2026 as of 08:09");
// The exact UTC equivalent must preserve the Kyiv-local 08:09.
ctx.freshCity.daily28[0].partial_through="2026-10-21T05:09:41Z";
e("renderSelectedCityKpis(freshCity,'kyiv','2026-10-21','2026-10-21')");
assert.match(fields.kpiRangeNote.textContent,/Data for 21\.10\.2026 as of 08:09/);
// A source containing only a calendar date must not invent a time.
ctx.freshCity.daily28[0].partial_through="2026-10-21";
e("renderSelectedCityKpis(freshCity,'kyiv','2026-10-21','2026-10-21')");
assert.match(fields.kpiRangeNote.textContent,/Data for 21\.10\.2026 \(incomplete day\)/);
assert.doesNotMatch(fields.kpiRangeNote.textContent,/as of/);
e("currentLanguage='uk'");
console.log("PASS: 28-day chart/KPIs and copy; dated Kyiv-local as-of in UK/EN and UTC/date-only fallback; no redundant rolling explanation");
