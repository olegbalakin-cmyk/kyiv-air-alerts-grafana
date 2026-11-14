#!/usr/bin/env node
/* Read-only walk-forward backtest. Uses only the pinned production Git dashboard.
   Fully closed, independently verified daily values; no source fetch or writes. */
"use strict";
const fs=require("node:fs"), assert=require("node:assert/strict");
const [,,input,commit,output]=process.argv;
assert(input&&/^[a-f0-9]{40}$/.test(commit)&&output,"usage: backtest_period_completion.js dashboard_data.json commit output.json");
const source=JSON.parse(fs.readFileSync(input,"utf8"));
const h=source.historical_daily_kpi, cityNames=source.multicity_meta?.production_city_keys;
assert(Array.isArray(cityNames)&&cityNames.length===23&&new Set(cityNames).size===23,"23 cities from production");
assert(h?.meta?.verified_count===23,"23/23 verified history must be embedded in exact production source");
const dayMs=864e5,iso=d=>new Date(d).toISOString().slice(0,10);
const stamp=s=>Date.parse(s+"T00:00:00Z");
const shift=(s,n)=>iso(stamp(s)+n*dayMs);
const monthEnd=(y,m)=>new Date(Date.UTC(y,m,0)).getUTCDate();
const quarterName=s=>s.slice(0,4)+"-Q"+(Math.floor((Number(s.slice(5,7))-1)/3)+1);
const periodBounds=(s,kind)=>{
 const d=new Date(stamp(s)),y=d.getUTCFullYear(),m=d.getUTCMonth()+1,wd=(d.getUTCDay()+6)%7;
 if(kind==="week"){const start=shift(s,-wd);return [start,shift(start,6)]}
 if(kind==="month"){const start=s.slice(0,7)+"-01";return [start,s.slice(0,7)+"-"+String(monthEnd(y,m)).padStart(2,"0")]}
 if(kind==="quarter"){const x=1+3*Math.floor((m-1)/3),end=x+2;
   return [y+"-"+String(x).padStart(2,"0")+"-01",y+"-"+String(end).padStart(2,"0")+"-"+String(monthEnd(y,end)).padStart(2,"0")]}
 throw Error(kind);
};
const alpha=.3;
const ewma=arr=>{let v=arr[0];for(let i=1;i<arr.length;i++)v=alpha*arr[i]+(1-alpha)*v;return v};
const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
const SLICES={week:[2,4,5],month:[7,14,21],quarter:[14,30,60]};
const records=[],coverage={},skip={};
for(const name of cityNames){
 const row=h.cities?.[name];assert(row?.status==="verified","unverified city "+name);
 const start=stamp(row.start),end=stamp(row.end),counts=row.counts,secs=row.daily_total_alert_duration_seconds;
 assert(Number.isFinite(start)&&Number.isFinite(end)&&Array.isArray(counts)&&counts.length===secs?.length&&
   counts.length===Math.round((end-start)/dayMs)+1,"historical array inconsistent "+name);
 const months=new Set(row.verified_metric_months||[]),days=new Set(row.verified_metric_days||[]);
 const data=new Map();
 for(let i=0;i<counts.length;i++){const d=iso(start+i*dayMs),n=counts[i],s=secs[i];
   if(!months.has(d.slice(0,7))&&!days.has(d))continue;
   if(!Number.isInteger(n)||n<0||!Number.isFinite(s)||s<0||s>86410)continue;
   data.set(d,[n,s/3600]);
 }
 const at=(a,b)=>{const ret=[];for(let x=a;x<=b;x=shift(x,1)){const v=data.get(x);if(!v)return null;ret.push(v)}return ret};
 const earliest=row.start,latest=row.end;
 coverage[name]={verified_days:data.size,first:earliest,last:latest,verified_months:months.size,verified_recent_days:days.size};
 for(const period of Object.keys(SLICES)){
   for(let startDate=periodBounds(earliest,period)[0];startDate<=latest;){
     const [from,to]=periodBounds(startDate,period),count=Math.round((stamp(to)-stamp(from))/dayMs)+1;
     const truth=at(from,to);
     const history=at(shift(from,-28),shift(from,-1)),previousRange=periodBounds(shift(from,-1),period);
     const lastPeriod=at(...previousRange);
     if(truth){
       for(let m=0;m<2;m++){
         const actual=truth.reduce((s,a)=>s+a[m],0),metric=m?"hours":"alerts";
         if(history){
           const vals=history.map(x=>x[m]);
           const models={mean28:mean(vals),ewma03:ewma(vals),mean7:mean(vals.slice(-7))};
           if(lastPeriod)models.previous=mean(lastPeriod.map(x=>x[m]));
           if(period==="quarter"){
             // Model true quarter-level EWMA on consecutive certified
             // complete quarters before the target. No target-period data.
             const quarters=[];
             let previousEnd=shift(from,-1);
             for(let i=0;i<4;i++){
               const [qa,qb]=periodBounds(previousEnd,"quarter"),p=at(qa,qb);
               if(!p)break;
               quarters.unshift(mean(p.map(x=>x[m])));
               previousEnd=shift(qa,-1);
             }
             if(quarters.length>=2)models.quarter_ewma03=ewma(quarters);
             if(quarters.length===4)models.same_quarter_last_year=quarters[0];
           }
           for(const [model,daily] of Object.entries(models))
             records.push({city:name,period,type:"full_next",metric,lead:count,model,cutoff:shift(from,-1),
               from,to,observed:0,actual,pred:daily*count});
         }
         for(const observed of SLICES[period]){
           if(observed>=count)continue;
           const cutoff=shift(from,observed-1),trail=at(shift(cutoff,-27),cutoff);
           if(!trail)continue;
           const prior=trail.map(x=>x[m]),observedSum=truth.slice(0,observed).reduce((s,x)=>s+x[m],0);
           const currentRate=observedSum/observed,left=count-observed;
           const models={run_rate:currentRate,ewma03:ewma(prior),mean28:mean(prior),blend50:(currentRate+ewma(prior))/2};
           if(lastPeriod)models.previous=mean(lastPeriod.map(x=>x[m]));
           for(const [model,futureRate] of Object.entries(models))
             records.push({city:name,period,type:"current",metric,lead:left,model,cutoff,from,to,
               observed,actual,pred:observedSum+left*futureRate});
         }
       }
     }
     startDate=shift(to,1);
   }
 }
 // Rolling means: 1/7/14 days ahead, keeping the known overlap intact.
 for(const window of [30,90,180])for(const ahead of [1,7,14]){
   for(let t=stamp(earliest)+(window+28)*dayMs;t+ahead*dayMs<=stamp(latest);t+=7*dayMs){
     const cutoff=iso(t),old=at(shift(cutoff,1-window),cutoff),
       trail=at(shift(cutoff,-27),cutoff),future=at(shift(cutoff,1),shift(cutoff,ahead));
     if(!old||!trail||!future)continue;
     for(let m=0;m<2;m++){
       const metric=m?"hours":"alerts",retained=old.slice(ahead).reduce((v,x)=>v+x[m],0);
       const actual=retained+future.reduce((v,x)=>v+x[m],0),
         prior=trail.map(x=>x[m]),models={no_change:old.reduce((v,x)=>v+x[m],0),
           ewma03:retained+ahead*ewma(prior),mean28:retained+ahead*mean(prior)};
       for(const [model,pred] of Object.entries(models))
         records.push({city:name,period:"rolling"+window,type:"rolling",metric,lead:ahead,model,
           cutoff,from:shift(cutoff,1-window+ahead),to:shift(cutoff,ahead),
           observed:window-ahead,actual,pred});
     }
   }
 }
}
assert(records.length>1000,"need physical historical forecast samples");
const groups=new Map();
for(const row of records){
 const key=[row.period,row.type,row.metric,row.lead,row.model].join("|");
 if(!groups.has(key))groups.set(key,[]);
 groups.get(key).push(row);
}
const summaries=[...groups].map(([key,rows])=>{
 const [period,type,metric,lead,model]=key.split("|");
 const abs=rows.map(x=>Math.abs(x.actual-x.pred)),total=rows.reduce((s,x)=>s+x.actual,0),errors=abs.reduce((s,x)=>s+x,0);
 const perCity=new Map();
 for(const x of rows){if(!perCity.has(x.city))perCity.set(x.city,[]);perCity.get(x.city).push(x)}
 const cityMAE=[...perCity.values()].map(rs=>mean(rs.map(x=>Math.abs(x.pred-x.actual))));
 return {period,type,metric,lead:Number(lead),model,n:rows.length,cities:perCity.size,
   mae:errors/rows.length,city_equal_mae:mean(cityMAE),wape:total>0?errors/total:null,
   bias:mean(rows.map(x=>x.pred-x.actual)),positive:rows.filter(x=>x.actual>0).length};
}).sort((a,b)=>[a.period,a.type,a.metric,a.lead,a.model].join("|").localeCompare([b.period,b.type,b.metric,b.lead,b.model].join("|")));
const cell=new Map();
for(const x of records){
 const key=[x.city,x.period,x.type,x.metric,x.lead,x.cutoff,x.from,x.to].join("|");
 if(!cell.has(key))cell.set(key,{});
 cell.get(key)[x.model]=x;
}
const paired=new Map();
for(const c of cell.values()){
 const baseline=c.previous||c.run_rate||c.no_change;
 if(!baseline)continue;
 for(const name of ["ewma03","mean28","mean7","blend50"]){
   if(!c[name])continue;
   const row=c[name],key=[row.period,row.type,row.metric,row.lead,name,baseline.model].join("|");
   if(!paired.has(key))paired.set(key,[]);
   paired.get(key).push({city:row.city,base:Math.abs(baseline.pred-row.actual),error:Math.abs(row.pred-row.actual)});
 }
}
const comparisons=[...paired].map(([key,arr])=>{
 const [period,type,metric,lead,model,baseline]=key.split("|"),mae=mean(arr.map(x=>x.error)),base=mean(arr.map(x=>x.base));
 const cityImprovement=[...new Set(arr.map(x=>x.city))].map(c=>{
   const a=arr.filter(x=>x.city===c),m=mean(a.map(x=>x.error)),b=mean(a.map(x=>x.base));return b?1-m/b:null;
 }).filter(x=>x!==null);
 return {period,type,metric,lead:Number(lead),model,baseline,n:arr.length,cities:new Set(arr.map(x=>x.city)).size,
   mae,baseline_mae:base,improvement:base?1-mae/base:null,
   improved_cities:cityImprovement.filter(x=>x>0).length,evaluated_cities:cityImprovement.length};
}).sort((a,b)=>[a.period,a.type,a.metric,a.lead,a.model].join("|").localeCompare([b.period,b.type,b.metric,b.lead,b.model].join("|")));
// Equal-city aggregate and paired run-rate comparison. Each stage is a fixed
// number of observed days (rather than variable days remaining in a month).
const stageSummary=[];
const stages=[["week",2],["week",4],["week",5],["month",7],["month",14],["month",21],
  ["quarter",14],["quarter",30],["quarter",60]];
