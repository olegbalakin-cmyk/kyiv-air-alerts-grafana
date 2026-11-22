const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const adapter = require("../kyiv-air-alerts-grafana/pages-preview/casualty-partial-preview.js");
const payload=JSON.parse(readFileSync(path.join(__dirname,"../kyiv-air-alerts-grafana/pages-preview/casualty-october-2026-preview.json"),"utf8"));
const baseline=Object.fromEntries(payload.cities.map(c=>[c.city_slug,{monthly:[
  {month:"2026-08",deaths:0},{month:"2026-09",deaths:2}
]}]));
const original=JSON.stringify(baseline);
const view=adapter.validate(payload,baseline);
assert.equal(view.verified_minimum,11);
assert.equal(Object.keys(view.cities).length,23);
const expected={lutsk:6,poltava:1,"ivano-frankivsk":1,khmelnytskyi:3};
let nKnown=0,nUnknown=0;
for(const city of Object.keys(baseline)){
  const r=adapter.rows(baseline[city].monthly,city,view);
  assert.equal(r.length,3);
  assert.equal(r[2].month,"2026-10");
  assert.equal(r[2].deaths,null);
  assert.equal(r[2].is_partial_period,true);
  assert.equal(r.filter(v=>!v.is_partial_period).reduce((n,v)=>n+v.deaths,0),2);
  if(Object.hasOwn(expected,city)){
    nKnown++;
    assert.equal(r[2].confirmed_event_lower_bound,expected[city]);
    assert.match(adapter.description(city,view,false),/щонайменше/);
    assert.match(adapter.description(city,view,true),/at least/);
    assert.match(adapter.sourceFor(city),/^https:\/\//);
  }else{
    nUnknown++;
    assert.equal(r[2].confirmed_event_lower_bound,null);
    assert.equal(r[2]._casualty_status,"unknown_not_zero");
    assert.match(adapter.description(city,view,true),/not zero/);
  }
}
assert.equal(nKnown,4);assert.equal(nUnknown,19);
assert.equal(JSON.stringify(baseline),original);
assert.throws(()=>adapter.validate({...payload,promotion:"ON"},baseline));
assert.throws(()=>adapter.validate({...payload,cities:payload.cities.slice(1)},baseline));
const tampered=structuredClone(payload);
tampered.cities.find(c=>c.city_slug==="kyiv").confirmed_event_lower_bound=0;
assert.throws(()=>adapter.validate(tampered,baseline));
const withOctober=structuredClone(baseline);
withOctober.kyiv.monthly.push({month:"2026-10",deaths:0});
assert.throws(()=>adapter.validate(payload,withOctober));
const stale=structuredClone(baseline);
stale.lutsk.monthly.pop();
assert.throws(()=>adapter.validate(payload,stale));
assert.equal(adapter.rows(baseline.lutsk.monthly,"lutsk",null),baseline.lutsk.monthly);
console.log("CASUALTY_UI_SIDECAR_OFFLINE_PASS 23_CITIES 4_MINIMUMS 19_UNKNOWN NO_YEAR_EXACT NO_SITE_WRITES");
