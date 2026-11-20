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
    return Object.freeze({...report,index:lastIndex,days,closedHours:closed,
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
  // Never show a full-period time forecast below hours already observed
  // at the exact source snapshot. Extend from that snapshot only over the
  // physically remaining time using the existing completion model's rate.
  function completionHoursPerDay(overlay,completion,midnightUtc){
    if(!overlay||!completion||typeof midnightUtc!=="function"||
       !Number.isFinite(completion.occupancyRate)||
       completion.occupancyRate<0||completion.occupancyRate>1||
       !Number.isInteger(completion.days)||completion.days<1)return null;
    const end=midnightUtc(completion.endAfter||"");
    const captured=Date.parse(overlay.capturedAt);
    if(!Number.isFinite(end)||!Number.isFinite(captured)||end<=captured)return null;
    const remaining=(end-captured)/3600000;
    if(!Number.isFinite(remaining)||remaining<0)return null;
    return (overlay.rawCombinedHours+completion.occupancyRate*remaining)/completion.days;
  }
  return Object.freeze({forChart,completionHoursPerDay});
});
