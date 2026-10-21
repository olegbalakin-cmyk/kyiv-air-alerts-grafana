const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const api = require("../pages-preview/kpi-range.js");
const day = (date,n,h,m=0,extra={}) => ({
  date,alerts_started:n,total_alert_duration_hours:h,
  avg_alert_duration_minutes:m,...extra
});
const month = (month,n,h,m,extra={}) => ({
  month,alerts_started:n,avg_daily_alert_hours:h,avg_alert_duration_min:m,...extra
});
const frozen=JSON.parse(fs.readFileSync(path.join(__dirname,
  "fixtures/daily28_20261020_live.json"),"utf8"));
assert.equal(Object.keys(frozen.complete_daily28).length,23);
assert.equal(frozen.current_day.cities.kyiv.partial_through,
  "2026-10-20T23:25:39.257068+03:00");
const live=[...frozen.complete_daily28.kyiv.slice(-27),frozen.current_day.cities.kyiv];
const city={daily28:live,monthly:[]};
const exact=api.calculate(city,live[0].date,live.at(-1).date);
assert.equal(exact.complete,true);
assert.equal(exact.usedDays,28);
assert.equal(exact.hasMonthly,false);
assert.equal(exact.alerts,live.reduce((s,r)=>s+r.alerts_started,0));
assert.ok(Math.abs(exact.hours-live.reduce((s,r)=>s+r.total_alert_duration_hours,0))<1e-7);
assert.equal(exact.maxDay,Math.max(...live.map(r=>r.alerts_started)));
assert.equal(exact.partialThrough,"2026-10-20T23:25:39.257068+03:00");
const oct=api.calculate(city,"2026-10-01","2026-10-20");
assert.equal(oct.complete,true);
assert.equal(oct.usedDays,20);
assert.equal(oct.alerts,live.filter(r=>r.date>="2026-10-01").reduce((s,r)=>s+r.alerts_started,0));
// Range is independent of visualization interval; no chartPeriod argument exists.
assert.deepEqual(oct,api.calculate(city,"2026-10-01","2026-10-20"));
const synthetic={monthly:[month("2026-01",31,1.5,30),month("2026-02",28,3,60)],
  daily28:[day("2026-03-01",1,2,60),day("2026-03-02",2,3,90)]};
let r=api.calculate(synthetic,"2026-01-01","2026-02-28");
assert.equal(r.complete,true);
assert.equal(r.alerts,59);
assert.ok(Math.abs(r.hours-(31*1.5+28*3))<1e-8);
assert.ok(Math.abs(r.avgDuration-(31*30+28*60)/59)<1e-8);
assert.equal(r.hasMonthly,true);
assert.equal(r.maxDay,null,"daily maximum cannot come from monthly aggregates");
r=api.calculate(synthetic,"2026-01-01","2026-03-02");
assert.equal(r.complete,true);
assert.equal(r.alerts,62);
assert.equal(r.usedDays,61);
assert.equal(r.maxDay,null);
assert.equal(api.calculate(synthetic,"2026-01-15","2026-03-02").complete,false);
assert.equal(api.calculate(synthetic,"2026-01-01","2026-03-03").complete,false);
assert.equal(api.calculate(synthetic,"2026-02-01","2026-03-01").complete,true);
assert.equal(api.calculate({monthly:[month("2026-02",8,0.215,45.2)],daily28:[]},
  "2026-02-01","2026-02-28").complete,true);
assert.equal(api.calculate({monthly:[month("2026-02",8,0.215,45.2,{is_partial_period:true})]},
  "2026-02-01","2026-02-28").complete,false,"incomplete month is never counted whole");
assert.equal(api.calculate({monthly:[month("2026-02",8,0.215,45.2),month("2026-02",10,1,45)]},
  "2026-02-01","2026-02-28").complete,false,"duplicate month rejected");
assert.equal(api.calculate({daily28:[day("2026-03-01",1,2,30),day("2026-03-01",2,2,30)]},
  "2026-03-01","2026-03-01").complete,false,"duplicate day rejected");
assert.equal(api.calculate({daily28:[day("2026-03-01",0,0),day("2026-03-02",0,0)]},
  "2026-03-01","2026-03-02").avgDuration,null,"no alerts, undefined mean");
const partial=api.calculate({daily28:[day("2026-10-20",7,10.133,86.857,
  {is_partial_period:true,partial_through:"2026-10-20T23:25:39.257068+03:00"})]},
  "2026-10-20","2026-10-20");
assert.equal(partial.complete,true);
assert.equal(partial.maxDay,7);
assert.equal(partial.partialThrough,"2026-10-20T23:25:39.257068+03:00");
assert.equal(api.validDay("2026-02-30"),false);
assert.equal(api.monthEnd("2026-02"),"2026-02-28");
const frontend=fs.readFileSync(path.join(__dirname,"../pages-preview/app.js"),"utf8");
const html=fs.readFileSync(path.join(__dirname,"../pages-preview/index.html"),"utf8");
assert.ok(frontend.includes("renderSelectedCityKpis(city, key, activeRange.from, activeRange.to)"));
assert.ok(!frontend.includes("resetCityDisplayRange();\n    renderCity();"));
assert.ok(frontend.includes('row.dataset.csvKpis = "selected-range"'));
assert.ok(frontend.includes("state.lastCityKpi"));
assert.ok(html.includes('id="kpiRangeNote"'));
assert.match(html,/kpi-range\.js\?v=20261021-(?:kpi|historical-kpi)-test1/);
console.log("PASS: live 23-city snapshot, partial current day, date boundaries, monthly/day nonoverlap, weighted duration, missing-data fail-closed, KPI/CSV binding");
