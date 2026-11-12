const assert=require("node:assert/strict"),fs=require("node:fs");
const app=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/app.js","utf8");
const rolling=fs.readFileSync("kyiv-air-alerts-grafana/scripts/apply_site_rolling_7d.py","utf8");
const builder=fs.readFileSync("kyiv-air-alerts-grafana/scripts/build_preview_historical_daily.py","utf8");
assert.ok(app.includes("state.data?.historical_daily_kpi"));
assert.ok(app.includes("embeddedHistory.meta.source_dashboard_generated_at === sourceGeneratedAt"));
assert.ok(rolling.includes('data["historical_daily_kpi"] = index'));
assert.ok(builder.includes("sources_override=undefined")===false);
assert.ok(builder.includes("source_override: dict | None = None"));
assert.ok(builder.includes("sources_override: dict | None = None"));
// Exercise the actual frontend predicate: no separate implementation.
const vm=require("node:vm");
const html=fs.readFileSync("kyiv-air-alerts-grafana/pages-preview/index.html","utf8");
const gitBase="https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/";
assert.ok(app.includes('const RAW_DATA_BASE = "'+gitBase+'";'));
assert.ok(!html.includes("preview-bootstrap.js"),"production must not load preview bootstrap");
const guard=app.match(/  const isolatedNeonPreview =[\s\S]*?;\n  const validIndex = index =>[\s\S]*?;\n/);
assert.ok(guard,"frontend index guard missing");
const t="2026-11-11T12:00:00Z";
const sample=(ref="neon:br-bold-mode-b5rub8pq")=>({
  schema:"verified-historical-daily-start-counts-v1",
  meta:{source_ref:ref,expected_cities:23,verified_count:23,source_dashboard_generated_at:t}
});
const check=(index,{mode,base=gitBase,time=t,dashboard=null}={})=>{
  const context={window:mode?{PREVIEW_CONFIG:{source:mode}}:{},
    RAW_DATA_BASE:base,sourceGeneratedAt:time,state:{data:dashboard}};
  const valid=vm.runInNewContext(guard[0]+"\nvalidIndex",context,{timeout:1000});
  return Boolean(valid(index));
};
const neon=sample(),git=sample("site-prod");
const scoped={mode:"neon",base:"./data/neon/"};
assert.equal(check(git),true,"Git production unchanged");
assert.equal(check(git,scoped),true,"Git rollback unchanged");
assert.equal(check({...git,meta:{...git.meta,verified_count:1}}),true,"Git index legacy contract unchanged");
assert.equal(check(neon,scoped),true,"vetted Neon index in isolated preview");
assert.equal(check(neon),false,"Neon outside preview");
assert.equal(check(neon,{mode:"legacy",base:scoped.base}),false,"Neon in Git preview");
assert.equal(check(neon,{mode:"neon"}),false,"preview marker with production Git URL");
assert.equal(check(neon,{mode:"neon",base:"./data/legacy/"}),false,"preview marker with wrong local source");
assert.equal(check(sample("neon:other"),scoped),false,"unapproved Neon branch");
assert.equal(check(sample("neon:br-bold-mode-b5rub8pq-extra"),scoped),false,"non-exact prefix");
for(const [name,bad] of [
 ["schema",{...neon,schema:"bad"}],
 ["city count",{...neon,meta:{...neon.meta,expected_cities:22}}],
 ["verified count",{...neon,meta:{...neon.meta,verified_count:22}}],
 ["missing verified",{...neon,meta:{...neon.meta,verified_count:undefined}}],
 ["generation",{...neon,meta:{...neon.meta,source_dashboard_generated_at:"other"}}],
 ["missing generation",{...neon,meta:{...neon.meta,source_dashboard_generated_at:undefined}}]
])assert.equal(check(bad,scoped),false,name);
assert.equal(check(neon,{...scoped,time:"different"}),false,"dashboard timestamp mismatch");
assert.equal(check(neon,{...scoped,time:null}),false,"missing dashboard timestamp");
assert.equal(check(neon,{...scoped,time:123}),false,"invalid dashboard timestamp");
assert.equal(check(null,scoped),false,"missing index");
// The release authority comes from the fetched Git dashboard, never from window.
const cityKeys=Array.from({length:23},(_,i)=>"city-"+i);
const authority={
  publication_allowed:true,scope:"PRODUCTION_NEON_GIT_RELEASE",
  delivery:"site-prod-git",branch_id:"br-bold-mode-b5rub8pq",
  release_manifest_sha256:"a".repeat(64),
  historical_freshness:{binding_sha256:"b".repeat(64)},
  dst_simulation:false,source_fallback:false,
  active_status:"UNKNOWN_UNCERTIFIED"
};
const dashboard={meta:{publication_authority:authority},
  multicity_meta:{production_city_keys:cityKeys}};
