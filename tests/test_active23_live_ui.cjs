/* Exact source-at-capture UI contract. No HTTP, no browser or production writes. */
"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const provisional=require("../kyiv-air-alerts-grafana/pages-preview/active-23-provisional.js");
const overlay=require("../kyiv-air-alerts-grafana/pages-preview/active-23-chart-overlay.js");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const html=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/index.html","utf8");
const build=fs.readFileSync("netlify.toml","utf8");
const DAY=24*3600*1000;
const AT=new Date("2026-11-20T05:31:00Z");
const CAPTURE="2026-11-20T05:30:00Z";
const TODAY="2026-11-20";
const CITIES=["cherkasy","chernihiv","chernivtsi","dnipro","ivano_frankivsk",
  "kharkiv","kherson","khmelnytskyi","kropyvnytskyi","kyiv",
  "lutsk","lviv","mykolaiv","odesa","poltava","rivne","sevastopol",
  "sumy","ternopil","uzhhorod","vinnytsia","zaporizhzhia","zhytomyr"];
const add=(date,n)=>new Date(Date.parse(date+"T00:00:00Z")+n*DAY).toISOString().slice(0,10);
function snapshot(open=true,start="2026-11-20T05:10:00Z"){
  const cities={};
  for(const key of CITIES){
    const active=key==="kyiv"&&open,seconds=active?1200:0;
    const period=from=>({from,through:TODAY,closed_seconds:0,
      provisional_seconds:seconds,combined_seconds:seconds});
    cities[key]={city_key:key,state:active?"open_at_source_capture":
      "no_open_at_source_capture",date:TODAY,
      source_key:key==="kyiv"?"kyiv_digital":"ukrainealarm_region_history",
      capture_at:CAPTURE,start_at:active?start:null,
      source_sha256:"b".repeat(64),
      periods:{day:period(TODAY),month:period("2026-11-01")}};
  }
  return {schema:"c6-active-23-source-capture-v1",
    capture_scope:"observed_at_last_collection_not_live",
    test_only:false,publication_allowed:true,delivery:"site-prod-git",
    authoritative_live_status:false,
    source_generated_at:"2026-11-20T07:30:00+02:00",
    archive_sha256:"b".repeat(64),
    same_run_dashboard_sha256:"c".repeat(64),
    same_run_derived_sha256:"d".repeat(64),
    release_manifest_sha256:"f".repeat(64),timezone:"Europe/Kyiv",
    count_cities:23,count_source_open:open?1:0,
    count_source_no_open:open?22:23,cities};
}
function row(){
  return {date:TODAY,is_partial_period:true,
    avg_daily_alert_hours:0,total_alert_duration_hours:0,
    alerts_started:0,alerts_per_day:0,
    partial_through:CAPTURE};
}
function cityData(){
  return Object.fromEntries(CITIES.map(k=>[k,{daily28:Array.from({length:28},(_,i)=>
    ({date:add(TODAY,i-28),is_partial_period:false,alerts_started:0,
      avg_daily_alert_hours:0,total_alert_duration_hours:0}))}]));
}
function envelope(){
  return {meta:{timezone:"Europe/Kyiv",current_day:TODAY,
    current_day_is_partial:true,kpi_period_unchanged:true},
    cities:Object.fromEntries(CITIES.map(k=>[k,
      {...row(),active_alerts:0}]))};
}
test("same-day started alarm is counted once in current-day and month",()=>{
  const snap=snapshot();
  const report=provisional.evaluate(snap,"kyiv","day",AT);
  assert.ok(report?.fresh&&report.hadOpen);
  const o=overlay.forChart(snap,"kyiv","daily28",[row()],AT);
  assert.ok(o);
  assert.equal(o.unclosedStartsToday,1);
  assert.equal(o.unclosedStartsInPeriod,1);
  assert.equal(o.rawProvisionalHours,1/3);
  assert.equal(Number(row().alerts_started)+o.unclosedStartsInPeriod,1);
  const month=overlay.forChart(snap,"kyiv","monthly",
    [{month:"2026-11",is_partial_period:true,
      partial_through:TODAY,avg_daily_alert_hours:0}],AT);
  assert.equal(month?.unclosedStartsInPeriod,1);
});
test("prior-day still-open alarm is not a new start today",()=>{
  const snap=snapshot(true,"2026-11-19T21:10:00Z");
  const o=overlay.forChart(snap,"kyiv","daily28",[row()],AT);
  assert.ok(o);
  assert.equal(o.unclosedStartDay,"2026-11-19");
  assert.equal(o.unclosedStartsToday,0);
  assert.equal(o.unclosedStartsInPeriod,0);
  const month=overlay.forChart(snap,"kyiv","monthly",
    [{month:"2026-11",is_partial_period:true,
      partial_through:TODAY,avg_daily_alert_hours:0}],AT);
  assert.equal(month?.unclosedStartsInPeriod,1);
});
test("verified all-clear removes provisional cap rather than repeating start",()=>{
  const snap=snapshot(false);
  assert.equal(provisional.evaluate(snap,"kyiv","day",AT).hadOpen,false);
  assert.equal(overlay.forChart(snap,"kyiv","daily28",[row()],AT),null);
  const cities=cityData();
  assert.equal(overlay.ensureSnapshotDay(cities,snap,TODAY,envelope(),AT),true);
  assert.equal(cities.kyiv.daily28.length,28);
  assert.equal(cities.kyiv.daily28.at(-1).date,TODAY);
  assert.equal(cities.kyiv.daily28.at(-1).alerts_started,0);
});
test("23 current-day rows attach to correct X date and not yesterday",()=>{
  const cities=cityData();
  assert.equal(cities.kyiv.daily28.at(-1).date,"2026-11-19");
  assert.equal(overlay.ensureSnapshotDay(cities,snapshot(),TODAY,envelope(),AT),true);
  for(const k of CITIES){
    assert.equal(cities[k].daily28.length,28,k);
    assert.equal(cities[k].daily28.at(-1).date,TODAY,k);
    assert.equal(cities[k].daily28[0].date,"2026-10-24",k);
  }
  assert.equal(overlay.ensureSnapshotDay(cities,snapshot(),TODAY,envelope(),AT),true);
});
test("stale source and next local midnight fail closed",()=>{
  const snap=snapshot();
  assert.equal(provisional.evaluate(snap,"kyiv","day",
    new Date("2026-11-20T16:00:00Z")),null);
  assert.equal(provisional.evaluate(snap,"kyiv","day",
    new Date("2026-11-20T22:01:00Z")),null);
  assert.equal(overlay.forChart(snap,"kyiv","daily28",[row()],
    new Date("2026-11-20T22:01:00Z")),null);
  assert.equal(overlay.ensureSnapshotDay(cityData(),snap,TODAY,envelope(),
    new Date("2026-11-20T22:01:00Z")),false);
});
test("invalid schema, cross-generation, missing source are never displayed",()=>{
  const snap=snapshot();
  assert.equal(provisional.evaluate({...snap,publication_allowed:false},
    "kyiv","day",AT),null);
  assert.equal(provisional.evaluate({...snap,schema:"c2-active-23-source-snapshot-test-v1"},
    "kyiv","day",AT),null);
  assert.equal(provisional.evaluate({...snap,count_cities:22},
    "kyiv","day",AT),null);
  assert.match(app,/source_generated_at === source/);
  assert.match(app,/release_manifest_sha256 === release\?\.release_manifest_sha256/);
  assert.match(app,/derived\?\.meta\?\.generated_at === state\.data\?\.meta\?\.generated_at/);
});
test("production has no frozen preview urls and deploys both chart modules",()=>{
  assert.match(app,/RAW_DATA_BASE \+ "active23_source_capture\.json"/);
  assert.match(app,/countRows\.map\(r => r\.alerts_per_day\)/);
  assert.match(app,/Попередні дані можуть коригуватися при наступних оновленнях/);
  assert.doesNotMatch(app,/active-23-provisional-test\.json|Архівний тест 20\.11\.2026/);
  for(const file of ["active-23-provisional.js","active-23-chart-overlay.js"]){
    assert.match(html,new RegExp(file.replaceAll(".","\\.")));
    assert.match(build,new RegExp(file.replaceAll(".","\\.")));
  }
  assert.doesNotMatch(build,/active-23-provisional-test\.json/);
});
