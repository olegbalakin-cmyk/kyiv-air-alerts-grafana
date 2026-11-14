const assert=require("node:assert/strict"),fs=require("node:fs");
const F=require("../pages-preview/current-period-completion.js");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const end="2026-11-13",start="2026-07-01",days=F.bounds(end,"quarterly");
assert.deepEqual(F.bounds("2026-11-14","quarterly"),{start:"2026-10-01",end:"2026-12-31",days:92,key:"2026-Q4"});
assert.equal(F.bounds("2026-11-14","calendarWeekly").start,"2026-11-09");
assert.equal(F.bounds("2026-11-14","calendarWeekly").end,"2026-11-15");
assert.equal(F.bounds("2026-11-14","monthly").end,"2026-11-30");
assert.equal(F.bounds("2026-01-01","quarterly").end,"2026-03-31");
const n=Math.round((Date.parse(end)-Date.parse(start))/86400000)+1;
const dates=Array.from({length:n},(_,i)=>F.add(start,i));
const history={status:"verified",start,end,counts:dates.map(()=>2),
daily_total_alert_duration_seconds:dates.map(()=>7200),
verified_metric_months:[...new Set(dates.map(d=>d.slice(0,7)))],
verified_metric_days:[]};
for(const mode of ["calendarWeekly","monthly","quarterly"]){
 const z=F.estimate(history,mode,"2026-11-14");
 assert(z,mode);assert(z.observed>=({calendarWeekly:2,monthly:7,quarterly:30}[mode]));
 assert(z.left>0&&z.days===z.left+z.observed);
 assert.equal(z.expectedAlerts,z.days*2);
 assert(Math.abs(z.expectedHours-z.actualHours-z.remainingHours)<1e-9);
 assert(z.occupancyRate>=0&&z.occupancyRate<=1,"historical occupancy is a probability");
 assert(z.remainingHours<=z.maximumRemainingHours+1e-9,"physical period remainder cap");
 assert.equal(z.periodRow.is_partial_period,true);
 assert.equal(z.periodRow.partial_through,"2026-11-13");
 assert.equal(z.periodRow.alerts_started,z.actualAlerts);
}
assert.equal(F.estimate({...history,status:"unverified"},"quarterly","2026-11-14"),null);
assert.equal(F.estimate({...history,end:"2026-11-12"},"quarterly","2026-11-14"),null);
assert.equal(F.estimate({...history,verified_metric_months:[],verified_metric_days:[]},"monthly","2026-11-14"),null);
assert.equal(F.estimate({...history,counts:[...history.counts.slice(0,-1),-1]},"monthly","2026-11-14"),null);
assert.equal(F.estimate(history,"quarterly","2026-10-14"),null); // 13 complete days, threshold 30
assert.equal(F.estimate(history,"calendarWeekly","2026-11-10"),null); // index is not yesterday

// Exact source-observed clock: 23:00 Kyiv means only one hour remains
// in the last calendar day, even with 24h/day model expectations.
assert.equal((F.kyivMidnightUtc("2026-03-30")-F.kyivMidnightUtc("2026-03-29"))/3600000,23,
  "DST spring-forward is 23 real hours");
assert.equal((F.kyivMidnightUtc("2026-10-26")-F.kyivMidnightUtc("2026-10-25"))/3600000,25,
  "DST fall-back is 25 real hours");
const endMonth="2026-11-29",mStart="2026-09-01",mN=Math.round((Date.parse(endMonth)-Date.parse(mStart))/86400000)+1;
const mDates=Array.from({length:mN},(_,i)=>F.add(mStart,i));
const monthIndex={status:"verified",start:mStart,end:endMonth,counts:mDates.map(()=>2),
 daily_total_alert_duration_seconds:mDates.map(()=>7200),
 verified_metric_months:[...new Set(mDates.map(d=>d.slice(0,7)))],verified_metric_days:[]};
const late={date:"2026-11-30",is_partial_period:true,
 partial_through:"2026-11-30T23:00:00+02:00",
 total_alert_duration_hours:0,alerts_started:0};
const early={...late,partial_through:"2026-11-30T09:00:00+02:00"};
const lateResult=F.estimate(monthIndex,"monthly","2026-11-30",late,"2026-11-30T23:02:00+02:00");
const earlyResult=F.estimate(monthIndex,"monthly","2026-11-30",early,"2026-11-30T09:02:00+02:00");
assert(lateResult&&earlyResult,"both fresh certified cutoffs must be supported");
assert.equal(lateResult.asOfIsIntraday,true);
assert.equal(lateResult.maximumRemainingHours,1);
assert.equal(earlyResult.maximumRemainingHours,15);
assert(lateResult.remainingHours<=1+1e-12,"late-day physical limit");
assert(lateResult.remainingHours<earlyResult.remainingHours,
  "quiet 23:00 observation must reduce estimate vs quiet 09:00");
assert.equal(lateResult.actualHours,29*2);
assert(lateResult.remainingDaysEquivalent>0&&lateResult.remainingDaysEquivalent<1/20,
  "last-day remaining is fractional");
assert.equal(lateResult.periodRow.partial_through,late.partial_through);
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",
 {...late,partial_through:"2026-11-30"}, "2026-11-30T23:02:00+02:00").asOfIsIntraday,false,
 "date-only source is not treated as time-aware evidence");
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",late,"2026-12-01T09:05:00+02:00"),null,
 "stale source clock must block estimate");
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",
 {...late,total_alert_duration_hours:23.5},"2026-11-30T23:02:00+02:00"),null,
 "impossible hours before clock must be blocked");
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",
 {...late,partial_through:"2026-11-30T23:00:00Z"},"2026-11-30T23:02:00+02:00"),null,
 "source timestamp with incorrect local date must be blocked");
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",
 {...late,partial_through:"2026-11-30T23:30:00+02:00"},"2026-11-30T23:00:00+02:00"),null,
 "future timestamp must be blocked");
