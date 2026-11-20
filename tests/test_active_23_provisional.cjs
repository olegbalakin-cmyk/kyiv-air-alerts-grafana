/* No network. Exact 23-city same-run C2 snapshot and math regression. */
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs");
const api=require("../kyiv-air-alerts-grafana/pages-preview/active-23-provisional.js");
const path=process.env.ACTIVE23_JSON;
if(!path)throw new Error("ACTIVE23_JSON must reference offline-generated source proof");
const snapshot=JSON.parse(fs.readFileSync(path,"utf8"));
const at=new Date("2026-11-20T06:00:00Z");
test("exact 23 city provenance and expected source states",()=>{
 assert.equal(snapshot.count_cities,23);
 assert.equal(snapshot.count_source_open,22);
 assert.equal(snapshot.count_source_no_open,1);
 assert.equal(snapshot.publication_allowed,false);
 assert.equal(Object.keys(snapshot.cities).length,23);
 for(const key of Object.keys(snapshot.cities)){
  const x=api.evaluate(snapshot,key,"day",at);
  assert.ok(x,key+" blocked");
  assert.equal(x.archival,true);
  assert.equal(x.through,"2026-11-20");
  assert.ok(x.closed>=0&&x.open>=0&&x.total>=0);
  assert.ok(Math.abs(x.total-x.closed-x.open)<0.005);
  for(const preset of api.periods)assert.ok(api.evaluate(snapshot,key,preset,at),key+"/"+preset);
 }
});
test("Sevastopol has a completed last pair and zero provisional hours",()=>{
 const s=api.evaluate(snapshot,"sevastopol","day",at);
 assert.equal(s.hadOpen,false);
 assert.equal(s.open,0);
 assert.equal(s.source,"sevastopol_history");
});
test("Kyiv and UkraineAlarm series have source-observed unclosed hours",()=>{
 const kyiv=api.evaluate(snapshot,"kyiv","day",at);
 assert.equal(kyiv.hadOpen,true);
 assert.equal(kyiv.source,"kyiv_digital");
 assert.ok(kyiv.open>6*3600&&kyiv.open<7*3600);
 const kharkiv=api.evaluate(snapshot,"kharkiv","day",at);
 assert.equal(kharkiv.hadOpen,true);
 assert.equal(kharkiv.source,"ukrainealarm_region_history");
});
test("periods accumulate verified completed and provisional only once",()=>{
 for(const city of Object.keys(snapshot.cities)){
  const a=api.evaluate(snapshot,city,"day",at);
  const b=api.evaluate(snapshot,city,"month",at);
  const c=api.evaluate(snapshot,city,"last28",at);
  assert.ok(b.closed+0.01>=a.closed,city);
  assert.ok(c.closed+0.01>=a.closed,city);
  // Cross-midnight alerts contribute only today's portion to the day,
  // but their previous-day portion also belongs to month/28-day windows.
  assert.ok(b.open+0.001>=a.open,city);
  assert.ok(c.open+0.001>=a.open,city);
  assert.ok(b.open<36*3600&&c.open<36*3600,city);
 }
});
test("stale snapshot remains explicitly archival and never claims live status",()=>{
 const earlier=api.evaluate(snapshot,"kyiv","day",at);
 assert.equal(earlier.archival,true);
 const late=api.evaluate(snapshot,"kyiv","day",new Date("2026-11-20T17:00:00Z"));
 assert.equal(late.fresh,false);
 assert.equal(late.archival,true);
 assert.equal(late.total,earlier.total);
});
test("mismatched generation, source data and arithmetic fail closed",()=>{
 const invalid=[
  {...snapshot,archive_sha256:"0000"},
  {...snapshot,same_run_dashboard_sha256:"unknown"},
  {...snapshot,count_cities:22},
  {...snapshot,cities:{...snapshot.cities,kyiv:{...snapshot.cities.kyiv,start_at:"untrusted"}}},
  {...snapshot,cities:{...snapshot.cities,kyiv:{...snapshot.cities.kyiv,periods:{...snapshot.cities.kyiv.periods,day:{...snapshot.cities.kyiv.periods.day,combined_seconds:9999999}}}}},
 ];
 for(const x of invalid)assert.equal(api.evaluate(x,"kyiv","day",at),null);
 assert.equal(api.evaluate(snapshot,"invented_city","day",at),null);
 assert.equal(api.evaluate(snapshot,"kyiv","unknown",at),null);
});
