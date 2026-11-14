/* Preview-only quarter aggregation and one-day rolling-window projection. */
(function(root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.QuarterRollingPreview = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const ALPHA = 0.3, DAY_MS = 86400000;
  const WINDOWS = Object.freeze({rolling30:30, rolling90:90, rolling180:180});
  const validDay = d => typeof d==="string" && /^\d{4}-\d{2}-\d{2}$/.test(d) &&
    Number.isFinite(Date.parse(d+"T00:00:00Z")) && new Date(d+"T00:00:00Z").toISOString().slice(0,10)===d;
  const validMonth = m => typeof m==="string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(m);
  function addDay(d,n) {
    return validDay(d) ? new Date(Date.parse(d+"T00:00:00Z")+n*DAY_MS).toISOString().slice(0,10) : null;
  }
  function daysInMonth(m) {
    return validMonth(m) ? new Date(Date.UTC(+m.slice(0,4),+m.slice(5,7),0)).getUTCDate() : NaN;
  }
  function monthEnd(m) {
    const n=daysInMonth(m);
    return Number.isInteger(n) ? m+"-"+String(n).padStart(2,"0") : null;
  }
  function quarterKey(m) {
    return validMonth(m) ? m.slice(0,4)+"-Q"+(Math.floor((+m.slice(5,7)-1)/3)+1) : null;
  }
  function quarterStartMonth(key) {
    return /^\d{4}-Q[1-4]$/.test(key) ?
      key.slice(0,4)+"-"+String((+key.at(-1)-1)*3+1).padStart(2,"0") : null;
  }
  function quarterRange(lastCompleteMonthEnd) {
    if (!validDay(lastCompleteMonthEnd)) return null;
    const year=+lastCompleteMonthEnd.slice(0,4), month=+lastCompleteMonthEnd.slice(5,7);
    const startMonth=Math.floor((month-1)/3)*3+1;
    const currentEnd=monthEnd(year+"-"+String(startMonth+2).padStart(2,"0"));
    const to=lastCompleteMonthEnd>=currentEnd?currentEnd:
      addDay(year+"-"+String(startMonth).padStart(2,"0")+"-01",-1);
    if(!to)return null;
    const key=quarterKey(to.slice(0,7));
    return {from:quarterStartMonth(key)+"-01",to,label:key};
  }
  // Use complete source months only. Never invent an absent month or pad an
  // incomplete first quarter. Only the newest quarter may be partial, with a
  // visible incomplete-period flag and the exact last complete month as cutoff.
  function quarterRows(monthly) {
    if (!Array.isArray(monthly)) return [];
    const byMonth=new Map(),duplicate=new Set();
    for(const row of monthly) {
      const m=row?.month || String(row?.time||"").slice(0,7);
      if(!validMonth(m)||row?.is_partial_period===true)continue;
      if(byMonth.has(m))duplicate.add(m);
      else byMonth.set(m,row);
    }
    const months=[...byMonth.keys()].filter(m=>!duplicate.has(m)).sort();
    if(!months.length)return [];
    const newestQuarter=quarterKey(months.at(-1));
    const result=[];
    for(const key of [...new Set(months.map(quarterKey))].sort()) {
      const first=quarterStartMonth(key),year=+first.slice(0,4),base=+first.slice(5,7);
      const expected=[0,1,2].map(i=>year+"-"+String(base+i).padStart(2,"0"));
      const count=expected.filter(m=>byMonth.has(m)&&!duplicate.has(m)).length;
      const partial=key===newestQuarter&&count>0&&count<3;
      if(count!==3&&!partial)continue;
      const used=expected.slice(0,count);
      if(used.some(m=>!byMonth.has(m)||duplicate.has(m)))continue;
      const days=used.reduce((n,m)=>n+daysInMonth(m),0);
      let alerts=0,hours=0,weightedDuration=0,durationCount=0,ok=true;
      for(const m of used) {
        const row=byMonth.get(m),n=row?.alerts_started,h=row?.avg_daily_alert_hours,d=row?.avg_alert_duration_min;
        if(!Number.isInteger(n)||n<0||typeof h!=="number"||!Number.isFinite(h)||h<0||h>24||
          n>0&&(typeof d!=="number"||!Number.isFinite(d)||d<0)){ok=false;break}
        const seconds=row.total_alert_duration_seconds;
        const monthHours=typeof seconds==="number"&&Number.isFinite(seconds)&&seconds>=0?
          seconds/3600:h*daysInMonth(m);
        if(monthHours<0||monthHours>daysInMonth(m)*24+0.02){ok=false;break}
        alerts+=n;hours+=monthHours;
        if(n>0){weightedDuration+=n*d;durationCount+=n}
      }
      if(!ok||!days)continue;
      const observedEnd=monthEnd(used.at(-1));
      result.push({
        quarter:key,quarter_start:first+"-01",quarter_end:observedEnd,
        quarter_calendar_end:monthEnd(expected[2]),
        time:first+"-01T00:00:00",days_observed:days,alerts_started:alerts,
        avg_daily_alert_hours:hours/days,alerts_per_day:alerts/days,
        avg_alert_duration_min:durationCount?weightedDuration/durationCount:null,
        total_alert_duration_hours:hours,is_partial_period:partial,
        partial_through:partial?observedEnd:null,interval_mode:"calendar_quarter"
      });
    }
    return result;
  }
  function ewmaDay(rows,field) {
    let level=null;
    for(const row of rows){
      const v=row[field];
      if(typeof v!=="number"||!Number.isFinite(v)||v<0)return null;
      level=level===null?v:ALPHA*v+(1-ALPHA)*level;
    }
    return level;
  }
  function rollingForecast(rows,period,history,city) {
    const n=WINDOWS[period];
    if(!n||!Array.isArray(rows)||!rows.length||history?.status!=="verified")return null;
    const anchor=rows.at(-1);
    const end=anchor?.window_end || String(anchor?.time||"").slice(0,10);
    if(!validDay(end)||anchor?.is_partial_period||!validDay(history.start)||!validDay(history.end))return null;
    const totalDays=Math.round((Date.parse(history.end+"T00:00:00Z")-
      Date.parse(history.start+"T00:00:00Z"))/DAY_MS)+1;
    if(totalDays<1||totalDays>36600||!Array.isArray(history.counts)||
      !Array.isArray(history.daily_total_alert_duration_seconds)||
      history.counts.length!==totalDays||history.daily_total_alert_duration_seconds.length!==totalDays)return null;
    const verifiedMonths=new Set(history.verified_metric_months||[]);
    const verifiedDays=new Set(history.verified_metric_days||[]);
    const recent=new Map();
    for(const row of city?.daily28||[]) {
      if(!validDay(row.date)||recent.has(row.date))return null;
      recent.set(row.date,row);
    }
    function daily(day) {
      const live=recent.get(day);
      let actual=null;
      if(day>=history.start&&day<=history.end) {
        if(!verifiedMonths.has(day.slice(0,7))&&!verifiedDays.has(day))return null;
        const i=Math.round((Date.parse(day+"T00:00:00Z")-Date.parse(history.start+"T00:00:00Z"))/DAY_MS);
        const count=history.counts[i],seconds=history.daily_total_alert_duration_seconds[i];
        if(!Number.isInteger(count)||count<0||typeof seconds!=="number"||
          !Number.isFinite(seconds)||seconds<0||seconds>86410)return null;
        actual={date:day,alerts:count,hours:seconds/3600};
      }
      if(live&&!live.is_partial_period) {
        const count=live.alerts_started,hours=live.total_alert_duration_hours;
        if(!Number.isInteger(count)||count<0||typeof hours!=="number"||
          !Number.isFinite(hours)||hours<0||hours>24.01)return null;
        if(actual&&(actual.alerts!==count||Math.abs(actual.hours-hours)>0.002))return null;
        if(!actual)actual={date:day,alerts:count,hours};
      }
      return actual;
    }
    const first=addDay(end,1-n);
    if(!first)return null;
    const dailyRows=[];
    for(let i=0;i<n;i++) {
      const row=daily(addDay(first,i));
      if(!row)return null;
      dailyRows.push(row);
    }
    const actualAlerts=dailyRows.reduce((sum,row)=>sum+row.alerts,0);
    const actualHours=dailyRows.reduce((sum,row)=>sum+row.hours,0);
    if(typeof anchor.avg_daily_alert_hours!=="number"||
      typeof anchor.alerts_per_day!=="number"||
      Math.abs(actualHours/n-anchor.avg_daily_alert_hours)>0.05||
      Math.abs(actualAlerts/n-anchor.alerts_per_day)>0.05)return null;
    const tail=dailyRows.slice(-28);
    const futureDayHours=ewmaDay(tail,"hours"),futureDayAlerts=ewmaDay(tail,"alerts");
    if(futureDayHours===null||futureDayAlerts===null)return null;
    const next=addDay(end,1);
    return {
      alpha:ALPHA,model:"EWMA_DAILY_TO_ROLLING",completedPeriods:n,excludedIncompletePeriods:0,
      forecasts:[{
        time:next+"T00:00:00",window_start:addDay(next,1-n),window_end:next,window_days:n,
        is_forecast:true,
        avg_daily_alert_hours:Math.max(0,Math.min(24,
          (actualHours-dailyRows[0].hours+Math.max(0,Math.min(24,futureDayHours)))/n)),
        alerts_per_day:Math.max(0,(actualAlerts-dailyRows[0].alerts+
          Math.max(0,futureDayAlerts))/n)
      }]
    };
  }
  return {quarterRows,quarterRange,quarterKey,rollingForecast,addDay,daysInMonth,monthEnd};
});
