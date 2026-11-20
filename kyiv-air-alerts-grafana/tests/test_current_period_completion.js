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

// Regression: current source as-of Sunday 15 Nov 18:09 Kyiv,
 // user visits Monday 16 Nov 00:05 Kyiv. Same month/quarter, different week.
 // A certified fresh partial day may anchor MONTH/Q4 prediction to the
 // source's 15 Nov cutoff, but never invent Monday observations/weekly stats.
const rolloverIndex={...history,end:"2026-11-14",
 counts:[...history.counts,2],
 daily_total_alert_duration_seconds:[...history.daily_total_alert_duration_seconds,7200],
 verified_metric_months:[...new Set([...history.verified_metric_months,"2026-11"])]};
const rolloverPartial={date:"2026-11-15",is_partial_period:true,
 partial_through:"2026-11-15T18:09:00+02:00",
 total_alert_duration_hours:0,alerts_started:0};
const midnightNow="2026-11-16T00:05:00+02:00";
assert(F.estimate(rolloverIndex,"quarterly","2026-11-15",rolloverPartial,midnightNow),
 "Q4 forecast stays available after midnight using fresh certified Nov15 snapshot");
assert(F.estimate(rolloverIndex,"monthly","2026-11-15",rolloverPartial,midnightNow),
 "November forecast stays available after midnight using recent certified cutoff");
assert.equal(F.estimate(rolloverIndex,"quarterly","2026-11-16",rolloverPartial,midnightNow),null,
 "no silent claim of observed Monday Nov16");
assert.notEqual(F.bounds("2026-11-15","calendarWeekly").start,
 F.bounds("2026-11-16","calendarWeekly").start,
 "new Monday week must not inherit old Sunday week forecast");
assert.equal(F.estimate(rolloverIndex,"quarterly","2026-11-15",rolloverPartial,
 "2026-11-16T03:00:00+02:00"),null,
 "source older than 8 hours must disable prediction");
assert(app.includes('sourceDayCanAnchor=period!=="daily28"'),
 "cross-midnight source anchoring restricted to supported period modes");
assert(app.includes('currentBounds.start===sourceBounds.start'),
 "stale source snapshot cannot cross period boundary");
assert(app.includes('trendControl.classList.remove("hidden")'),
 "trend checkbox stays visible even if source projection unavailable");
assert(app.includes('trendToggle.disabled=!completionPotential'),
 "unavailable forecast is disabled, never faked");
assert(app.includes('if(!completionPotential)trendToggle.checked=false'),
 "stale selected trend must clear when projection is unavailable");
assert(!app.includes('intensitySubtitle.textContent+=" "+trendReason'),
 "unavailable state must not clutter chart explanation");
assert(app.includes('trendHelpText.textContent=completionPotential?"":trendReason'),
 "unavailable reason appears in the compact tooltip");
assert(app.includes('trendHelpButton?.addEventListener("click"'),
 "info button can open tooltip on touch");
assert(app.includes('trendHelpButton?.addEventListener("keydown"'),
 "keyboard users can dismiss explanation");
assert(app.includes('completionModel?.estimate('),"trend uses established verified completion estimator");
assert(app.includes('const completionPeriod = ["daily28","calendarWeekly","monthly","quarterly"]'));
assert(app.includes("completionModel?.estimateToday("),"daily chart uses verified current day");
assert(app.includes('trendToggle.disabled=!completionPotential'),"trend disabled unless the original factual period has a certified forecast");
assert(!app.includes("QuarterRollingPreview?.rollingForecast("),"no rolling next-period forecast invocation");
assert(!app.includes("window.ForecastTrend?.build("),"no daily/month next-period forecast invocation");
assert(!app.includes("projectedRows"),"no additional future bar");
assert(!app.includes("_isForecast: true"),"no future-period dataset");
assert(!app.includes("forecastIndices"),"no extra forecast axis labels");
// The trend toggle must NEVER change any actual input, scale or value.
// All observed daily averages use the verified source's observed-day divisor;
// a forecast uses full calendar-period days and is only an annotation.
const q4=F.estimate(history,"quarterly","2026-11-14");
assert(q4&&q4.days===92&&q4.observed===44);
assert.equal(q4.periodRow.avg_daily_alert_hours,2);
assert.equal(q4.periodRow.alerts_per_day,2);
assert.equal(q4.actualHours/q4.observedDaysEquivalent,2);
assert(q4.actualHours/q4.days<1,"dividing actual by 92 is not observed intensity");
assert(Math.abs(q4.expectedHours-q4.actualHours-q4.remainingHours)<1e-9);
// Independent baseline: raw periodRows() must remain exactly as it is on
// site-prod. Even selecting the verified newer forecast source may NOT
// change a factual October-only Q4 into an October+November Q4.
assert(app.includes('const currentObservedRow=rows.at(-1);'),
  "actuals must be anchored to the original period rows");
assert(app.includes('const currentObservedPeriodMatches=Boolean('),
  "forecast can be added only to its matching calendar period");
assert(app.includes('const completionPotential=completionVisible && currentObservedPeriodMatches'),
  "forecast candidate is distinct from original actual period");
assert(app.includes('const completion=completionPotential && trendToggle?.checked'),
  "toggle affects only forecast overlay, not fact");
assert(!app.includes('rows=[...rows,completionPotential.periodRow]'),
  "trend cannot replace original factual rows with a newer partial day");
assert(!app.includes('rows = [...rows,completion.periodRow]'),
  "regression: original production replaced actual Q4 on trend ON");
