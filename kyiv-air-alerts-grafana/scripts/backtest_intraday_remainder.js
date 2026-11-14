#!/usr/bin/env node
/* Kyoto local-hour occupancy walk-forward pilot from immutable completed
   Kyiv alert intervals. No source calls; compare flat and time-of-day rates. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const [,,file,output]=process.argv;assert(file&&output,"Specify source JSON and report JSON");
const src=JSON.parse(fs.readFileSync(file,"utf8"));
assert(Array.isArray(src)&&src.length>1000,"Need real interval corpus");
const HOUR=3600000,utc=s=>Date.parse(s);
const events=[];
for(const q of src){
 const a=utc(q.start),b=utc(q.end);
 if(!Number.isFinite(a)||!Number.isFinite(b)||a>=b)continue;
 events.push([a,b]);
}
events.sort((a,b)=>a[0]-b[0]);
const merged=[];
for(const [a,b] of events){
 if(!merged.length||a>merged.at(-1)[1])merged.push([a,b]);
 else merged.at(-1)[1]=Math.max(merged.at(-1)[1],b);
}
const start=Date.parse("2024-01-01T00:00:00Z"),end=Math.min(Date.parse("2026-11-12T00:00:00Z"),Math.floor(merged.at(-1)[1]/HOUR)*HOUR);
const n=Math.floor((end-start)/HOUR);
assert(n>19000,"Need long historical series");
const fmt=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Kyiv",hour:"2-digit",hourCycle:"h23"});
const hours=new Float64Array(n),localHour=new Uint8Array(n),pref=new Float64Array(n+1);
const profS=Array.from({length:24},()=>new Float64Array(n+1));
const profN=Array.from({length:24},()=>new Uint16Array(n+1));
let cursor=0;
for(let i=0;i<n;i++){
 const a=start+i*HOUR,b=a+HOUR;
 while(cursor<merged.length&&merged[cursor][1]<=a)cursor++;
 let c=cursor,sum=0;
 while(c<merged.length&&merged[c][0]<b){sum+=Math.max(0,Math.min(b,merged[c][1])-Math.max(a,merged[c][0]));c++}
 hours[i]=sum/HOUR;
 const h=Number(fmt.format(new Date(a)));
 assert(h>=0&&h<24,"local hour");
 localHour[i]=h;pref[i+1]=pref[i]+hours[i];
 for(let j=0;j<24;j++){profS[j][i+1]=profS[j][i]+(j===h?hours[i]:0);profN[j][i+1]=profN[j][i]+(j===h?1:0)}
}
function predict(t,lead,lookback,alpha){
 const left=Math.max(0,t-lookback*24),count=t-left;
 if(count<lookback*24*.85)return null;
 const flat=(pref[t]-pref[left])/count;
 let value=0;
 for(let h=t;h<t+lead;h++){
   const hour=localHour[h],den=profN[hour][t]-profN[hour][left];
   const byHour=den?(profS[hour][t]-profS[hour][left])/den:flat;
   value+=Math.max(0,Math.min(1,alpha*byHour+(1-alpha)*flat));
 }
 return value;
}
const models=[["flat28",28,0],["flat90",90,0],["hour28_mix25",28,.25],["hour28_mix50",28,.5],["hour90_mix25",90,.25],["hour90_mix50",90,.5],["hour90",90,1]];
const leads=[1,6,12,24],records=[];
const validStart=Date.parse("2025-01-01T00:00:00Z"),split=Date.parse("2026-07-01T00:00:00Z"),validEnd=Date.parse("2026-11-01T00:00:00Z");
for(let t=0;t+24<n;t++){
 const stamp=start+t*HOUR;
 if(stamp<validStart||stamp>validEnd||t%6!==0)continue;
 const group=stamp<split?"train":"holdout";
 for(const lead of leads){
   const actual=pref[t+lead]-pref[t];
   for(const [model,look,alpha] of models){
     const pred=predict(t,lead,look,alpha);if(pred===null)continue;
     records.push({group,lead,model,pred,actual});
   }
 }
}
const summary=[];
for(const group of ["train","holdout"])for(const lead of leads)for(const [model] of models){
 const rows=records.filter(r=>r.group===group&&r.lead===lead&&r.model===model);
 if(!rows.length)continue;
 const err=rows.reduce((s,x)=>s+Math.abs(x.actual-x.pred),0);
 const total=rows.reduce((s,x)=>s+x.actual,0);
 const pred=rows.reduce((s,x)=>s+x.pred,0);
 summary.push({group,lead,model,n:rows.length,mae:err/rows.length,
  wape:total>0?err/total:null,bias:(pred-total)/rows.length,actualMean:total/rows.length,predMean:pred/rows.length});
}
const train=summary.filter(x=>x.group==="train");
const winner=leads.map(lead=>{
 const arr=train.filter(x=>x.lead===lead).sort((a,b)=>a.mae-b.mae);
 return {lead,byMae:arr[0].model,trainMae:arr[0].mae};
});
const winAll=models.map(([model])=>{
 const x=train.filter(z=>z.model===model);
 return {model,meanNormalizedMae:x.reduce((s,z)=>s+z.mae/z.lead,0)/x.length};
}).sort((a,b)=>a.meanNormalizedMae-b.meanNormalizedMae);
const payload={meta:{source:"site-prod exact Kyiv alerts_combined.json",events:src.length,union:merged.length,
  first:new Date(start).toISOString(),through:new Date(end).toISOString(),split:"2026-07-01 UTC",
  origins:"one every 6h",method:"hourly occupancy probabilities; trailing 28/90 days, no future leakage",
  caveat:"Kyiv only; correlated overlapping horizons; aggregate hourly presence, not an attack event forecast"},
 summary,winner,trainRanking:winAll};
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(payload,null,2)+"\n");
console.log("INTRADAY_BACKTEST_SUCCESS "+JSON.stringify({episodes:src.length,unions:merged.length,observations:records.length,winner,ranking:winAll}));
for(const lead of leads)console.log("HOLDOUT "+lead+"h "+JSON.stringify(summary.filter(x=>x.group==="holdout"&&x.lead===lead).map(x=>({m:x.model,n:x.n,mae:+x.mae.toFixed(3),wape:x.wape===null?null:+(100*x.wape).toFixed(1),bias:+x.bias.toFixed(3)}))));
