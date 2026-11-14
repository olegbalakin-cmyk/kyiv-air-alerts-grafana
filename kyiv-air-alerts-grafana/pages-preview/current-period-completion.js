/* Research-only, verified-day partial-calendar-period completion estimate.
   Requires exact same-generation source; never anticipates alerts or overrides
   historical observations. No source fetches, production writes, or live status. */
(function(root,factory){
  "use strict";
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.PeriodCompletionPreview=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const MS=86400000,MIN=Object.freeze({calendarWeekly:2,monthly:7,quarterly:30});
  const valid=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&
    Number.isFinite(Date.parse(d+"T00:00:00Z"))&&new Date(d+"T00:00:00Z").toISOString().slice(0,10)===d;
  const dayNumber=d=>Date.parse(d+"T00:00:00Z");
  const add=(d,n)=>valid(d)?new Date(dayNumber(d)+n*MS).toISOString().slice(0,10):null;
  const nDays=(a,b)=>Math.round((dayNumber(b)-dayNumber(a))/MS)+1;
  const sum=values=>values.reduce((s,x)=>s+x,0);
  const mean=values=>sum(values)/values.length;
  const ewma=values=>values.reduce((s,v,i)=>i?s*.7+v*.3:v,0);
  const clamp=(v,max)=>Math.max(0,Math.min(max,v));
  function bounds(today,period){
    if(!valid(today)||!Object.hasOwn(MIN,period))return null;
    const d=new Date(dayNumber(today)),year=d.getUTCFullYear(),month=d.getUTCMonth()+1;
    if(period==="calendarWeekly"){
      const monday=add(today,-((d.getUTCDay()+6)%7));
      return {start:monday,end:add(monday,6),key:add(monday,6),days:7};
    }
    const firstMonth=period==="quarterly"?1+3*Math.floor((month-1)/3):month;
    const lastMonth=period==="quarterly"?firstMonth+2:month;
    const lastDay=new Date(Date.UTC(year,lastMonth,0)).getUTCDate();
    const start=year+"-"+String(firstMonth).padStart(2,"0")+"-01";
    const end=year+"-"+String(lastMonth).padStart(2,"0")+"-"+String(lastDay).padStart(2,"0");
    return {start,end,days:nDays(start,end),
      key:period==="quarterly"?String(year)+"-Q"+Math.ceil(month/3):start.slice(0,7)};
  }
  function estimate(index,period,today){
    if(index?.status!=="verified"||!Object.hasOwn(MIN,period))return null;
    const periodInfo=bounds(today,period);
    if(!periodInfo||!valid(index.start)||!valid(index.end)||index.end!==add(today,-1))return null;
    const {start,end,days,key}=periodInfo,through=index.end;
    if(through<start||through>=end||start<index.start)return null;
    const observed=nDays(start,through),left=days-observed;
    if(observed<MIN[period]||left<1)return null;
    const totalDays=nDays(index.start,index.end);
    if(totalDays<28||totalDays>36600||
      !Array.isArray(index.counts)||!Array.isArray(index.daily_total_alert_duration_seconds)||
      index.counts.length!==totalDays||index.daily_total_alert_duration_seconds.length!==totalDays)return null;
    const verifiedMonths=new Set(index.verified_metric_months||[]);
    const verifiedDays=new Set(index.verified_metric_days||[]);
    const get=d=>{
      if(!valid(d)||d<index.start||d>index.end||
        !verifiedMonths.has(d.slice(0,7))&&!verifiedDays.has(d))return null;
      const i=nDays(index.start,d)-1,n=index.counts[i],s=index.daily_total_alert_duration_seconds[i];
      return Number.isInteger(n)&&n>=0&&typeof s==="number"&&Number.isFinite(s)&&s>=0&&s<=86410
        ?{alerts:n,hours:s/3600}:null;
    };
    const actual=[],last28=[];
    for(let d=start;d<=through;d=add(d,1)){const row=get(d);if(!row)return null;actual.push(row)}
    for(let i=27;i>=0;i--){const row=get(add(through,-i));if(!row)return null;last28.push(row)}
    const totalAlerts=sum(actual.map(x=>x.alerts)),totalHours=sum(actual.map(x=>x.hours));
    const trailingA=last28.map(x=>x.alerts),trailingH=last28.map(x=>x.hours);
    const rateA=totalAlerts/observed,rateH=totalHours/observed;
    const trailingMeanA=mean(trailingA),trailingMeanH=mean(trailingH);
    const lastEwmaA=ewma(trailingA),lastEwmaH=ewma(trailingH);
    let modelAlerts="mean28",modelHours="mean28";
    let rateFutureAlerts=trailingMeanA,rateFutureHours=trailingMeanH;
    if(period==="monthly"&&observed>=14&&observed<21){
      modelAlerts=modelHours="blend50";
      rateFutureAlerts=(rateA+lastEwmaA)/2;
      rateFutureHours=(rateH+lastEwmaH)/2;
    }else if(period==="monthly"&&observed>=21){
      modelHours="run_rate";
      rateFutureHours=rateH;
    }else if(period==="quarterly"){
      modelAlerts=modelHours="run_rate";
      rateFutureAlerts=rateA;rateFutureHours=rateH;
      if(observed>=60){modelHours="blend50";rateFutureHours=(rateH+lastEwmaH)/2}
    }
    rateFutureAlerts=Math.max(0,rateFutureAlerts);
    rateFutureHours=clamp(rateFutureHours,24);
    const remainingAlerts=left*rateFutureAlerts,remainingHours=left*rateFutureHours;
    const periodRow={
      time:start+"T00:00:00",
      alerts_started:totalAlerts,
      avg_daily_alert_hours:totalHours/observed,
      alerts_per_day:totalAlerts/observed,
      is_partial_period:true,partial_through:through,
      _verified_completion_source:true
    };
    if(period==="calendarWeekly")Object.assign(periodRow,{week_start:start,week_end:end,interval_mode:"calendar_week"});
    else if(period==="monthly")Object.assign(periodRow,{month:key});
    else Object.assign(periodRow,{quarter:key,quarter_start:start,quarter_end:end,
      quarter_calendar_end:end,days_observed:observed,interval_mode:"calendar_quarter"});
    return {period,start,end,key,through,observed,days,left,
      actualAlerts:totalAlerts,actualHours:totalHours,
      remainingAlerts,remainingHours,
      expectedAlerts:totalAlerts+remainingAlerts,
      expectedHours:totalHours+remainingHours,
      modelAlerts,modelHours,periodRow};
  }
  return {estimate,bounds,add};
});