assert(app.includes('const intensityHours=rows.map(r=>r.avg_daily_alert_hours)') &&
       app.includes('data: intensityHours,') &&
       app.includes('if(active23Overlay)intensityHours[active23Overlay.index]=active23Overlay.closedHours;'),
  "original factual bar data remain unchanged except exact source-certified last-bar provisional normalization");
assert(app.includes('data: rows.map(r => r.alerts_per_day)'),
  "actual line remains original-source values");
assert(!app.includes('intensityDatasets[0].data[i]='),
  "trend cannot overwrite observed hours");
assert(!app.includes('intensityDatasets[1].data[i]='),
  "trend cannot overwrite observed alert rate");
assert(app.includes('completion.expectedHours/completion.days'),
  "forecast-only hours uses all calendar days");
assert(app.includes('completion.expectedAlerts/completion.days'),
  "forecast-only alerts uses all calendar days");
assert(!app.includes('type:"bar",_isCompletion:true'),
  "no forecast bar should be confused with the observed bar");
assert(!app.includes('stack:"completion"'),"forecast-only markers are not additive to fact");
assert(app.includes('stacked:false'),"actual bar retains original stacking semantics");
assert(!app.includes('periodCompletionHatchPlugin'),"no misleading hatch on actual");
assert(app.includes('completionPotential&&!active23Overlay ? completionPotential.expectedHours/completionPotential.days : 0') &&
       app.includes('Number(active23AxisForecast)||0') &&
       app.includes('const active23Forecast=completion&&active23Overlay ? active23AxisForecast : null;'),
  "hours axis stays stable regardless of trend toggle, even with source-certified provisional cap");
assert(app.includes('completionPotential ? completionPotential.expectedAlerts/completionPotential.days : 0'),
  "alerts axis stays stable regardless of trend toggle");
assert(app.includes('const periodForecastDeltaHatchPlugin = {'),"hatched forecast delta renderer exists");
assert(app.includes('id:"periodForecastDeltaHatch"'),"hatch plugin registered by stable ID");
assert(app.includes('plugins: [partialPeriodBarPlugin, periodForecastDeltaHatchPlugin, active23FinalBarPlugin]'),
  "forecast delta hatch and isolated provisional-cap renderer only on city intensity chart");
assert(app.includes('observedHoursPerDay:completion&&!active23Overlay ? rows.at(-1)?.avg_daily_alert_hours : null'),
  "forecast hatching compares original factual mean only when no provisional source cap exists");
assert(app.includes('forecastHoursPerDay:completion&&!active23Overlay ? completion.expectedHours/completion.days : null'),
  "forecast hatch uses full period denominator only without competing provisional hatching");
assert(app.includes('const top=Math.min(ya,yf),bottom=Math.max(ya,yf)'),
  "hatched interval is bounded by actual and forecast for either direction");
assert(app.includes('ctx.fillStyle=expected>actual?'),
  "forecast above and below actual must have visibly distinct hatch infill");
assert(!app.includes('pointStyle:"line",pointRadius:13'),
  "old detached white tick has been replaced by in-bar hatching");
assert(app.includes('pointStyle:"rectRot"'),"alert forecast is a separate diamond");
assert(app.includes('trendControl.classList.remove("hidden")'),
  "trend always visible, including unsupported or fresh-data-unavailable modes");
assert(app.includes('Штрихування не додається до факту.'),
  "Ukrainian explanation must distinguish fact/forecast cutoffs");
assert(app.includes('Hatching is not additive.'),
  "English explanation must distinguish fact/forecast cutoffs");
assert(app.includes('const factClock=partialThroughKyivClock(factSource,factDay);'),
  "tooltip formats source timezone-aware factual clock instead of dropping time");
assert(app.includes('partialThroughKyivClock(modelSource,modelDay)'),
  "forecast source clock is rendered in Kyiv local time");
assert(app.includes('shortDateLabel(completion.end)'),
  "tooltip uses readable short forecast period ending date");
assert(!app.includes('" за даними до "+modelCutoff'),
  "tooltip must not expose raw ISO timestamp and timezone offsets");
assert(app.includes('factualRow?.quarter_end'),
  "quarterly factual cutoff is the original completed-month endpoint");
assert(app.includes('completionPotential.asOf'),
  "forecast carries its own independently verified cutoff");

assert(app.includes('approvedNeonGitRelease'));
assert(app.includes('matchesDashboardGeneration'));
assert(!app.includes('netlify deploy --prod'));
assert(app.includes('const quarterRangeStartsTooLate=period==="quarterly" && completionCandidate'),
  "quarter range warning is only used for an actually valid forecast");
assert(app.includes('activeRange.from>completionCandidate.start'),
  "late date-from is diagnosed against the current quarter start");
assert(app.includes('activeRange.to<completionCandidate.through'),
  "early date-to is diagnosed separately");
assert(app.includes('Для прогнозу "+quarterRoman+" кварталу виберіть діапазон від '),
  "quarter-specific Ukrainian tooltip replaces ambiguous freshness message");
assert(app.includes('toUkrDate(quarterStart)+" або раніше."'),
  "quarter start shown as a localized inclusive boundary");
assert(app.includes('select a range starting on '),
  "English tooltip describes the actual date-range problem");
console.log("CURRENT_PERIOD_ORIGINAL_FACT_METHOD_PASS: original quarter/month/week rows unchanged, forecast-only markers and two source cutoffs, DST 23/25h");
