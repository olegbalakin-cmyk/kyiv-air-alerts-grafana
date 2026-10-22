const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const KPI=require("../pages-preview/kpi-range.js");
const root=path.join(__dirname,"../pages-preview");
const source=fs.readFileSync(path.join(root,"app.js"),"utf8");
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
assert.match(html,/<option value="allTime">За весь час<\/option>/);
assert.match(source,/setOptionText\("cityPeriod","allTime","За весь час","All time"\)/);
assert.match(source,/validParam\("period",\s*\[[^\]]*"allTime"\]/);
assert.match(source,/if \(\["daily28", "allTime"\]\.includes\(\$\("cityPeriod"\)\.value\)\) resetCityDisplayRange\(\);/);
assert.match(source,/if \(\$\("cityPeriod"\)\.value === "allTime"\) resetCityDisplayRange\(\);/);
const marker="\napplyStaticLanguage();\n\ninit().catch(err=>{";
assert.ok(source.includes(marker));
const frozen=JSON.parse(fs.readFileSync(path.join(__dirname,
  "fixtures/daily28_20261020_live.json"),"utf8"));
const daily28=[...frozen.complete_daily28.kyiv.slice(-27),frozen.current_day.cities.kyiv];
assert.equal(daily28.length,28);
const city={
  monthly:[
    {month:"2026-08",alerts_started:17,avg_daily_alert_hours:2.125,avg_alert_duration_min:40},
    {month:"2026-09",alerts_started:25,avg_daily_alert_hours:1.5,avg_alert_duration_min:50},
    {month:"2026-10",alerts_started:9,avg_daily_alert_hours:1.1,
      avg_alert_duration_min:52,is_partial_period:true}
  ],
  daily28
};
const elem=(id,value="")=>({
  id,value,min:"",max:"",textContent:"",title:"",
  classList:{add(){},remove(){}},
  removeAttribute(k){delete this[k]},
  closest(){return{querySelector(){return{textContent:""}}}}
});
const fields=Object.fromEntries(["citySelect","cityPeriod","cityDateFrom","cityDateTo",
  "kpiAlerts","kpiHours","kpiDuration","kpiMaxDay","kpiMaxDayDate","kpiRangeNote"]
  .map(id=>[id,elem(id)]));
fields.citySelect.value="kyiv";fields.cityPeriod.value="monthly";
fields.cityDateFrom.value="2026-10-01";fields.cityDateTo.value="2026-10-20";
const context={Date,Intl,URLSearchParams,console,window:{KpiRange:KPI},
  location:{search:"?lang=uk"},localStorage:{getItem(){return null}},
  document:{getElementById(id){return fields[id]||null}}
};
vm.createContext(context);
vm.runInContext(source.slice(0,source.indexOf(marker)),context);
context.city=city;
const evaluate=src=>vm.runInContext(src,context);
evaluate("state.data={cities:{kyiv:city}}");
assert.equal(evaluate("rowTime(city.monthly[0],'allTime')"),"2026-08");
assert.equal(evaluate("periodRows(city,'allTime').length"),3);
assert.equal(evaluate("periodRows(city,'allTime')[2].month"),"2026-10");
// Explicit selection of All time resets both visible date controls.
fields.cityPeriod.value="allTime";
evaluate("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,"2026-08-01");
assert.equal(fields.cityDateTo.value,"2026-10-20");
assert.equal(fields.cityDateFrom.min,"2026-08-01");
assert.equal(fields.cityDateTo.max,"2026-10-20");
const visible=evaluate("periodRows(city,'allTime').filter(row=>dateKeyInRange(rowTime(row,'allTime'),document.getElementById('cityDateFrom').value,document.getElementById('cityDateTo').value))");
assert.equal(visible.length,3);
evaluate("renderSelectedCityKpis(city,'kyiv','2026-08-01','2026-10-20','allTime')");
const oct=daily28.filter(r=>r.date>="2026-10-01"&&r.date<="2026-10-20");
const total=17+25+oct.reduce((s,r)=>s+r.alerts_started,0);
assert.equal(evaluate("state.lastCityKpi.complete"),true);
assert.equal(evaluate("state.lastCityKpi.alerts"),total);
assert.equal(evaluate("state.lastCityKpi.usedDays"),31+30+20);
assert.equal(fields.kpiAlerts.textContent,String(total));
assert.match(fields.kpiRangeNote.textContent,/За весь час: 01\.08\.2026 – 20\.10\.2026/);
assert.equal(evaluate("state.lastCityKpi.from"),"2026-08-01");
assert.equal(evaluate("state.lastCityKpi.to"),"2026-10-20");
// Verified historical counts provide an all-time daily maximum in addition
// to monthly aggregate totals without deriving a bogus maximum from averages.
const start=new Date("2026-08-01T00:00:00Z").getTime();
const counts=Array.from({length:81},(_,i)=>{
  const day=new Date(start+i*86400000).toISOString().slice(0,10);
  const recent=daily28.find(r=>r.date===day);
  return recent?recent.alerts_started:0;
});
context.index={cities:{kyiv:{status:"verified",start:"2026-08-01",
  end:"2026-10-20",counts}}};
evaluate("state.historicalDaily=index");
evaluate("renderSelectedCityKpis(city,'kyiv','2026-08-01','2026-10-20','allTime')");
assert.equal(evaluate("state.lastCityKpi.complete"),true);
assert.notEqual(fields.kpiMaxDay.textContent,"—");
// Editing a date doesn't incorrectly claim all time, and other granularities
// leave the manually entered date range untouched.
fields.cityDateFrom.value="2026-09-01";
evaluate("renderSelectedCityKpis(city,'kyiv','2026-09-01','2026-10-20','allTime')");
assert.match(fields.kpiRangeNote.textContent,/^Період: 01\.09\.2026 – 20\.10\.2026/);
for(const period of ["monthly","weekly","calendarWeekly","rolling30","rolling90","rolling180"]){
  fields.cityPeriod.value=period;
  evaluate("resetCityDisplayRange()");
  assert.equal(fields.cityDateFrom.value,"2026-09-01");
  assert.equal(fields.cityDateTo.value,"2026-10-20");
}
// Last 28 Days still resets only to available 28 daily buckets.
fields.cityPeriod.value="daily28";
evaluate("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,daily28[0].date);
assert.equal(fields.cityDateTo.value,daily28.at(-1).date);
// Deep links should restore explicit dates on load instead of resetting them.
context.location.search="?period=allTime&cityfrom=2026-09-01&cityto=2026-10-10";
evaluate("setDateInputFromParam('cityDateFrom','cityfrom')");
evaluate("setDateInputFromParam('cityDateTo','cityto')");
fields.cityPeriod.value="allTime";
const deep=evaluate("syncDateRange('cityDateFrom','cityDateTo',cityPeriodDateValues(city,'allTime',periodRows(city,'allTime')))");
assert.equal(deep.from,"2026-09-01");assert.equal(deep.to,"2026-10-10");
// Changing cities while All time is selected must adopt that city's bounds.
context.laterCity={daily28,monthly:[city.monthly[1],city.monthly[2]]};
evaluate("state.data.cities.later=laterCity");
fields.citySelect.value="later";
evaluate("resetCityDisplayRange()");
assert.equal(fields.cityDateFrom.value,"2026-09-01");
assert.equal(fields.cityDateTo.value,"2026-10-20");
assert.equal(KPI.periodKpiWindow("allTime","2026-09-01","2026-10-20",city).to,"2026-10-20");
console.log("PASS All time: labels, all monthly plot, full-history date preset per city, KPI/CSV range, validated maximum, manual edits, deep links, other modes");