const stageSpecs=[...stages.map(([period,observed])=>({period,type:"current",observed})),
  ...["week","month","quarter"].map(period=>({period,type:"full_next",observed:0})),
  ...[30,90,180].flatMap(n=>[1,7,14].map(lead=>({period:"rolling"+n,type:"rolling",lead})))];
for(const spec of stageSpecs)for(const metric of ["alerts","hours"]){
  const rows=records.filter(x=>x.period===spec.period&&x.type===spec.type&&x.metric===metric&&
    (spec.lead===undefined?x.observed===spec.observed:x.lead===spec.lead));
  if(!rows.length)continue;
  const models=[...new Set(rows.map(x=>x.model))];
  const modelStats=[];
  for(const model of models){
    const x=rows.filter(v=>v.model===model);
    const total=x.reduce((s,v)=>s+v.actual,0),err=x.reduce((s,v)=>s+Math.abs(v.pred-v.actual),0);
    const perCity=new Map();
    for(const q of x){if(!perCity.has(q.city))perCity.set(q.city,[]);perCity.get(q.city).push(q)}
    const cityWape=[...perCity.values()].map(rs=>{
      const actual=rs.reduce((s,v)=>s+v.actual,0),err=rs.reduce((s,v)=>s+Math.abs(v.pred-v.actual),0);
      return actual>0?err/actual:null;
    }).filter(x=>x!==null);
    modelStats.push({model,n:x.length,cities:perCity.size,wape:total>0?err/total:null,
      mae:err/x.length,city_equal_wape:cityWape.length?mean(cityWape):null});
  }
  // Compare only common exact forecast-origin observations when evaluating
  // improvements, otherwise baseline-only sample selection would bias result.
  const keys=new Map();
  for(const x of rows){
    const k=[x.city,x.cutoff,x.from,x.to].join("|");
    if(!keys.has(k))keys.set(k,{});
    keys.get(k)[x.model]=x;
  }
  const pairs=[];
  for(const model of models.filter(x=>x!=="previous"&&x!=="run_rate"&&x!=="no_change")){
    const comparative=[...keys.values()].filter(d=>d[model]&&(d.previous||d.run_rate||d.no_change));
    if(!comparative.length)continue;
    const actualErr=comparative.reduce((s,d)=>s+Math.abs(d[model].pred-d[model].actual),0);
    const baseErr=comparative.reduce((s,d)=>s+Math.abs((d.previous||d.run_rate||d.no_change).pred-d[model].actual),0);
    pairs.push({model,baseline:comparative[0].previous?"previous":comparative[0].run_rate?"run_rate":"no_change",
      n:comparative.length,improvement_pct:baseErr>0?100*(baseErr-actualErr)/baseErr:null});
  }
  stageSummary.push({period:spec.period,type:spec.type,metric,observed_days:spec.observed??null,
    forecast_days:spec.lead??null,models:modelStats,pairs});
}
const report={
 meta:{source:"site-prod",commit,verified_cities:cityNames.length,records:records.length,
   sample_kind:"walk-forward; no future data in feature calculation",quasi_repeated:"rolling evaluation origins seven days apart are correlated",
   metrics:"MAE absolute alerts or hours in period, WAPE pooled abs error / observed total",no_source_http:true},
 coverage,summaries,comparisons,stageSummary};
fs.mkdirSync(require("node:path").dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(report,null,2)+"\n");
for(const v of stageSummary){console.log("STAGE_RESULT",JSON.stringify(v))}
console.log("BACKTEST_PASS",JSON.stringify({commit,cities:cityNames.length,records:records.length,
  groups:summaries.length,paired:comparisons.length,coverage:Object.values(coverage).map(x=>x.verified_days).reduce((a,b)=>a+b,0)}));
for(const period of ["quarter","month","week","rolling30","rolling90","rolling180"])for(const type of ["full_next","current","rolling"]){
 const a=summaries.filter(x=>x.period===period&&x.type===type&&x.metric==="hours");
 if(a.length)console.log("RESULTS",period,type,JSON.stringify(a.map(x=>({lead:x.lead,model:x.model,n:x.n,mae:+x.mae.toFixed(2),wape:x.wape==null?null:+(100*x.wape).toFixed(2)}))));
}
