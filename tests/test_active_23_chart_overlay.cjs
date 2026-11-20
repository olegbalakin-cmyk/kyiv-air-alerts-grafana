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
