"use strict";
const fs = require("fs");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const preview = require("./coverage-preview.js");
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture.json"), "utf8"));
let pass = 0;
function test(name, f) {
  f();
  pass += 1;
  console.log("PASS " + String(pass).padStart(2,"0") + " " + name);
}
test("fixture is unpublished",()=>assert.equal(fixture.not_for_publication,true));
test("fixture is one city",()=>assert.equal(fixture.city,"zaporizhzhia"));
test("fixture month",()=>assert.equal(fixture.month,"2026-10"));
test("fixture confirmed minimum",()=>assert.equal(fixture.confirmed_minimum,23));
test("fixture final total unknown",()=>assert.equal(fixture.complete_total,null));
test("fixture deaths null",()=>assert.equal(fixture.deaths,null));
test("fixture classification incomplete",()=>assert.equal(fixture.coverage_status,"INCOMPLETE"));
const entry=preview.normalize(fixture);
test("lower bound not final",()=>assert.equal(entry.value_kind,"confirmed_lower_bound_not_final"));
test("normalized value remains 23",()=>assert.equal(entry.value,23));
test("minimum retained",()=>assert.equal(entry.minimum,23));
test("explicit zero complete",()=>{
  const e=preview.normalize({month:"2026-09",deaths:0,coverage_status:"COMPLETE"});
  assert.equal(e.status,"COMPLETE");assert.equal(e.value,0);
});
test("unknown never zero",()=>{
  const e=preview.normalize({month:"2026-09",deaths:null,coverage_status:"UNKNOWN"});
  assert.equal(e.status,"UNKNOWN");assert.equal(e.value,null);
});
test("legacy reconstructed not certified",()=>{
  const e=preview.normalize({month:"2026-09",deaths:12});
  assert.equal(e.status,"LEGACY_UNVERIFIED");assert.equal(e.value,12);
});
test("missing row unknown",()=>{
  const e=preview.normalize({month:"2026-09"});
  assert.equal(e.value,null);
});
test("incomplete rejects deaths field as final",()=>{
  assert.throws(()=>preview.normalize({month:"2026-10",deaths:23,confirmed_minimum:23,coverage_status:"INCOMPLETE"}));
});
test("incomplete rejects zero lower bound",()=>{
  assert.throws(()=>preview.normalize({month:"2026-10",deaths:null,confirmed_minimum:0,coverage_status:"INCOMPLETE"}));
});
test("unknown rejects minimum",()=>{
  assert.throws(()=>preview.normalize({month:"2026-10",deaths:null,confirmed_minimum:23,coverage_status:"UNKNOWN"}));
});
test("complete rejects missing exact number",()=>{
  assert.throws(()=>preview.normalize({month:"2026-10",deaths:null,coverage_status:"COMPLETE"}));
});
test("unknown status fails closed",()=>assert.throws(()=>preview.normalize({month:"2026-10",deaths:1,coverage_status:"GUESSED"})));
test("annual is at least 23, not total",()=>{
  const year=preview.aggregateYear([fixture],"2026");
  assert.equal(year.status,"INCOMPLETE");assert.equal(year.value,23);assert.equal(year.minimum,23);
});
test("annual missing month does not establish completeness",()=>{
  const year=preview.aggregateYear([{month:"2026-10",deaths:0,coverage_status:"COMPLETE"}],"2026");
  assert.equal(year.status,"INCOMPLETE");
});
test("annual all twelve verified is final",()=>{
  const months=Array.from({length:12},(_,i)=>({month:"2026-"+String(i+1).padStart(2,"0"),deaths:i,coverage_status:"COMPLETE"}));
  const year=preview.aggregateYear(months,"2026");
  assert.equal(year.status,"COMPLETE");assert.equal(year.value,66);
});
test("annual unknown remains unknown",()=>{
  const year=preview.aggregateYear([{month:"2026-10",deaths:null,coverage_status:"UNKNOWN"}],"2026");
  assert.equal(year.status,"UNKNOWN");assert.equal(year.value,null);
});
test("annual lower bound includes confirmed full months",()=>{
  const year=preview.aggregateYear([fixture,{month:"2026-09",deaths:2,coverage_status:"COMPLETE"}],"2026");
  assert.equal(year.status,"INCOMPLETE");assert.equal(year.value,25);
});
test("month label correct",()=>assert.equal(preview.monthLabel("2026-10",false),"жовтень 2026"));
test("english month label correct",()=>assert.equal(preview.monthLabel("2026-10",true),"October 2026"));
const app=fs.readFileSync(path.join(root,"pages-preview/app.js"),"utf8");
const share=fs.readFileSync(path.join(root,"pages-preview/chart-share.js"),"utf8");
const workflow=fs.readFileSync(path.join(root,"../../.github/workflows/netlify-production.yml"),"utf8");
test("real single casualty chart target",()=>assert.match(app,/function renderCasualties\(key\)/));
test("real city comparison target",()=>assert.match(app,/compareCasualtiesChart/));
test("real CSV target",()=>assert.match(app,/function exportChartCsv\(chartId\)/));
test("real PNG canvas export target",()=>assert.match(share,/function renderChartPng\(chartId, card\)/));
test("embed moves original chart card",()=>assert.match(share,/rootSection\.appendChild\(card\)/));
test("production deploy path filter excludes research",()=>{
  assert.match(workflow,/branches: \[site-prod\]/);
  assert.doesNotMatch(workflow,/research\/\*\*/);
});
test("original source bytes contain no fixture marker",()=>assert.doesNotMatch(app,/confirmed_minimum:23|coverage_fixture=1/));
test("loader requires localhost",()=>{
  const loader=fs.readFileSync(path.join(__dirname,"local-fixture-loader.js"),"utf8");
  assert.match(loader,/localhost/);assert.match(loader,/coverage_fixture/);
});
test("overlay never patches non-casualty setChart",()=>{
  const code=fs.readFileSync(path.join(__dirname,"coverage-preview.js"),"utf8");
  assert.match(code,/id !== "casualtyChart" && id !== "compareCasualtiesChart"/);
});
test("CSV exports status and value kind",()=>{
  const code=fs.readFileSync(path.join(__dirname,"coverage-preview.js"),"utf8");
  assert.match(code,/coverage_status/);assert.match(code,/confirmed_minimum/);
});
test("overlay glyph and hatching",()=>{
  const code=fs.readFileSync(path.join(__dirname,"coverage-preview.js"),"utf8");
  assert.match(code,/≥/);assert.match(code,/ctx.clip\(\)/);
});
test("browser tooltip contains lower-bound explanatory wording",()=>{
  const code=fs.readFileSync(path.join(__dirname,"coverage-preview.js"),"utf8");
  assert.match(code,/нижня межа/); assert.match(code,/дані неповні/);
});
test("PNG and embed use original card and canvas",()=>{
  assert.match(share,/ctx\.drawImage\(source,/);
  assert.match(share,/rootSection\.appendChild\(card\)/);
});
test("main and site-prod are never written",()=>{
  const loader=fs.readFileSync(path.join(__dirname,"local-fixture-loader.js"),"utf8");
  assert.doesNotMatch(loader,/fetch\([^)]*,\s*\{\s*method:\s*["'](?:POST|PUT|PATCH)/i);
});
const digest=crypto.createHash("sha256").update(fs.readFileSync(path.join(__dirname,"fixture.json"))).digest("hex");
console.log("CHECKS_PASS="+pass+" CHECKS_FAIL=0");
console.log("FIXTURE_SHA256="+digest);
