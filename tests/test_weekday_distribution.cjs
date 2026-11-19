/* Run with: node --test tests/test_weekday_distribution.cjs */
const test=require("node:test");
const assert=require("node:assert/strict");
const w=require("../kyiv-air-alerts-grafana/pages-preview/weekday-distribution.js");
const index={status:"verified",start:"2026-10-25",end:"2026-10-29",
  counts:[1,0,2,0,1],
  daily_total_alert_duration_seconds:[3600,1800,7200,0,0]};
test("weekday attribution: start count vs actual time split at midnight",()=>{
  assert.equal(w.validIndex(index),true);
  const result=w.summarize(index,"2026-10-25","2026-10-29");
  assert.deepEqual(result.weekdays.map(x=>x.days),[1,1,1,1,0,0,1]);
  assert.equal(result.weekdays[0].starts,0);
  assert.equal(result.weekdays[0].seconds,1800);
  assert.equal(result.weekdays[0].averageHours,0.5);
  assert.equal(result.weekdays[6].starts,1);
  assert.equal(result.weekdays[6].averageHours,1);
});
test("range selection clamps and missing weekday is null rather than zero",()=>{
  assert.equal(w.summarize(index,"2026-10-26","2026-10-27").calendarDays,2);
  assert.equal(w.summarize(index,"2026-10-26","2026-10-27").weekdays[6].days,0);
  assert.equal(w.summarize(index,"2026-10-26","2026-10-27").weekdays[6].averageStarts,null);
  assert.equal(w.summarize(index,"2026-10-20","2026-10-29").calendarDays,5);
  assert.equal(w.summarize(index,"2026-10-30","2026-10-31"),null);
  assert.equal(w.summarize(index,"2026-10-29","2026-10-26"),null);
});
test("presets use latest verified day rather than wall clock",()=>{
  assert.deepEqual(w.preset(index,"28d"),{from:"2026-10-25",to:"2026-10-29"});
  assert.deepEqual(w.preset(index,"90d"),{from:"2026-10-25",to:"2026-10-29"});
  assert.deepEqual(w.preset(index,"year"),{from:"2026-10-25",to:"2026-10-29"});
});
test("invalid or incomplete source index fails closed",()=>{
  assert.equal(w.validIndex({...index,counts:[1,2]}),false);
  assert.equal(w.validIndex({...index,daily_total_alert_duration_seconds:[3600,NaN,7200,0,0]}),false);
  assert.equal(w.validIndex({...index,start:"2026-02-30"}),false);
});
test("DST transition does not shift weekday assignment",()=>{
  const dst={status:"verified",start:"2026-10-24",end:"2026-10-27",counts:[1,1,0,2],
    daily_total_alert_duration_seconds:[120,300,180,400]};
  assert.deepEqual(w.summarize(dst,dst.start,dst.end).weekdays.map(x=>x.days),[1,1,0,0,0,1,1]);
  assert.equal(w.summarize(dst,dst.start,dst.end).weekdays[0].seconds,180);
});
