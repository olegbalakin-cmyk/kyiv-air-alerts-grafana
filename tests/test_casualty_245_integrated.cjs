const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const ROOT=path.resolve(__dirname,"../kyiv-air-alerts-grafana");
const adapter=require(path.join(ROOT,"pages-preview/casualty-partial-preview.js"));
const source=require(path.join(ROOT,"pages-preview/casualty-partial-source.js"));
const fixture=JSON.parse(fs.readFileSync(path.join(ROOT,"data/casualty_partial_months.json"),"utf8"));
const original={};
for(const [key,months] of Object.entries(fixture.cities))
  original[key]={monthly:[{month:"2026-08",deaths:0},
    {month:"2026-09",deaths:months["2026-09"].confirmed_baseline_deaths}]};
const originalBytes=JSON.stringify(original);
const view=adapter.validate(fixture,original);
assert.equal(Object.keys(view.cities).length,23);
assert.equal(view.verified_event_groups,4);
assert.equal(view.verified_minimum,11);
const expected={lutsk:6,poltava:1,"ivano-frankivsk":1,khmelnytskyi:3};
let sepKnown=0,sepUnknown=0,octUnknown=0,octKnown=0;
for(const key of Object.keys(original)){
  const rows=adapter.rows(original[key].monthly,key,view);
  assert.equal(rows.length,3);
  assert.equal(rows[1].deaths,null);
  assert.equal(rows[2].deaths,null);
  assert.equal(rows[1]._casualty_status,
    rows[1].confirmed_event_lower_bound===null?"september_unknown_not_zero":"september_partial_confirmed_lower_bound");
  if(rows[1].partial_through)sepKnown++;else sepUnknown++;
  if(Object.hasOwn(expected,key)){
    octKnown++;assert.equal(rows[2].confirmed_event_lower_bound,expected[key]);
    assert.match(adapter.sourceFor(key,view),/^https:\/\//);
  }else{
    octUnknown++;assert.equal(rows[2].confirmed_event_lower_bound,null);
    assert.equal(adapter.sourceFor(key,view),null);
  }
  const annual=rows.filter(r=>!r.is_partial_period).reduce((s,r)=>s+r.deaths,0);
  assert.equal(annual,0);
  assert.match(adapter.describeRow(rows[1],true),/incomplete/);
  assert.match(adapter.describeRow(rows[2],false),/неповний/);
}
assert.deepEqual([sepKnown,sepUnknown,octKnown,octUnknown],[4,19,4,19]);
assert.equal(JSON.stringify(original),originalBytes);
assert.equal(fixture.cities.sumy["2026-09"].confirmed_baseline_deaths,4);
assert.deepEqual(fixture.cities.sumy["2026-09"].verified_individual_event_dates,["2026-09-20"]);
function altered(change){
  const p=structuredClone(fixture);
  change(p);
  assert.throws(()=>adapter.validate(p,original));
}
altered(p=>p.promotion="ON");
altered(p=>p.publication_allowed=true);
altered(p=>p.schema="future-unknown");
altered(p=>p.cities.lutsk["2026-10"].confirmed_event_lower_bound=5);
altered(p=>p.cities.kyiv["2026-10"].confirmed_event_lower_bound=2);
altered(p=>p.cities.odesa["2026-09"].coverage_through="2026-09-30");
altered(p=>p.cities.sumy["2026-09"].confirmed_baseline_deaths=5);
altered(p=>p.cities.lutsk["2026-10"].provenance.incident_ids=["incident:poltava:2026-10-17:oops"]);
altered(p=>p.cities.lutsk["2026-10"].monthly_exact_total=6);
altered(p=>delete p.cities.kyiv);
const withOctober=structuredClone(original);
withOctober.kyiv.monthly.push({month:"2026-10",deaths:0});
assert.throws(()=>adapter.validate(fixture,withOctober));
const tampered=structuredClone(original);
tampered.kyiv.monthly.at(-1).deaths+=1;
assert.throws(()=>adapter.validate(fixture,tampered));
(async()=>{
  const te=new TextEncoder();
  const hash=async str=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",te.encode(str)))).map(v=>v.toString(16).padStart(2,"0")).join("");
  const originalCrypto=globalThis.crypto;
  if(!globalThis.crypto)globalThis.crypto=require("node:crypto").webcrypto;
  const localBody=fs.readFileSync(path.join(ROOT,"data/casualty_partial_months.json"),"utf8");
  const dashboard=JSON.stringify({cities:Object.fromEntries(Object.keys(original).map(k=>[k,{}])),casualties_by_city:original});
  const binding={schema:"casualty-245-frozen-binding-v1",mode:"frozen_test",site_prod_sha:fixture.baseline_ref.slice(10),
    dashboard_sha256:await source.digest(dashboard),sidecar_sha256:await source.digest(localBody),promotion:"OFF",production:false};
  const response=(text,status=200)=>({ok:status===200,status,text:async()=>text});
  const map=new Map([["data.json",dashboard],["casualty_partial_months.json",localBody],
    ["casualty-test-binding.json",JSON.stringify(binding)]]);
  const req=async (url)=>map.has(url)?response(map.get(url)):response("missing",404);
  const pair=await source.load("frozen_test",req);
  assert.equal(pair.mode,"frozen_test");
  assert.equal(adapter.validate(pair.sidecar,pair.dashboard.casualties_by_city).verified_minimum,11);
  const rejectRead=async (m,changes)=>{
    const map2=new Map(map);
    for(const [k,v] of changes)map2.set(k,v);
    await assert.rejects(()=>source.load(m,async url=>map2.has(url)?response(map2.get(url)):response("missing",404)));
  };
  await rejectRead("frozen_test",[["casualty_partial_months.json","{}"]]);
  await rejectRead("frozen_test",[["data.json","{}"]]);
  await rejectRead("frozen_test",[["casualty-test-binding.json",JSON.stringify({...binding,site_prod_sha:"bad"})]]);
  const sha="58634812155ddc6b4324c26d694cf3de6cfb9bbe";
  const before={object:{sha}},after={object:{sha:"a".repeat(40)}};
  const shaUrl=source.HEAD_URL;
  const base="https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/"+sha+"/kyiv-air-alerts-grafana/data/";
  const canonicalMap=new Map([[base+"dashboard_data.json",dashboard],[source.CANONICAL,localBody],
    [base+"casualty_partial_months.json",localBody]]);
  let count=0;
  const moving=async url=>url===shaUrl?response(JSON.stringify(++count===1?before:after)):
    response(canonicalMap.get(url)||"",canonicalMap.has(url)?200:404);
  await assert.rejects(()=>source.load("canonical_site_prod",moving),/advanced/);
  count=0;
  const stable=async url=>url===shaUrl?response(JSON.stringify(before)):
    response(canonicalMap.get(url)||"",canonicalMap.has(url)?200:404);
  const pinned=await source.load("canonical_site_prod",stable);
  assert.equal(pinned.sourceSha,sha);
  const drift=new Map(canonicalMap);drift.set(source.CANONICAL,"{}");
  await assert.rejects(()=>source.load("canonical_site_prod",async url=>url===shaUrl?
    response(JSON.stringify(before)):response(drift.get(url)||"",drift.has(url)?200:404)),/differs/);
  await assert.rejects(()=>source.load("canonical_site_prod",async url=>url===shaUrl?
    response(JSON.stringify(before)):response("missing",404)),/HTTP/);
  await assert.rejects(()=>source.load("unrecognized",req),/unapproved/);
  console.log("CASUALTY_245_OFFLINE_PASS 23_CITIES SEP_56_4_CUTOFFS OCT_4EVENT_11 19_UNKNOWN NO_PROMOTE source_read_negative_tests");
})().catch(e=>{console.error(e);process.exitCode=1});
