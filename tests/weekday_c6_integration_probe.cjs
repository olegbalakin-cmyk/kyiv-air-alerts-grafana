/* Offline release parity regression. Reads only current branch Git JSON.
 * No HTTP, Neon, Netlify, C2, mutation or publication.
 * Runs in GitHub Actions checkout where >1 MiB producer outputs are available.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const w = require("../kyiv-air-alerts-grafana/pages-preview/weekday-distribution.js");
const root = path.resolve(__dirname, "..");
const read = name => JSON.parse(fs.readFileSync(path.join(root,
  "kyiv-air-alerts-grafana/data",name), "utf8"));
const dashboard = read("dashboard_data.json");
const derived = read("site_derived.json");
const manifest = dashboard.meta?.publication_authority?.release_manifest_sha256;
const generated = dashboard.meta?.generated_at;
const schema = derived.explorations?.meta?.weekday_daypart_schema;
const keys = dashboard.multicity_meta?.production_city_keys || [];
const result = {
  schema:"weekday-c6-proof-v1",
  release:manifest || null,
  dashboard_generation:generated || null,
  derived_generation:derived.meta?.generated_at || null,
  derived_release:derived.meta?.publication_authority?.release_manifest_sha256 || null,
  cities:keys.length,
  schema_name:schema,
  cases:0,
  success:0,
  failures:[],
  per_city:[],
  verdict:"FAIL"
};
function test(ok,key,reason,more={}) {
  result.cases++;
  if (ok) {result.success++;return;}
  result.failures.push({key,reason,...more});
}
function iso(ms){return new Date(ms).toISOString().slice(0,10);}
function shift(d,offset){return iso(Date.parse(d+"T00:00:00Z")+offset*86400000);}
function attempts(index,city) {
  const start=index.start, end=index.end;
  const vals=[
    ["28d",shift(end,-27),end],
    ["90d",shift(end,-89),end],
    ["180d",shift(end,-179),end],
    ["year",end.slice(0,4)+"-01-01",end],
    ["all",start,end],
    ["custom",shift(end,-13),shift(end,-3)]
  ];
  return vals.map(([name,a,b])=>[name,a<start?start:a,b]);
}
try {
  test(keys.length===23,"all","CITIES_NOT_23",{got:keys.length});
  test(!!manifest && /^[a-f0-9]{64}$/.test(manifest),"all","DASHBOARD_RELEASE_MISSING");
  test(derived.meta?.publication_authority?.release_manifest_sha256===manifest,
    "all","DERIVED_RELEASE_MISMATCH");
  test(schema==="weekday-local-five-bands-union-v1","all","DAYPART_SCHEMA_MISMATCH");
  const indexMeta=dashboard.historical_daily_kpi?.meta;
  test(indexMeta?.release_manifest_sha256===manifest,"all","HISTORICAL_INDEX_RELEASE_MISMATCH");
  test(indexMeta?.source_dashboard_generated_at===generated,"all","KPI_DASHBOARD_GENERATION_MISMATCH");
  for (const key of keys) {
    const index=dashboard.historical_daily_kpi?.cities?.[key];
    const city=derived.explorations?.cities?.[key];
    const entry={key,index_start:index?.start,index_end:index?.end,
      derived_start:city?.coverage_start,derived_end:city?.analysis_end,pass:0,fail:0};
    result.per_city.push(entry);
    test(!!city&&!!index,key,"MISSING_CITY_DATA");
    if(!city||!index) {entry.fail++;continue;}
    test(w.validIndex(index),key,"INVALID_VERIFIED_INDEX");
    if(!w.validIndex(index)) {entry.fail++;continue;}
    const ctx={
      dashboardReleaseId:manifest,
      derivedReleaseId:derived.meta?.publication_authority?.release_manifest_sha256,
      dashboardGeneratedAt:generated,
      derivedGeneratedAt:derived.meta?.generated_at,
      city,
      schema
    };
    const expected = w.sameVerifiedRelease(index,ctx);
    test(expected,key,"RELEASE_ID_NOT_ACCEPTED");
    for(const [name,from,to] of attempts(index,city)) {
      for (const mode of ["four","daynight"]) {
        const split=w.splitDerivedHours(index,ctx,from,to,mode);
        const success=!!split && split.weekdays.length===7 &&
          split.weekdays.every(b=>b.parts.length===(mode==="four"?4:2)) &&
          split.weekdays.reduce((sum,day)=>sum+day.parts.reduce((a,b)=>a+b,0),0)>=0;
        test(success,key,"SPLIT_UNAVAILABLE",{name,mode,from,to});
        if(success)entry.pass++;else entry.fail++;
      }
    }
    const from=Math.max(index.start,shift(index.end,-6));
    const mismatch = {
      ...ctx, derivedReleaseId:"f".repeat(64)
    };
    const blocked = w.splitDerivedHours(index,mismatch,from,index.end,"four");
    test(blocked===null,key,"FOREIGN_RELEASE_WAS_ACCEPTED");
    if(blocked===null)entry.pass++;else entry.fail++;
  }
  const report = {cases:result.cases,passed:result.success,failed:result.failures.length,
    sampleFailures:result.failures.slice(0,50)};
  result.verdict = result.failures.length===0?"PASS":"FAIL";
  console.log("WEEKDAY_C6_INTEGRATION",JSON.stringify(report));
} catch (error) {
  result.failures.push({key:"probe",reason:"EXCEPTION",message:String(error.stack||error)});
  console.error("WEEKDAY_C6_INTEGRATION_EXCEPTION",error);
}
fs.writeFileSync("weekday-c6-integration-proof.json",JSON.stringify(result,null,2)+"\n");
if(result.failures.length)process.exitCode=1;
