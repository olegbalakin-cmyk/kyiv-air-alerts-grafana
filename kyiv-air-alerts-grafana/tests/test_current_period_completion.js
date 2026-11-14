const assert=require("node:assert/strict"),fs=require("node:fs");
const F=require("../pages-preview/current-period-completion.js");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const end="2026-11-13",start="2026-07-01",days=F.bounds(end,"quarterly");
assert.deepEqual(F.bounds("2026-11-14","quarterly"),{start:"2026-10-01",end:"2026-12-31",days:92,key:"2026-Q4"});
assert.equal(F.bounds("2026-11-14","calendarWeekly").start,"2026-11-09");
assert.equal(F.bounds("2026-11-14","calendarWeekly").end,"2026-11-15");
assert.equal(F.bounds("2026-11-14","monthly").end,"2026-11-30");
assert.equal(F.bounds("2026-01-01","quarterly").end,"2026-03-31");
const n=Math.round((Date.parse(end)-Date.parse(start))/86400000)+1;
const dates=Array.from({length:n},(_,i)=>F.add(start,i));
const history={status:"verified",start,end,counts:dates.map(()=>2),
daily_total_alert_duration_seconds:dates.map(()=>7200),
verified_metric_months:[...new Set(dates.map(d=>d.slice(0,7)))],
verified_metric_days:[]};
for(const mode of ["calendarWeekly","monthly","quarterly"]){
 const z=F.estimate(history,mode,"2026-11-14");
 assert(z,mode);assert(z.observed>=({calendarWeekly:2,monthly:7,quarterly:30}[mode]));
 assert(z.left>0&&z.days===z.left+z.observed);
 assert.equal(z.expectedAlerts,z.days*2);
 assert(Math.abs(z.expectedHours-z.days*2)<1e-6);
 assert.equal(z.periodRow.is_partial_period,true);
 assert.equal(z.periodRow.partial_through,"2026-11-13");
 assert.equal(z.periodRow.alerts_started,z.actualAlerts);
}
assert.equal(F.estimate({...history,status:"unverified"},"quarterly","2026-11-14"),null);
assert.equal(F.estimate({...history,end:"2026-11-12"},"quarterly","2026-11-14"),null);
assert.equal(F.estimate({...history,verified_metric_months:[],verified_metric_days:[]},"monthly","2026-11-14"),null);
assert.equal(F.estimate({...history,counts:[...history.counts.slice(0,-1),-1]},"monthly","2026-11-14"),null);
assert.equal(F.estimate(history,"quarterly","2026-10-14"),null); // 13 complete days, threshold 30
assert.equal(F.estimate(history,"calendarWeekly","2026-11-10"),null); // index is not yesterday
assert(app.includes('window.PeriodCompletionPreview?.estimate('));
assert(app.includes('const completionPeriod = ["calendarWeekly","monthly","quarterly"]'));
assert(app.includes('trendControl.classList.toggle("hidden", !completionVisible)'),"trend only on current calendar periods");
assert(!app.includes("QuarterRollingPreview?.rollingForecast("),"no rolling next-period forecast invocation");
assert(!app.includes("window.ForecastTrend?.build("),"no daily/month next-period forecast invocation");
assert(!app.includes("projectedRows"),"no additional future bar");
assert(!app.includes("_isForecast: true"),"no future-period dataset");
assert(!app.includes("forecastIndices"),"no extra forecast axis labels");
assert(app.includes('if (completion) {'));
assert(app.includes('periodCompletionHatchPlugin'));
assert(app.includes('stacked:Boolean(completion)'));
assert(app.includes('approvedNeonGitRelease'));
assert(app.includes('matchesDashboardGeneration'));
assert(!app.includes('netlify deploy --prod'));
console.log("CURRENT_PERIOD_COMPLETION_OFFLINE_PASS: verified source, calendar bounds, 3 modes, no future leakage, legend/stack/tooltip guards");
