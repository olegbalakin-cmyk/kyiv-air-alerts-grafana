/* UI-only overlay model for the final factual bar.
   No extra panel, no mutation of source rows, no live-status inference. */
(function(root,factory){
  "use strict";
  const api=factory();
  if(root)root.Active23ChartOverlay=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const DAY=86400000, TOLERANCE_SECONDS=150;
  const supported=Object.freeze({
    daily28:"day",calendarWeekly:"week",monthly:"month",
    allTime:"month",quarterly:"quarter"
  });
  const countDays=(start,end)=>{
    const from=Date.parse(start+"T00:00:00Z"),to=Date.parse(end+"T00:00:00Z");
    return Number.isFinite(from)&&Number.isFinite(to)&&to>=from
      ? Math.round((to-from)/DAY)+1 : 0;
  };
  function matchesRow(row,period,report){
    if(!row||row.is_partial_period!==true)return false;
    if(period==="daily28")return row.date===report.through;
    if(period==="calendarWeekly")return row.week_start===report.from&&
      row.week_end>=report.through;
    if(period==="monthly"||period==="allTime")
      return row.month===report.through.slice(0,7);
    if(period==="quarterly")
      return row.quarter_start===report.from&&
        row.quarter_end<report.through&&row.quarter_calendar_end>=report.through;
    return false;
  }
  function forChart(snapshot,key,period,rows){
    if(!Object.hasOwn(supported,period)||!Array.isArray(rows)||!rows.length||
       typeof key!=="string")return null;
    const report=globalEvaluator(snapshot,key,supported[period]);
    if(!report||!report.hadOpen||!(report.open>0)||!(report.closed>=0)||
       !(report.total>0)||!report.archival)return null;
    const lastIndex=rows.length-1,row=rows[lastIndex];
    if(!matchesRow(row,period,report))return null;
    // A date-only stale/cross-generation frame must never acquire today's
    // provisional hours from an unrelated snapshot.
    if(row.partial_through&&row.partial_through.includes("T")&&
       Math.abs(Date.parse(row.partial_through)-Date.parse(report.capturedAt))>4*3600000)
      return null;
    const days=countDays(report.from,report.through);
    if(days<1||days>100)return null;
    const observed=Number(row.avg_daily_alert_hours);
    if(!Number.isFinite(observed)||observed<0)return null;
    // Source row must be the same exact C2 generation. The monthly row
    // excludes today's unfinished day; calendar week includes it. The Q4
    // source chart intentionally ends at the last *complete* month, so only
    // check its immutable row structure, not an Oct-only mean against Oct+Nov.
    if(period==="daily28"||period==="calendarWeekly"){
      if(Math.abs(observed*days*3600-report.closed)>TOLERANCE_SECONDS)return null;
    }
    if(period==="monthly"||period==="allTime"){
      const finished=countDays(report.from,
        row.partial_through&&row.partial_through.length===10
          ? row.partial_through : report.through);
      if(!finished||finished>days)return null;
      if(Math.abs(observed*finished*3600-report.closed)>TOLERANCE_SECONDS)return null;
    }
    if(period==="quarterly"&&
       (!Number.isInteger(row.days_observed)||row.days_observed<1||
        row.days_observed>=days))return null;
    const closed=report.closed/3600/days,open=report.open/3600/days,total=closed+open;
    if(![closed,open,total].every(Number.isFinite)||closed<0||open<=0||
       total>26+0.02)return null;
    const source=snapshot.cities[key];
    const unclosedStartsToday=period==="daily28"&&source?.start_at&&
      localDay(source.start_at)===report.through?1:0;
    return Object.freeze({...report,index:lastIndex,days,unclosedStartsToday,closedHours:closed,
      provisionalHours:open,combinedHours:total,rawClosedHours:report.closed/3600,
      rawProvisionalHours:report.open/3600,rawCombinedHours:report.total/3600});
  }
  function globalEvaluator(snapshot,key,period){
    if(typeof window!=="undefined"){
      return window.Active23Provisional?.evaluate(snapshot,key,period)||null;
    }
    if(typeof module==="object"&&module.exports){
      const provisional=require("./active-23-provisional.js");
      return provisional.evaluate(snapshot,key,period);
    }
    return null;
  }
  // Ensure the source-certified snapshot day has an actual X-axis row.
  // Real C2 dashboard daily28 contains 28 COMPLETED days (through Nov 19 in
  // this frozen run). The source snapshot for Nov 20 cannot be drawn onto Nov 19.
  // Prefer an exact same-run partial row provided by the existing site-derived
  // generator. Only synthesize a preview-only zero-completed-time row if the
  // exact C2 source proof confirms zero completed time for that day.
  const addDay=(date,n)=>{
    const t=Date.parse(date+"T00:00:00Z");
    return Number.isFinite(t)?new Date(t+n*DAY).toISOString().slice(0,10):null;
  };
  const localDay=instant=>{
    const parts=new Intl.DateTimeFormat("en-GB",{
      timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit"
    }).formatToParts(new Date(instant));
    const f=type=>parts.find(p=>p.type===type)?.value;
    return f("year")+"-"+f("month")+"-"+f("day");
  };
  function ensureSnapshotDay(cities,snapshot,today){
    if(!cities||!snapshot||typeof today!=="string"||
       !/^\d{4}-\d{2}-\d{2}$/.test(today)||
       !snapshot.cities||Object.keys(cities).length!==23||
       Object.keys(snapshot.cities).length!==23)return false;
    const keys=Object.keys(cities),next=new Map();
    for(const key of keys){
      const base=cities[key]?.daily28;
      const proof=globalEvaluator(snapshot,key,"day");
      if(!Array.isArray(base)||base.length!==28||!proof||
         proof.through!==today||proof.from!==today||
         !proof.archival||localDay(proof.capturedAt)!==today||
         !Number.isFinite(proof.closed)||proof.closed<0||
         !Number.isFinite(proof.open)||proof.open<0||
         !Object.hasOwn(snapshot.cities,key))return false;
      const last=base.at(-1)?.date,previous=addDay(today,-1);
      if(last!==today && last!==previous)return false;
      const prev=last===today?base.slice(0,-1):base;
      if(prev.slice(-27).length!==27||
         prev.slice(-27).some((row,i)=>
           row?.date!==addDay(today,i-27)))return false;
      if(last===today){
        const actual=base.at(-1);
        if(actual.is_partial_period!==true||
           !Number.isFinite(Number(actual.total_alert_duration_hours))||
           Math.abs(Number(actual.total_alert_duration_hours)*3600-proof.closed)>150)
          return false;
        next.set(key,null); // already correctly attached by same-run generator
      }else{
        // In particular no green-line zero can be invented when completed
        // source-start counts are unknown: this fallback is only for the
        // exact zero-completed time in the frozen C2 snapshot.
        if(proof.closed!==0)return false;
        const row={
          time:today+"T00:00:00+02:00",
          date:today,
          // Started-count semantics: a source-proven open alert beginning
          // on this date counts once even without an all-clear.
          alerts_started:proof.hadOpen&&
            localDay(snapshot.cities[key].start_at)===today?1:0,
          active_alerts:proof.hadOpen?1:0,
          total_alert_duration_minutes:0,total_alert_duration_hours:0,
          avg_alert_duration_minutes:null,avg_active_alert_duration_minutes:null,
          is_partial_period:true,partial_through:proof.capturedAt,
          _active23_test_snapshot_only:true
        };
        next.set(key,[...prev.slice(-27),row]);
      }
    }
    // All-or-nothing across 23. No Neon or downloaded source records mutated.
    for(const [key,rows] of next)if(rows)cities[key].daily28=rows;
    return true;
  }

  // Never show a full-period time forecast below hours already observed
  // at the exact source snapshot. Extend from that snapshot only over the
  // physically remaining time using the existing completion model's rate.
  function completionHoursPerDay(overlay,completion,midnightUtc,nextDay){
    if(!overlay||!completion||typeof midnightUtc!=="function"||
       typeof nextDay!=="function"||!Number.isFinite(completion.occupancyRate)||
       completion.occupancyRate<0||completion.occupancyRate>1||
       !Number.isInteger(completion.days)||completion.days<1||
       !/^\d{4}-\d{2}-\d{2}$/.test(completion.end||""))return null;
    const after=nextDay(completion.end,1);
    const end=after?midnightUtc(after):null;
    const captured=Date.parse(overlay.capturedAt);
    if(!Number.isFinite(end)||!Number.isFinite(captured)||end<=captured)return null;
    const remaining=(end-captured)/3600000;
    if(!Number.isFinite(remaining)||remaining<0)return null;
    // This is a research estimate of *remaining time only*, not a claim
    // that an unfinished alarm lasts until the model's forecast endpoint.
    const projected=(overlay.rawCombinedHours+completion.occupancyRate*remaining)/completion.days;
    return Number.isFinite(projected)&&projected>=overlay.combinedHours ? projected:null;
  }
  return Object.freeze({forChart,completionHoursPerDay,ensureSnapshotDay});
});
