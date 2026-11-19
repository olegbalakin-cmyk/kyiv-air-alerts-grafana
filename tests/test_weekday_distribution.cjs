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
  assert.deepEqual(w.preset(index,"180d"),{from:"2026-10-25",to:"2026-10-29"});
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

test("180-day preset includes exactly 180 verified calendar days",()=>{
  const end="2026-11-18";
  const start=new Date(Date.parse(end+"T00:00:00Z")-219*86400000).toISOString().slice(0,10);
  const from=new Date(Date.parse(end+"T00:00:00Z")-179*86400000).toISOString().slice(0,10);
  const long={status:"verified",start,end,counts:Array(220).fill(1),daily_total_alert_duration_seconds:Array(220).fill(60)};
  assert.deepEqual(w.preset(long,"180d"),{from,to:end});
  assert.equal(w.summarize(long,from,end).calendarDays,180);
  assert.equal(w.summarize(long,from,end).weekdays.reduce((sum,day)=>sum+day.starts,0),180);
});

const bandSource={schema:"weekday-dayparts-test-v1",
  meta:{timezone:"Europe/Kyiv",test_only:true},max_day:"2026-10-29",
  rows:[
    ["2026-10-25",1200,300,600,900,600],
    ["2026-10-26",0,600,600,300,300],
    ["2026-10-27",1800,600,600,3600,600],
    ["2026-10-29",0,0,0,0,0]
  ]};
test("four time bands exactly preserve verified daily hours and weekdays",()=>{
  const split=w.splitHours(index,bandSource,index.start,index.end,"four");
  assert.ok(split);
  assert.equal(split.weekdays[6].days,1);
  assert.deepEqual(split.weekdays[6].parts,[1200,900,900,600]);
  assert.deepEqual(split.weekdays[0].parts,[0,1200,300,300]);
  assert.equal(split.weekdays[4].averageParts[0],null);
  assert.ok(Math.abs(split.weekdays.reduce((v,b)=>v+b.parts.reduce((x,y)=>x+y,0),0)-12600)<0.0001);
});
test("day and evening-night are 09-18 / 18-09, not a six-hour approximation",()=>{
  const split=w.splitHours(index,bandSource,index.start,index.end,"daynight");
  assert.ok(split);
  assert.deepEqual(split.weekdays[6].parts,[1500,2100]);
  assert.deepEqual(split.weekdays[1].parts,[4200,3000]);
});
test("time band split rejects discrepancies, future dates, invalid and duplicate rows",()=>{
  assert.equal(w.splitHours(index,{...bandSource,rows:[["2026-10-25",0,0,0,0,0]]},index.start,index.end,"four"),null);
  assert.equal(w.splitHours(index,{...bandSource,max_day:"2026-10-28"},index.start,index.end,"four"),null);
  assert.equal(w.splitHours(index,{...bandSource,rows:[...bandSource.rows,bandSource.rows[0]]},index.start,index.end,"four"),null);
  assert.equal(w.splitHours(index,bandSource,index.start,index.end,"six"),null);
  assert.equal(w.splitHours(index,bandSource,"2026-10-20",index.end,"four"),null);
});
test("DST day can contain more than 24 elapsed hours without normalization",()=>{
  const dst={status:"verified",start:"2026-10-25",end:"2026-10-25",
    counts:[1],daily_total_alert_duration_seconds:[90000]};
  const bands={...bandSource,rows:[["2026-10-25",25200,10800,10800,21600,21600]]};
  const split=w.splitHours(dst,bands,dst.start,dst.end,"daynight");
  assert.ok(split);
  assert.equal(split.weekdays[6].parts[0],32400);
  assert.equal(split.weekdays[6].parts[1],57600);
});