const releaseIndex={...neon,meta:{...neon.meta,verified_cities:[...cityKeys],
    release_manifest_sha256:authority.release_manifest_sha256},
  cities:Object.fromEntries(cityKeys.map(key=>[key,{status:"verified"}]))};
const approved={dashboard};
assert.equal(check(releaseIndex,approved),true,"approved Neon index via production Git URL");
assert.equal(check(releaseIndex,{...approved,mode:"legacy"}),true,"browser config cannot veto approved Git release");
assert.equal(check(releaseIndex,{...approved,mode:"neon"}),true,"browser config does not grant authority");
assert.equal(check(releaseIndex,{dashboard}),true,"Git release works without browser preview config");
assert.equal(check(releaseIndex,{...approved,base:"./data/legacy/"}),false,"local source cannot impersonate production Git delivery");
assert.equal(check(releaseIndex,{...approved,base:"https://example.com/data/"}),false,"arbitrary remote base rejected");
const noAuthority={meta:{},multicity_meta:{production_city_keys:cityKeys}};
assert.equal(check(releaseIndex,{dashboard:noAuthority,mode:"neon"}),false,"browser marker alone cannot activate");
assert.equal(check(releaseIndex,{dashboard:{...dashboard,meta:{publication_authority:{...authority,publication_allowed:false}}}}),false,
  "default-off candidate cannot be accepted as released");
for(const [name,patch] of [
  ["no permission",{publication_allowed:undefined}],
  ["string permission",{publication_allowed:"true"}],
  ["wrong scope",{scope:"RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION"}],
  ["wrong delivery",{delivery:"preview"}],
  ["wrong branch",{branch_id:"br-other"}],
  ["no manifest",{release_manifest_sha256:undefined}],
  ["bad manifest",{release_manifest_sha256:"a".repeat(63)}],
  ["bad freshness",{historical_freshness:{binding_sha256:"not-a-sha"}}],
  ["DST simulation",{dst_simulation:true}],
  ["source fallback",{source_fallback:true}],
  ["active status claim",{active_status:"CERTIFIED"}]
])assert.equal(check(releaseIndex,{dashboard:{...dashboard,meta:{publication_authority:{...authority,...patch}}}}),false,
  "release authority: "+name);
for(const [name,bad] of [
  ["wrong schema",{...releaseIndex,schema:"invalid"}],
  ["wrong index branch",{...releaseIndex,meta:{...releaseIndex.meta,source_ref:"neon:br-other"}}],
  ["wrong city count",{...releaseIndex,meta:{...releaseIndex.meta,expected_cities:22}}],
  ["verified_count 22",{...releaseIndex,meta:{...releaseIndex.meta,verified_count:22}}],
  ["verified city list 22",{...releaseIndex,meta:{...releaseIndex.meta,verified_cities:cityKeys.slice(1)}}],
  ["duplicate city list",{...releaseIndex,meta:{...releaseIndex.meta,verified_cities:[cityKeys[0],...cityKeys.slice(0,22)]}}],
  ["city omitted",{...releaseIndex,cities:Object.fromEntries(Object.entries(releaseIndex.cities).slice(1))}],
  ["city not verified",{...releaseIndex,cities:{...releaseIndex.cities,[cityKeys[0]]:{status:"unverified"}}}],
  ["wrong generation",{...releaseIndex,meta:{...releaseIndex.meta,source_dashboard_generated_at:"2026-11-10T12:00:00Z"}}],
  ["missing index release binding",{...releaseIndex,meta:{...releaseIndex.meta,release_manifest_sha256:undefined}}],
  ["wrong index release binding",{...releaseIndex,meta:{...releaseIndex.meta,release_manifest_sha256:"c".repeat(64)}}]
])assert.equal(check(bad,approved),false,"Git Neon index: "+name);
assert.equal(check(releaseIndex,{...approved,time:null}),false,"Git Neon missing dashboard generation");
assert.equal(check(releaseIndex,{...approved,time:"not-a-date"}),false,"Git Neon invalid dashboard generation");
assert.equal(check(git,{dashboard:noAuthority}),true,"Git-only mode preserved without release");
console.log("PASS approved Git-delivered Neon release authority, 23/23 city set and negative cases");
console.log("PASS scoped Neon historical index positive/negative cases");

