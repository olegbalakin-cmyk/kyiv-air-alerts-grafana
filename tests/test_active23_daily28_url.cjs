"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const a=app.indexOf("function rollingDaily28UrlAdvance(");
const b=app.indexOf("\nfunction rowTime(",a);
assert(a>0&&b>a,"Pure rolling-range recovery must be present");
const addIsoDays=(value,n)=>new Date(Date.parse(value+"T00:00:00Z")+n*86400000).toISOString().slice(0,10);
const context={addIsoDays,kyivCalendarToday:()=> "2026-11-21",Date,Math,Array,Number};
const fn=vm.runInNewContext(app.slice(a,b)+"\nrollingDaily28UrlAdvance",context);
const city=()=>({daily28:Array.from({length:28},(_,i)=>({
 date:addIsoDays("2026-10-25",i),is_partial_period:i===27,
 alerts_started:0,total_alert_duration_hours:0
}))});
test("a URL emitted yesterday for the complete 28-day preset follows today's verified bar",()=>{
 const z=fn(city(),"2026-10-24","2026-11-20");
 assert.deepEqual({...z},{from:"2026-10-25",to:"2026-11-21"});
});
test("a 2-7-day-old rolling 28-day preset moves to latest 28 days",()=>{
 for(let n=2;n<=7;n++){
  const z=fn(city(),addIsoDays("2026-10-25",-n),addIsoDays("2026-11-21",-n));
  assert.equal(z?.from,"2026-10-25");
  assert.equal(z?.to,"2026-11-21");
 }
});
test("arbitrary selected intervals, including shortened yesterday, do not change",()=>{
 for(const [from,to] of [["2026-10-25","2026-11-20"],
    ["2026-11-14","2026-11-20"],["2026-10-30","2026-11-20"],
    ["2026-10-25","2026-11-21"],["2026-10-10","2026-10-31"]]){
  assert.equal(fn(city(),from,to),null,from+":"+to);
 }
});
test("no certified current-day row means no date advancement",()=>{
 const missing=city();
 missing.daily28[27].is_partial_period=false;
 assert.equal(fn(missing,"2026-10-24","2026-11-20"),null);
 const wrongDay=city();
 wrongDay.daily28[27].date="2026-11-20";
 assert.equal(fn(wrongDay,"2026-10-24","2026-11-20"),null);
 const hole=city();
 hole.daily28[14].date="2026-11-11";
 assert.equal(fn(hole,"2026-10-24","2026-11-20"),null);
});
test("init integrates recovery before first chart render",()=>{
 const called=app.indexOf("const range = rollingDaily28UrlAdvance(",b);
 assert(called>b);
 assert(called<app.indexOf("  renderCity();",called));
 assert.match(app.slice(called,called+500),/cityDateTo/);
});
