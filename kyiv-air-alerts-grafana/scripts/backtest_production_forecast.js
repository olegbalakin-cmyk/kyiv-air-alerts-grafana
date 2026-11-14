#!/usr/bin/env node
/* Re-run exactly the production ForecastTrend.build() for historical daily,
   calendar weekly and monthly intervals using only independently verified
   historical city-days. No data fetch, inference shortcuts or site writes. */
"use strict";
const fs=require("node:fs"), assert=require("node:assert/strict");
const forecast=require("../pages-preview/forecast-trend.js");
const [,,input,sha,output]=process.argv;
assert(input&&/^[a-f0-9]{40}$/.test(sha)&&output);
const data=JSON.parse(fs.readFileSync(input,"utf8")),index=data.historical_daily_kpi;
const keys=data.multicity_meta.production_city_keys;
assert(keys.length===23&&index?.meta?.verified_count===23);
const MS=864e5,iso=n=>new Date(n).toISOString().slice(0,10),stamp=d=>Date.parse(d+"T00:00:00Z");
const plus=(d,n)=>iso(stamp(d)+n*MS),sum=arr=>arr.reduce((a,b)=>a+b,0);
const results=[];
for(const city of keys){
 const idx=index.cities[city];
 assert(idx.status==="verified"&&idx.counts.length===idx.daily_total_alert_duration_seconds.length);
 const validMonths=new Set(idx.verified_metric_months||[]),validDays=new Set(idx.verified_metric_days||[]);
 const observed=new Map();
 for(let i=0;i<idx.counts.length;i++){
   const date=plus(idx.start,i),a=idx.counts[i],seconds=idx.daily_total_alert_duration_seconds[i];
   if((validMonths.has(date.slice(0,7))||validDays.has(date))&&
     Number.isInteger(a)&&a>=0&&Number.isFinite(seconds)&&seconds>=0&&seconds<=86410)
     observed.set(date,{date,time:date+"T00:00:00",alerts_per_day:a,avg_daily_alert_hours:seconds/3600,alerts_started:a});
 }
 function collect(from,to){
   const out=[];
   for(let d=from;d<=to;d=plus(d,1)){const row=observed.get(d);if(!row)return null;out.push(row)}
   return out;
 }
 const end=stamp(idx.end);
 // Daily: one origin weekly per city, keep each original 28-day chart series.
 for(let t=stamp(idx.start)+28*MS;t<=end;t+=7*MS){
   const cutoff=iso(t),days=collect(plus(cutoff,-27),cutoff),truth=observed.get(plus(cutoff,1));
   if(!days||!truth)continue;
   const out=forecast.build(days,"daily28")?.forecasts?.[0];
   if(!out)continue;
   assert(out.date===truth.date);
   for(const [metric,field] of [["alerts","alerts_per_day"],["hours","avg_daily_alert_hours"]])
     results.push({city,period:"daily28",metric,date:truth.date,pred:out[field],actual:truth[field]});
 }
 const calendar={calendarWeekly:[],monthly:[]};
 // For full months, require the source's certified full-metric month, not
 // partial-month rows or fabricated zero-day values.
 for(const month of [...validMonths].sort()){
   const y=Number(month.slice(0,4)),m=Number(month.slice(5,7));
   const last=new Date(Date.UTC(y,m,0)).getUTCDate();
   const days=collect(month+"-01",month+"-"+String(last).padStart(2,"0"));
   if(days) calendar.monthly.push({
     month,time:month+"-01T00:00:00",alerts_per_day:sum(days.map(x=>x.alerts_per_day))/days.length,
     avg_daily_alert_hours:sum(days.map(x=>x.avg_daily_alert_hours))/days.length
   });
 }
 for(let t=stamp(idx.start);t<=end;t+=MS){
   const date=iso(t),day=new Date(t).getUTCDay();
   if(day!==1)continue;
   const endDay=plus(date,6);
   const days=collect(date,endDay);if(!days)continue;
   calendar.calendarWeekly.push({
     week_start:date,week_end:endDay,time:endDay+"T00:00:00",
     alerts_per_day:sum(days.map(x=>x.alerts_per_day))/7,
     avg_daily_alert_hours:sum(days.map(x=>x.avg_daily_alert_hours))/7
   });
 }
 for(const period of ["monthly","calendarWeekly"]){
   const sequence=calendar[period];
   for(let i=0;i<sequence.length-1;i++){
     const rows=sequence.slice(0,i+1),actual=sequence[i+1];
     const pred=forecast.build(rows,period)?.forecasts?.[0];if(!pred)continue;
     const knownDate=period==="monthly"?actual.month:actual.week_end;
     const predictedDate=period==="monthly"?pred.month:pred.week_end;
     if(predictedDate!==knownDate)continue;
     for(const [metric,field] of [["alerts","alerts_per_day"],["hours","avg_daily_alert_hours"]])
       results.push({city,period,metric,date:knownDate,pred:pred[field],actual:actual[field]});
   }
 }
}
const keysOut=[...new Set(results.map(x=>x.period+"|"+x.metric))].sort();
const summaries=keysOut.map(key=>{
 const [period,metric]=key.split("|"),rows=results.filter(x=>x.period===period&&x.metric===metric);
 const grouped=new Map();
 for(const row of rows){if(!grouped.has(row.city))grouped.set(row.city,[]);grouped.get(row.city).push(row)}
 const error=sum(rows.map(x=>Math.abs(x.pred-x.actual))),actual=sum(rows.map(x=>x.actual));
 const equalWapes=[...grouped.values()].map(rs=>{
  const v=sum(rs.map(x=>x.actual));return v?sum(rs.map(x=>Math.abs(x.pred-x.actual)))/v:null;
 }).filter(x=>x!==null);
 return {period,metric,n:rows.length,cities:grouped.size,wape:actual?error/actual:null,
   mae:error/rows.length,city_equal_wape:equalWapes.length?sum(equalWapes)/equalWapes.length:null};
});
assert(results.length>100,"insufficient verified physical evaluation");
const payload={meta:{source:"site-prod",sha,method:"exact production ForecastTrend.build; walk-forward and independently certified days",
  samples:results.length,verified_cities:23,
  caveat:"calendar week/month complete only; daily origins weekly to reduce dependence; WAPE is pooled, not percent per city"},summaries};
fs.mkdirSync(require("node:path").dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(payload,null,2)+"\n");
console.log("EXACT_PRODUCTION_FORECAST_BACKTEST_PASS "+JSON.stringify(payload));