// Run the *actual* static fallback condition, not a copied approximation.
const generationGuard=app.match(/  const matchesDashboardGeneration = index =>[\s\S]*?;\n/);
const staticIf=app.match(/        if \((validIndex\(index\)[\s\S]*?)\) \{\n          state\.historicalDaily = index;/);
assert.ok(generationGuard && staticIf,"static fallback must have the production generation guard");
const checkStatic=(index,{mode,base=gitBase,time="2026-11-12T09:08:13.340390+02:00"}={})=>
  Boolean(vm.runInNewContext(guard[0]+generationGuard[0]+"\n("+staticIf[1]+")",
    {index,window:mode?{PREVIEW_CONFIG:{source:mode}}:{},
      RAW_DATA_BASE:base,sourceGeneratedAt:time,state:{data:null}},{timeout:1000}));
const nov12="2026-11-12T09:08:13.340390+02:00";
const oct23="2026-10-23T07:47:16.946235+03:00";
const gitStatic={...git,meta:{...git.meta,source_dashboard_generated_at:nov12}};
assert.equal(checkStatic(gitStatic),true,"matching static index accepted");
assert.equal(checkStatic({...gitStatic,meta:{...gitStatic.meta,source_dashboard_generated_at:oct23}}),
  false,"Oct 23 static index rejected against Nov 12 Git dashboard");
for(const [name,index,time] of [
  ["missing dashboard",gitStatic,null],
  ["empty dashboard",gitStatic,""],
  ["numeric dashboard",gitStatic,123],
  ["malformed dashboard",gitStatic,"not-a-timestamp"],
  ["missing index timestamp",{...gitStatic,meta:{...gitStatic.meta,source_dashboard_generated_at:undefined}},nov12],
  ["empty index timestamp",{...gitStatic,meta:{...gitStatic.meta,source_dashboard_generated_at:""}},nov12],
  ["numeric index timestamp",{...gitStatic,meta:{...gitStatic.meta,source_dashboard_generated_at:123}},nov12],
  ["malformed both",{...gitStatic,meta:{...gitStatic.meta,source_dashboard_generated_at:"not-a-timestamp"}},"not-a-timestamp"],
  ["wrong schema",{...gitStatic,schema:"wrong"},nov12],
  ["wrong source",{...gitStatic,meta:{...gitStatic.meta,source_ref:"wrong"}},nov12],
  ["wrong city count",{...gitStatic,meta:{...gitStatic.meta,expected_cities:22}},nov12],
  ["empty verified count",{...gitStatic,meta:{...gitStatic.meta,verified_count:0}},nov12]
]) assert.equal(checkStatic(index,{time}),false,"static fallback: "+name);
assert.equal(checkStatic({...neon,meta:{...neon.meta,source_dashboard_generated_at:nov12}}),
  false,"Neon static index rejected in Git mode");
assert.equal(checkStatic({...neon,meta:{...neon.meta,source_dashboard_generated_at:nov12}},
  {mode:"neon",base:"./data/neon/"}),true,"isolated Neon preview remains valid");
const releasedStatic={...releaseIndex,meta:{...releaseIndex.meta,source_dashboard_generated_at:t}};
const checkReleasedStatic=(index,time=t)=>
  Boolean(vm.runInNewContext(guard[0]+generationGuard[0]+"\n("+staticIf[1]+")",
    {index,window:{},RAW_DATA_BASE:gitBase,sourceGeneratedAt:time,state:{data:dashboard}},{timeout:1000}));
assert.equal(checkReleasedStatic(releasedStatic),true,"released Git Neon static index same generation");
assert.equal(checkReleasedStatic(releasedStatic,"2026-11-10T12:00:00Z"),false,"Git Neon static mismatch rejected");
console.log("PASS static KPI generation parity and negative recovery scenarios");

console.log("PASS live-index binding preserves source-generation synchronization and static fallback");