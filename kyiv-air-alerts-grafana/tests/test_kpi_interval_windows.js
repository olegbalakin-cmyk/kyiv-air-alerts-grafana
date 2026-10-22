const assert=require("node:assert/strict"),k=require("../pages-preview/kpi-range.js");
const c={daily28:[
 {date:"2026-10-18",is_partial_period:false},
 {date:"2026-10-19",is_partial_period:false},
 {date:"2026-10-20",is_partial_period:false},
 {date:"2026-10-21",is_partial_period:true}
]};
for(const [type,n] of [["weekly",7],["rolling30",30],["rolling90",90],["rolling180",180]]) {
 const r=k.periodKpiWindow(type,"2026-01-01","2026-10-21",c);
 assert.equal(r.to,"2026-10-21");
 assert.equal((Date.parse(r.to)-Date.parse(r.from))/86400000+1,n);
 assert.equal(r.days,n);
}
let r=k.periodKpiWindow("calendarWeekly","2026-01-01","2026-10-21",c);
assert.deepEqual([r.from,r.to],["2026-10-12","2026-10-18"]);
r=k.periodKpiWindow("calendarWeekly","2026-01-01","2026-10-12",c);
assert.deepEqual([r.from,r.to],["2026-10-05","2026-10-11"]);
r=k.periodKpiWindow("monthly","2026-03-01","2026-10-21",c);
assert.deepEqual([r.from,r.to],["2026-03-01","2026-10-21"]);
r=k.periodKpiWindow("daily28","2026-09-24","2026-10-21",c);
assert.deepEqual([r.from,r.to],["2026-09-24","2026-10-21"]);
const history={status:"verified",start:"2026-01-01",end:"2026-01-31",
  counts:Array(31).fill(1),daily_total_alert_duration_seconds:Array(31).fill(3600),
  daily_started_alert_duration_seconds:Array(31).fill(1800),
  verified_metric_months:["2026-01"],verified_metric_days:[]};
let result=k.preciseHistoricalKpis({daily28:[]},history,"2026-01-03","2026-01-09");
assert.equal(result.complete,true);assert.equal(result.alerts,7);
assert.equal(result.hours,7);assert.equal(result.avgDuration,30);
assert.equal(result.maxDay,1);
assert.equal(k.preciseHistoricalKpis({daily28:[]},{...history,verified_metric_months:[]},"2026-01-03","2026-01-09"),null);
assert.equal(k.preciseHistoricalKpis({daily28:[]},history,"2025-12-31","2026-01-09"),null);
console.log("PASS: rolling KPI windows 7/30/90/180, completed Monday-Sunday week, monthly dates, verified historical seconds, fail-closed gaps");
