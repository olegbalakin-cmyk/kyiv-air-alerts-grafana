/* Research-only exact-time completion estimate. Only source-certified intraday
   observations may advance the cutoff beyond the last verified complete day.
   No wall-clock imputation, API fetch, production write, or active-alert claim. */
(function(root,factory){
  "use strict";
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.PeriodCompletionPreview=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const MS=86400000,HOUR=3600000,MIN=Object.freeze({calendarWeekly:2,monthly:7,quarterly:30});
  const MAX_SOURCE_AGE_HOURS=8;
  const valid=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&
    Number.isFinite(Date.parse(d+"T00:00:00Z"))&&new Date(d+"T00:00:00Z").toISOString().slice(0,10)===d;
  const dayNumber=d=>Date.parse(d+"T00:00:00Z");
  const add=(d,n)=>valid(d)?new Date(dayNumber(d)+n*MS).toISOString().slice(0,10):null;
  const nDays=(a,b)=>Math.round((dayNumber(b)-dayNumber(a))/MS)+1;
  const sum=values=>values.reduce((s,x)=>s+x,0);
  const mean=values=>sum(values)/values.length;
  const ewma=values=>values.reduce((s,v,i)=>i?s*.7+v*.3:v,0);
  const clamp=(v,max)=>Math.max(0,Math.min(max,v));
  const kyivFormatter=new Intl.DateTimeFormat("en-GB",{
    timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit",
    hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"
  });
  const kyivParts=t=>{
    const parts=kyivFormatter.formatToParts(new Date(t));
    const part=name=>Number(parts.find(x=>x.type===name)?.value);
    return {year:part("year"),month:part("month"),day:part("day"),
      hour:part("hour"),minute:part("minute"),second:part("second")};
  };
  function kyivLocalDay(t){
    if(!Number.isFinite(t))return null;
    const p=kyivParts(t);
    return p.year+"-"+String(p.month).padStart(2,"0")+"-"+String(p.day).padStart(2,"0");
  }
  // Kyiv's UTC offset may change on transition days. Derive each LOCAL
  // midnight in real UTC time, so 23/25-hour DST days get correct hard caps.
  function kyivMidnightUtc(day){
    if(!valid(day))return null;
    const guess=dayNumber(day),parts=kyivParts(guess);
    const localAtGuess=Date.UTC(parts.year,parts.month-1,parts.day,
      parts.hour,parts.minute,parts.second);
    const timestamp=guess-(localAtGuess-guess);
    return kyivLocalDay(timestamp)===day&&kyivLocalDay(timestamp-1000)!==day?timestamp:null;
  }
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
  function certifiedPartial(row,today,nowTimestamp){
    if(!row||row.date!==today||row.is_partial_period!==true)return null;
    const through=row.partial_through;
    // Date-only marker means "partial, clock unknown", NOT a whole day's
    // verified calm observation. Fall back to completed days only.
    if(through===today)return null;
    if(typeof through!=="string"||
      !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(through))return false;
    const at=Date.parse(through);
    if(!Number.isFinite(at)||kyivLocalDay(at)!==today||at>nowTimestamp+120000||
       nowTimestamp-at>MAX_SOURCE_AGE_HOURS*HOUR)return false;
    const start=kyivMidnightUtc(today),end=kyivMidnightUtc(add(today,1));
    if(start===null||end===null||at<=start||at>=end)return false;
    const elapsed=(at-start)/HOUR;
    const hours=row.total_alert_duration_hours,alerts=row.alerts_started;
    if(typeof hours!=="number"||!Number.isFinite(hours)||hours<0||
       hours>elapsed+0.002||!Number.isInteger(alerts)||alerts<0)return false;
    return {at,sourceTimestamp:through,date:today,hours,alerts,elapsed,dayHours:(end-start)/HOUR,
      dayFraction:(at-start)/(end-start)};
  }
  function estimate(index,period,today,partialDay=null,nowInstant=new Date()){
    if(index?.status!=="verified"||!Object.hasOwn(MIN,period))return null;
    const info=bounds(today,period);
    if(!info||!valid(index.start)||!valid(index.end)||index.end!==add(today,-1))return null;
    const {start,end,days,key}=info,through=index.end;
    if(through<start||through>=end||start<index.start)return null;
    const completed=nDays(start,through),leftDays=days-completed;
    if(completed<MIN[period]||leftDays<1)return null;
    const totalDays=nDays(index.start,index.end);
    if(totalDays<28||totalDays>36600||
      !Array.isArray(index.counts)||!Array.isArray(index.daily_total_alert_duration_seconds)||
      index.counts.length!==totalDays||index.daily_total_alert_duration_seconds.length!==totalDays)return null;
    const verifiedMonths=new Set(index.verified_metric_months||[]);
    const verifiedDays=new Set(index.verified_metric_days||[]);
    const get=d=>{
      if(!valid(d)||d<index.start||d>index.end||
        !verifiedMonths.has(d.slice(0,7))&&!verifiedDays.has(d))return null;
      const i=nDays(index.start,d)-1,n=index.counts[i],seconds=index.daily_total_alert_duration_seconds[i];
      return Number.isInteger(n)&&n>=0&&typeof seconds==="number"&&Number.isFinite(seconds)&&
        seconds>=0&&seconds<=90010?{alerts:n,hours:seconds/3600}:null;
    };
    const actual=[],last28=[];
    for(let d=start;d<=through;d=add(d,1)){const row=get(d);if(!row)return null;actual.push(row)}
    for(let i=27;i>=0;i--){const row=get(add(through,-i));if(!row)return null;last28.push(row)}
    const nowTimestamp=nowInstant instanceof Date?nowInstant.getTime():Date.parse(nowInstant);
    if(!Number.isFinite(nowTimestamp))return null;
    // If a timestamped source exists but fails validation, show NO current
    // estimate rather than silently treating stale hours as observed calm.
    const observedPartial=certifiedPartial(partialDay,today,nowTimestamp);
    if(observedPartial===false)return null;
    let observedHours=sum(actual.map(x=>x.hours)),observedAlerts=sum(actual.map(x=>x.alerts));
    let observedDaysEquivalent=completed,remainingDaysEquivalent=leftDays;
    let cutoff=kyivMidnightUtc(today),asOf=through,asOfIsIntraday=false;
    if(observedPartial){
      observedHours+=observedPartial.hours;
      observedAlerts+=observedPartial.alerts;
      observedDaysEquivalent+=observedPartial.dayFraction;
      remainingDaysEquivalent-=observedPartial.dayFraction;
      cutoff=observedPartial.at;
      asOf=observedPartial.sourceTimestamp;
      asOfIsIntraday=true;
    }
    const periodStartUtc=kyivMidnightUtc(start),periodEndUtc=kyivMidnightUtc(add(end,1));
    if(periodStartUtc===null||periodEndUtc===null||cutoff===null||
      cutoff<periodStartUtc||cutoff>=periodEndUtc)return null;
    const maximumRemainingHours=(periodEndUtc-cutoff)/HOUR;
    const observedPhysicalHours=(cutoff-periodStartUtc)/HOUR;
    if(observedHours>observedPhysicalHours+0.01||maximumRemainingHours<=0||
       remainingDaysEquivalent<=0)return null;
    // Physical, clock-scaled occupancy baseline: estimate ONLY the real
    // hours that have not yet elapsed. Do not extrapolate today's partial
    // alarm load (or the whole quarter's past high rate) into the final hour.
    // Holdout validation in #43630913174 showed hourly curves did not
    // materially beat the simpler 28-day rate over 6/12/24-hour windows.
    const trailingA=last28.map(x=>x.alerts),trailingH=last28.map(x=>x.hours);
    const baselineStart=kyivMidnightUtc(add(through,-27));
    const baselineEnd=kyivMidnightUtc(today);
    if(baselineStart===null||baselineEnd===null||baselineEnd<=baselineStart)return null;
    const baselinePhysicalHours=(baselineEnd-baselineStart)/HOUR;
    const baselineAlertHours=sum(trailingH);
    if(!Number.isFinite(baselinePhysicalHours)||baselinePhysicalHours<24*27||
       baselineAlertHours<0||baselineAlertHours>baselinePhysicalHours+0.01)return null;
    const occupancyRate=clamp(baselineAlertHours/baselinePhysicalHours,1);
    // A physical occupancy fraction (0–1), not an attempt to hit an old
    // predicted total. The remaining alert time naturally approaches 0
    // as the verified observation cutoff approaches the calendar end.
    const remainingHours=occupancyRate*maximumRemainingHours;
    const remainingAlerts=Math.max(0,mean(trailingA)*maximumRemainingHours/24);
    const modelAlerts="mean28_per_24h",modelHours="observed_28d_hour_fraction";
    const periodRow={
      time:start+"T00:00:00",alerts_started:observedAlerts,
      avg_daily_alert_hours:observedHours/observedDaysEquivalent,
      alerts_per_day:observedAlerts/observedDaysEquivalent,
      is_partial_period:true,partial_through:asOf,
      _verified_completion_source:true
    };
    if(period==="calendarWeekly")Object.assign(periodRow,{week_start:start,week_end:end,interval_mode:"calendar_week"});
    else if(period==="monthly")Object.assign(periodRow,{month:key});
    else Object.assign(periodRow,{quarter:key,quarter_start:start,quarter_end:end,
      quarter_calendar_end:end,days_observed:completed,interval_mode:"calendar_quarter"});
    return {period,start,end,key,through,asOf,asOfIsIntraday,observed:completed,days,
      observedDaysEquivalent,remainingDaysEquivalent,left:leftDays,
      actualAlerts:observedAlerts,actualHours:observedHours,
      remainingAlerts,remainingHours,maximumRemainingHours,occupancyRate,baselinePhysicalHours,
      expectedAlerts:observedAlerts+remainingAlerts,
      expectedHours:observedHours+remainingHours,
      modelAlerts,modelHours,periodRow};
  }
  return {estimate,bounds,add,kyivMidnightUtc,kyivLocalDay,certifiedPartial};
});