assert.equal(F.estimate(monthIndex,"monthly","2026-11-30",null,
 "2026-11-30T23:02:00+02:00").asOfIsIntraday,false,
 "missing exact clock keeps completed-days-only estimate");


assert(lateResult.occupancyRate>=0&&lateResult.occupancyRate<=1);
assert(Math.abs(lateResult.remainingHours-lateResult.occupancyRate*lateResult.maximumRemainingHours)<1e-10);
assert(Math.abs(earlyResult.remainingHours-earlyResult.occupancyRate*earlyResult.maximumRemainingHours)<1e-10);
assert.equal(lateResult.occupancyRate,earlyResult.occupancyRate,
  "remaining-hour intensity must not increase to meet an old period total");
assert(lateResult.remainingHours<=1,"one hour remains at 23:00");
assert(Math.abs(earlyResult.remainingHours/lateResult.remainingHours-15)<1e-6,
  "09:00 to 23:00 forecast scales exactly with time remaining");
const highCurrent={...late,total_alert_duration_hours:22};
const highResult=F.estimate(monthIndex,"monthly","2026-11-30",highCurrent,
  "2026-11-30T23:02:00+02:00");
assert(highResult&&Math.abs(highResult.remainingHours-lateResult.remainingHours)<1e-10,
  "a high partial-day load does not imply a 100-percent-alert final hour");
assert.equal(highResult.actualHours-lateResult.actualHours,22,
  "observed alert hours are still fully counted as fact");
assert.equal(highResult.modelHours,"observed_28d_hour_fraction");
assert.equal(lateResult.modelHours,"observed_28d_hour_fraction");

// Last of 28 days: observed partial day and forecasted remainder are separate,
// with source time verification. The same observed day is never duplicated.
const partialToday={date:"2026-11-14",is_partial_period:true,
 partial_through:"2026-11-14T21:00:00+02:00",
 total_alert_duration_hours:1,alerts_started:1};
const todayForecast=F.estimateToday(history,"2026-11-14",partialToday,"2026-11-14T21:02:00+02:00");
assert(todayForecast,"timestamped current-day source supports one-bar completion");
assert.equal(todayForecast.days,1);
assert.equal(todayForecast.start,"2026-11-14");
assert.equal(todayForecast.end,"2026-11-14");
assert.equal(todayForecast.maximumRemainingHours,3);
assert.equal(todayForecast.actualHours,1);
assert.equal(todayForecast.actualAlerts,1);
assert(todayForecast.remainingHours>=0&&todayForecast.remainingHours<3);
assert(Math.abs(todayForecast.expectedHours-(1+todayForecast.remainingHours))<1e-9);
assert.equal(todayForecast.periodRow.date,"2026-11-14");
assert.equal(todayForecast.periodRow.total_alert_duration_hours,1);
assert.equal(todayForecast.periodRow.partial_through,partialToday.partial_through);
assert.equal(todayForecast.modelHours,"observed_28d_hour_fraction");
assert.equal(F.estimateToday(history,"2026-11-14",{...partialToday,partial_through:"2026-11-14"},"2026-11-14T21:02:00+02:00"),null,
 "date-only marker must not count as elapsed 21 hours");
assert.equal(F.estimateToday(history,"2026-11-14",partialToday,"2026-11-15T06:02:00+02:00"),null,
 "stale source must not become false calm time");
assert.equal(F.estimateToday(history,"2026-11-14",{...partialToday,total_alert_duration_hours:23},"2026-11-14T21:02:00+02:00"),null,
 "physically impossible current-day alert hours blocked");
assert.equal(F.estimateToday({...history,end:"2026-11-12"},"2026-11-14",partialToday,"2026-11-14T21:02:00+02:00"),null,
 "requires a completed yesterday");
assert.equal(F.estimateToday({...history,verified_metric_months:[],verified_metric_days:[]},"2026-11-14",partialToday,"2026-11-14T21:02:00+02:00"),null,
 "requires verified 28-day baseline");

assert(app.includes('window.PeriodCompletionPreview?.estimate('));
assert(app.includes('const completionPeriod = ["daily28","calendarWeekly","monthly","quarterly"]'));
assert(app.includes("window.PeriodCompletionPreview?.estimateToday("),"daily chart uses verified current day");
assert(app.includes('trendControl.classList.toggle("hidden", !completionVisible)'),"trend only on current calendar periods");
assert(!app.includes("QuarterRollingPreview?.rollingForecast("),"no rolling next-period forecast invocation");
assert(!app.includes("window.ForecastTrend?.build("),"no daily/month next-period forecast invocation");
assert(!app.includes("projectedRows"),"no additional future bar");
assert(!app.includes("_isForecast: true"),"no future-period dataset");
assert(!app.includes("forecastIndices"),"no extra forecast axis labels");
assert(app.includes('if (completion) {'));
assert(app.includes('periodCompletionHatchPlugin'));
assert(app.includes('stacked:Boolean(completion)'));
assert(app.includes('approvedNeonGitRelease'));
assert(app.includes('matchesDashboardGeneration'));
assert(!app.includes('netlify deploy --prod'));
console.log("CURRENT_PERIOD_COMPLETION_OFFLINE_PASS: verified source, calendar bounds, 3 modes, no future leakage, legend/stack/tooltip guards");
