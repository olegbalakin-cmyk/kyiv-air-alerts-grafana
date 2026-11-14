const assert=require("node:assert/strict");
const fs=require("node:fs");
const {quarterRows,quarterRange,quarterKey,rollingForecast,addDay}=require("../pages-preview/quarterly-rolling-preview.js");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const html=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/index.html","utf8");
const monthly=[];
function addMonth(m,days,counts,hrs) {
  monthly.push({month:m,alerts_started:counts,avg_daily_alert_hours:hrs,
    avg_alert_duration_min:counts?30:null,total_alert_duration_seconds:hrs*days*3600});
}
for(let m=1;m<=7;m++){const mm="2026-"+String(m).padStart(2,"0");const days=new Date(Date.UTC(2026,m,0)).getUTCDate();addMonth(mm,days,days,2)}
let qs=quarterRows(monthly);
assert.deepEqual(qs.map(x=>x.quarter),["2026-Q1","2026-Q2","2026-Q3"]);
assert.equal(qs[0].alerts_started,90);assert.equal(qs[1].alerts_started,91);
assert.equal(qs[2].is_partial_period,true);
assert.equal(qs[2].quarter_end,"2026-07-31");
assert.equal(qs[2].days_observed,31);
assert.equal(qs[0].avg_daily_alert_hours,2);
assert.equal(qs[0].alerts_per_day,1);
assert.equal(qs[0].avg_alert_duration_min,30);
assert.equal(quarterRows(monthly.filter(x=>x.month!=="2026-05")).some(x=>x.quarter==="2026-Q2"),false,"missing historical month excludes quarter");
assert.equal(quarterRows([...monthly,{...monthly[1]}]).some(x=>x.quarter==="2026-Q1"),false,"duplicate month must not be used");
assert.equal(quarterRows(monthly.map(x=>({...x,is_partial_period:true}))).length,0);
assert.deepEqual(quarterRange("2026-10-31"),{from:"2026-07-01",to:"2026-09-30",label:"2026-Q3"});
assert.deepEqual(quarterRange("2026-09-30"),{from:"2026-07-01",to:"2026-09-30",label:"2026-Q3"});
assert.deepEqual(quarterRange("2026-01-31"),{from:"2025-10-01",to:"2025-12-31",label:"2025-Q4"});
assert.equal(quarterKey("2024-02"),"2024-Q1");
for(const id of ["cityPeriod","comparePeriod"]){
  const match=html.match(new RegExp('<select id="'+id+'"[^>]*>([\\s\\S]*?)<\\/select>'));
  assert(match);assert(match[1].includes('value="quarterly"'));
}
assert(html.includes('id="allCitiesRange"')&&html.includes('value="quarter"'));
assert(app.includes("root.QuarterRollingPreview = api"),"preview helper inlined into app.js to survive Netlify build");
assert.equal((app.match(/_isForecast: true/g)||[]).length,0,"no next-period chart datasets");
assert(app.includes("return !data.datasets[item.datasetIndex]?._isCompletion;"),"legend excludes completion overlays");
assert(!app.includes("Boolean(context.dataset._isForecast) === forecastPoint"),"no next-period forecast tooltip");
assert(app.includes("Number.isFinite(context.parsed?.y)"),"null cannot appear as zero tooltip");
assert(!app.includes("Останній штрихований стовпчик — експериментальний прогноз на наступний період"),"no next-period description");
assert(!app.includes("The final outlined bar is an experimental forecast for the next period"),"no next-period English description");
assert(!html.includes('src="quarterly-rolling-preview.js'),"preview has no missing standalone asset");
for(const code of ["calendarQuarterOverlapsRange","periodRows(city, period)","quarterly", 
  "QuarterRollingPreview?.quarterRange","hasMissingQuarter", "approvedNeonGitRelease","matchesDashboardGeneration"]){
  assert(app.includes(code),code)
}
const first="2026-04-01",len=220,days=Array.from({length:len},(_,i)=>addDay(first,i));
const history={status:"verified",start:first,end:days.at(-1),
  counts:days.map(()=>2),daily_total_alert_duration_seconds:days.map(()=>7200),
  verified_metric_months:[...new Set(days.map(x=>x.slice(0,7)))],
  verified_metric_days:[]};
const city={daily28:days.slice(-28).map(date=>({date,alerts_started:2,total_alert_duration_hours:2}))};
for(const n of [30,90,180]){
  const rows=[{window_start:addDay(history.end,1-n),window_end:history.end,
    alerts_per_day:2,avg_daily_alert_hours:2}];
  const answer=rollingForecast(rows,"rolling"+n,history,city);
  assert(answer,"rolling"+n+" requires verified full metric history");
  assert.equal(answer.model,"EWMA_DAILY_TO_ROLLING");
  assert.equal(answer.forecasts.length,1);
  assert.equal(answer.forecasts[0].window_end,addDay(history.end,1));
  assert.equal(answer.forecasts[0].window_days,n);
  assert.equal(answer.forecasts[0].alerts_per_day,2);
  assert.equal(answer.forecasts[0].avg_daily_alert_hours,2);
  assert.equal(rollingForecast(rows,"rolling"+n,{...history,verified_metric_months:[],verified_metric_days:[]},city),null,"unverified days blocked");
  assert.equal(rollingForecast([{...rows[0],alerts_per_day:9}],"rolling"+n,history,city),null,"mismatching source window blocked");
}
const future=rollingForecast([{window_end:history.end,avg_daily_alert_hours:2,alerts_per_day:2}],
  "rolling30",history,{daily28:[...city.daily28,{date:city.daily28[0].date,alerts_started:2,total_alert_duration_hours:2}]});
assert.equal(future,null,"duplicate recent date blocked");
console.log("QUARTER_ROLLING_OFFLINE_PASS: 3 menus, calendar boundary, partial/missing/duplicate quarters, 30/90/180 next-day projection, verified fail-closed");
