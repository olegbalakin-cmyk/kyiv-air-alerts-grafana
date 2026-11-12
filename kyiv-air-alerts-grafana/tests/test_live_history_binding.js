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
const check=(index,{mode,base=gitBase,time=t}={})=>{
  const context={window:mode?{PREVIEW_CONFIG:{source:mode}}:{},
    RAW_DATA_BASE:base,sourceGeneratedAt:time};
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
console.log("PASS scoped Neon historical index positive/negative cases");

console.log("PASS live-index binding preserves source-generation synchronization and static fallback");