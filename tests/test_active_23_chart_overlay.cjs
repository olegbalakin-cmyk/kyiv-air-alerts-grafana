/* Overlay contract on archived C2 23-city proof. Never a second card. */
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs");
const model=require("../kyiv-air-alerts-grafana/pages-preview/active-23-chart-overlay.js");
const capture=require("../kyiv-air-alerts-grafana/pages-preview/active-23-provisional.js");
const proof=JSON.parse(fs.readFileSync(process.env.ACTIVE23_JSON,"utf8"));
const html=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/index.html","utf8");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
function makeRow(city,period){
 const p=capture.evaluate(proof,city,period==="allTime"?"month":(
  {daily28:"day",calendarWeekly:"week",monthly:"month",quarterly:"quarter"}[period]));
 assert.ok(p);
 const avg=p.closed/3600/(new Date(p.through+"T00:00Z")-new Date(p.from+"T00:00Z"))*86400000;
 // Use exact days instead of naive wall-clock milliseconds in local timezone.
 const days=Math.round((Date.parse(p.through+"T00:00:00Z")-Date.parse(p.from+"T00:00:00Z"))/86400000)+1;
 const row={is_partial_period:true,avg_daily_alert_hours:p.closed/3600/days};
 if(period==="daily28")Object.assign(row,{date:p.through,partial_through:"2026-11-20T07:49:31+02:00"});
 if(period==="calendarWeekly")Object.assign(row,{week_start:p.from,week_end:"2026-11-22",partial_through:"2026-11-20T07:49:31+02:00"});
 if(period==="monthly"||period==="allTime")Object.assign(row,{month:"2026-11",partial_through:"2026-11-19",avg_daily_alert_hours:p.closed/3600/19});
 if(period==="quarterly")Object.assign(row,{quarter_start:"2026-10-01",quarter_end:"2026-10-31",quarter_calendar_end:"2026-12-31",days_observed:31,avg_daily_alert_hours:p.closed/3600/31});
 return row;
}
test("no separate content block, one final-bar drawing plugin",()=>{
 assert.equal(html.includes('id="active23Section"'),false);
 assert.match(html,/active-23-chart-overlay\.js/);
 assert.match(app,/active23FinalBarPlugin/);
 assert.match(app,/active23Overlay\.closedHours/);
 assert.match(app,/active23FinalBar: \{overlay:active23Overlay,forecast:active23Forecast\}/);
 assert.match(app,/periodForecastDeltaHatch:[\s\S]{0,150}!active23Overlay/);
 assert.match(app,/Завершено \(Neon\)/);
 assert.match(app,/Архівний зріз джерела/);
});
test("all 22 open source captures become ONLY the final chart bar",()=>{
 for(const city of Object.keys(proof.cities)){
  for(const period of ["daily28","calendarWeekly","monthly","quarterly","allTime"]){
   const previous={date:"2026-11-19",avg_daily_alert_hours:3};
   const last=makeRow(city,period);
   const original=JSON.stringify([previous,last]);
   const o=model.forChart(proof,city,period,[previous,last]);
   assert.equal(JSON.stringify([previous,last]),original,city+" / "+period);
   if(city==="sevastopol"){assert.equal(o,null);continue}
   assert.ok(o,city+" / "+period+" rejected");
   assert.equal(o.index,1);
   assert.ok(o.provisionalHours>0);
   assert.ok(o.combinedHours>o.closedHours);
   assert.ok(Math.abs(o.rawCombinedHours-o.rawProvisionalHours-o.rawClosedHours)<0.0001);
  }
 }
});
test("strictly fail closed on unrelated/old last bars and no false current states",()=>{
 const r=makeRow("kyiv","daily28");
 assert.equal(model.forChart(proof,"kyiv","daily28",[{...r,date:"2026-11-19"}]),null);
 assert.equal(model.forChart(proof,"kyiv","daily28",[{...r,is_partial_period:false}]),null);
 assert.equal(model.forChart(proof,"kyiv","daily28",[{...r,partial_through:"2026-11-19T08:00:00+02:00"}]),null);
 assert.equal(model.forChart(proof,"kyiv","daily28",[{...r,avg_daily_alert_hours:100}]),null);
 assert.equal(model.forChart(proof,"kyiv","rolling30",[r]),null);
});
test("trend estimates future remainder only and never changes observed cap",()=>{
 const m=model.forChart(proof,"kyiv","daily28",[makeRow("kyiv","daily28")]);
 assert.ok(m);
 const comp={occupancyRate:.25,days:1,end:"2026-11-20"};
 const date=day=>Date.parse(day+"T00:00:00+02:00");
 const add=(d,n)=>new Date(Date.parse(d+"T00:00:00Z")+n*86400000).toISOString().slice(0,10);
 const forecast=model.completionHoursPerDay(m,comp,date,add);
 assert.ok(forecast>m.combinedHours && forecast<24);
 assert.equal(m.combinedHours,m.rawCombinedHours);
 assert.equal(model.completionHoursPerDay(m,{...comp,occupancyRate:1.2},date,add),null);
 assert.equal(model.completionHoursPerDay(m,{...comp,end:"2026-11-19"},date,add),null);
});


