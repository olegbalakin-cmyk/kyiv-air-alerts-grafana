/* No-network, fail-closed regression for the separate Kyiv provisional label. */
const test=require("node:test"),assert=require("node:assert/strict");
const api=require("../kyiv-air-alerts-grafana/pages-preview/kyiv-active-provisional.js");
const base=require("../kyiv-air-alerts-grafana/pages-preview/kyiv-active-provisional-test.json");
const now=new Date("2026-11-20T06:00:00Z");
test("source-bound unclosed interval displays precisely 6h05 at 07:24 Kyiv",()=>{
 const x=api.evaluate(base,now);assert.ok(x);assert.equal(x.hours,6);assert.equal(x.remainingMinutes,5);
 assert.equal(x.minutes,365);assert.equal(x.date,"2026-11-20");
});
test("no wall clock growth; same 365 minutes when viewed later",()=>{
 assert.equal(api.evaluate(base,new Date("2026-11-20T10:00:00Z")).minutes,365);
});
test("stale or next Kyiv calendar day hidden, not shown as current",()=>{
 assert.equal(api.evaluate(base,new Date("2026-11-20T14:00:00Z")),null);
 assert.equal(api.evaluate(base,new Date("2026-11-20T23:30:00Z")),null);
});
test("missing or ambiguous end/source/start/time is blocked",()=>{
 const invalid=[
  {...base,ends_at:"2026-11-20T08:00:00+02:00"},
  {...base,status:"completed"}, {...base,status:"unknown"},
  {...base,city_key:"kharkiv"}, {...base,source:"unaudited"},
  {...base,alert_type:"UNKNOWN"}, {...base,source_body_sha256:"invalid"},
  {...base,started_at:"2026-11-20T07:30:00+02:00"},
  {...base,captured_at:"2026-11-19T05:24:02Z"},
  {...base,test_only:false}, {...base,github_run_id:1}
 ];
 invalid.forEach(x=>assert.equal(api.evaluate(x,now),null));
});
test("snapshot is separate from verified history, and source capture remains immutable",()=>{
 assert.equal(base.publication_allowed,false);assert.equal(base.neon_writes,0);
 assert.equal(base.archive_change,false);assert.equal(base.ends_at,null);
 const old=base.captured_at; api.evaluate(base,now); assert.equal(base.captured_at,old);
});
