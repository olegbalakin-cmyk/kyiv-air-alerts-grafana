/* Offline release contract for Kyiv Feb 2022 provisional UI. Node 20, no HTTP. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const ROOT=path.resolve(__dirname,"../..");
const DATA=path.join(ROOT,"kyiv-air-alerts-grafana/pages-preview/kyiv-early-2022-preview.json");
const SCRIPT=path.join(ROOT,"kyiv-air-alerts-grafana/pages-preview/kyiv-early-2022-preview.js");
const INDEX=path.join(ROOT,"kyiv-air-alerts-grafana/pages-preview/index.html");
const BUILD=path.join(ROOT,"netlify.toml");
const canonicalNames=["dashboard_data.json","alerts_combined.json","site_derived.json","kyiv_threat_mix.json"];
const before=Object.fromEntries(canonicalNames.map(n=>{
  const p=path.join(ROOT,"kyiv-air-alerts-grafana/data",n);
  return [n,fs.readFileSync(p)];
}));
const mod=require(SCRIPT);
const source=JSON.parse(fs.readFileSync(DATA,"utf8"));
const result=mod.validate(source);
assert.deepEqual(result.counts,[1,9,6,8]);
assert.deepEqual(result.daily,[3600,15300,10800,11466]);
assert.equal(result.earlySeconds,41166);
assert.equal(result.carrySeconds,1416);
assert.equal(result.thirty,19);
assert.equal(source.events.length,24);
assert(source.events.every(e=>e.confirmed_end===null&&e.confidence==="unverified"));
for(const update of [
  o=>{o.events[0].confirmed_end=o.events[0].estimated_end},
  o=>{o.city_key="odesa"},
  o=>{o.status="verified"},
  o=>{o.events[0].start=o.events[1].start},
  o=>{o.not_in_verified_kpi=false},
  o=>{o.events[0].estimated_end="2022-02-24T15:00:00+02:00"},
  o=>{o.events[0].estimated_end="2022-02-24T15:44:57+02:00"},
  o=>{o.events.push({...o.events[0]})},
]) {
  const test=structuredClone(source);update(test);
  assert.throws(()=>mod.validate(test));
}
const html=fs.readFileSync(INDEX,"utf8");
const build=fs.readFileSync(BUILD,"utf8");
assert.equal(html.split('id="kyivEarlyPreviewSection"').length,2);
assert.match(html,/kyiv-early-2022-preview.js\?v=20261117-research1/);
assert.match(html,/id="kyivEarlyDaily"/);
assert.match(html,/id="kyivEarlyEvents"/);
assert.match(build,/kyiv-early-2022-preview.js kyiv-air-alerts-grafana\/pages-preview\/kyiv-early-2022-preview.json _site\//);
assert.match(fs.readFileSync(SCRIPT,"utf8"),/select.value!=="kyiv"/);
for(const name of canonicalNames) {
  const after=fs.readFileSync(path.join(ROOT,"kyiv-air-alerts-grafana/data",name));
  assert.deepEqual(before[name],after,name+" was mutated by test");
}
console.log("KYIV_EARLY_PREVIEW_OFFLINE_PASS: counts, 4-day seconds, midnight carryover, fail-closed cases, assets, canonical invariance");