test("20 November is an actual final X-axis bar for all 23 series, not a cap on 19 November",()=>{
 const keys=Object.keys(proof.cities);
 const first="2026-10-23";
 const days=Array.from({length:28},(_,i)=>new Date(Date.parse(first+"T00:00:00Z")+i*86400000).toISOString().slice(0,10));
 assert.equal(days.at(-1),"2026-11-19");
 const cities=Object.fromEntries(keys.map(key=>[key,{
  daily28:days.map(date=>({date,time:date+"T00:00:00+02:00",
   alerts_started:0,active_alerts:0,total_alert_duration_hours:0,
   avg_active_alert_duration_minutes:null}))
 }]));
 const original=JSON.stringify(cities);
 assert.equal(model.ensureSnapshotDay(cities,proof,"2026-11-20"),true);
 assert.equal(Object.keys(cities).length,23);
 for(const key of keys){
  const rows=cities[key].daily28;
  assert.equal(rows.length,28,key);
  assert.equal(rows.at(-2).date,"2026-11-19",key);
  assert.equal(rows.at(-1).date,"2026-11-20",key);
  assert.equal(rows.at(-1).is_partial_period,true,key);
  assert.equal(rows.at(-1)._active23_test_snapshot_only,true,key);
  assert.equal(rows.at(-1).total_alert_duration_hours,0,key);
  const report=capture.evaluate(proof,key,"day");
  const expected=proof.cities[key];
  assert.equal(rows.at(-1).alerts_started,
    expected.start_at&&expected.start_at.slice(0,10)==="2026-11-19" ? 0 :
    report.hadOpen ? 1:0,key);
  const asChartRow=rows.at(-1);
  const dailyChartRow={...asChartRow,
   avg_daily_alert_hours:asChartRow.total_alert_duration_hours,
   alerts_per_day:asChartRow.alerts_started};
  const output=model.forChart(proof,key,"daily28",[...rows.slice(0,-1),dailyChartRow]);
  if(report.hadOpen){
   assert.ok(output,key+" overlay missing on November 20");
   assert.equal(output.index,27);
   assert.ok(output.combinedHours>0);
  } else assert.equal(output,null);
 }
 assert.notEqual(JSON.stringify(cities),original);
 assert.equal(model.ensureSnapshotDay(cities,proof,"2026-11-20"),true);
 assert.equal(cities.kyiv.daily28.at(-1).date,"2026-11-20");
});
test("missing or inconsistent 23-city proof never inserts invented chart dates",()=>{
 const keys=Object.keys(proof.cities),day="2026-11-19";
 const make=()=>Object.fromEntries(keys.map(k=>[k,{daily28:Array.from({length:28},(_,i)=>({
   date:new Date(Date.parse("2026-10-23T00:00:00Z")+i*86400000).toISOString().slice(0,10)
 }))}]));
 const missing=make();delete missing.sumy;
 assert.equal(model.ensureSnapshotDay(missing,proof,"2026-11-20"),false);
 const wrong=make();wrong.kyiv.daily28.at(-1).date="2026-11-18";
 assert.equal(model.ensureSnapshotDay(wrong,proof,"2026-11-20"),false);
 for(const [k,obj] of Object.entries(wrong))assert.notEqual(obj.daily28.at(-1).date,"2026-11-20",k);
 const stale=make();
 assert.equal(model.ensureSnapshotDay(stale,proof,"2026-11-21"),false);
});
test("render order: today is reconciled before city period ranges and chart creation",()=>{
 assert.match(app,/ensureSnapshotDay\([\s\S]*?state\.data\.cities,state\.active23Snapshot,snapshotDay/);
 assert.ok(app.indexOf("const didShowSnapshotDay")<app.indexOf("renderCity();",app.indexOf("async function init()")));
});
