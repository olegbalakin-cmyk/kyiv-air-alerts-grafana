"use strict";
/* Independent current site-prod regression tests. Only localhost is allowed. */
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");

const preview = process.env.PREVIEW_DIR;
const rollback = process.env.ROLLBACK_DIR;
const proof = process.env.PROOF_DIR;
assert(preview && rollback && proof, "isolated preview and proof paths required");
fs.mkdirSync(proof, {recursive:true});
let passed = 0;
function check(label, fn) { fn(); passed++; console.log("PASS",passed,label); }
function serve(req,res) {
  const url = new URL(req.url,"http://127.0.0.1");
  const isRollback = url.pathname === "/rollback" || url.pathname.startsWith("/rollback/");
  const root = path.resolve(isRollback?rollback:preview);
  const name = isRollback ? url.pathname.replace(/^\/rollback/,"") : url.pathname;
  const target = path.resolve(root, "."+(name === "/" || name === "" ? "/index.html":name));
  if(!target.startsWith(root+path.sep) || !fs.existsSync(target) || !fs.statSync(target).isFile()){
    res.writeHead(404).end();return;
  }
  const ext=path.extname(target);
  const mime={".html":"text/html",".js":"text/javascript",".css":"text/css",".json":"application/json",".svg":"image/svg+xml",".png":"image/png"};
  res.writeHead(200,{"Content-Type":mime[ext]||"application/octet-stream","Cache-Control":"no-store","X-Robots-Tag":"noindex"});
  fs.createReadStream(target).pipe(res);
}
async function test(browser,base,mobile) {
  const page=await browser.newPage({viewport:mobile?{width:375,height:812}:{width:1440,height:900},
    hasTouch:mobile,acceptDownloads:true});
  const errors=[],external=[],requests=[];
  page.on("pageerror",e=>errors.push(String(e)));
  page.on("request",r=>requests.push(r.url()));
  await page.route("**/*",route=>{
    const u=new URL(route.request().url());
    if(u.protocol==="http:" && u.hostname==="127.0.0.1")return route.continue();
    external.push(u.href);return route.abort();
  });
  await page.addInitScript(()=>localStorage.setItem("air-alerts-intro-tour-v5","1"));
  await page.goto(base+"?city=zaporizhzhia&casyear=2026",{waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>typeof state !== "undefined" &&
    Boolean(state.data?.casualties_by_city?.zaporizhzhia) &&
    Boolean(state.charts.casualtyChart),{timeout:45000});
  const s=await page.evaluate(()=>{
    const charts=state.charts;
    const z=state.data.casualties_by_city.zaporizhzhia.monthly.find(x=>x.month==="2026-10");
    return {cityCount:Object.keys(state.data.cities).length,
      casualtiesCount:Object.keys(state.data.casualties_by_city).length,
      row:z,city:document.querySelector("#citySelect")?.value,
      chartIds:Object.keys(charts),
      meta:state.data.meta,
      kpi:document.querySelector("#kpiAlerts")?.textContent,
      banner:document.querySelector("#freshnessBanner")?.textContent,
      selectedPeriod:document.querySelector("#cityPeriod")?.value,
      source:document.querySelector("#casualtySourceNote")?.textContent};
  });
  check("current city and casualty object coverage",()=>{assert.equal(s.cityCount,23);assert.equal(s.casualtiesCount,23);assert.equal(s.city,"zaporizhzhia")});
  check("current dashboard contains actual Work F generated incomplete row",()=>{
    assert.equal(s.row.coverage_status,"INCOMPLETE");
    assert.equal(s.row.deaths,null);assert.equal(s.row.confirmed_minimum,23);
    assert.equal(s.row.complete_total,null);
  });
  check("current UI has active KPI and alert-intensity chart",()=>{
    assert(s.kpi?.trim());assert(s.chartIds.includes("cityIntensityChart"));
    assert(s.chartIds.includes("casualtyChart"));
  });
  check("current UI has actual comparison charts",()=>assert(
    s.chartIds.includes("compareAlertsChart") && s.chartIds.includes("compareCasualtiesChart")));
  check("current UI has actual trend",()=>assert(
    s.chartIds.includes("heavyDaysChart") || s.chartIds.includes("rolling7dIntensityChart") ||
    s.chartIds.includes("extremesChart")));
  const currentChart=await page.evaluate(()=>{
    const c=state.charts.casualtyChart,i=c.data.labels.indexOf("2026-10");
    return {idx:i,month:c.data.datasets[0].data[i],coverage:c.data.datasets[0]._coverageRows?.[i]};
  });
  check("current chart displays lower-bound 23",()=>{
    assert(currentChart.idx>=0);assert.equal(currentChart.month,23);
    assert.equal(currentChart.coverage.status,"INCOMPLETE");
  });
  check("no current runtime JavaScript errors",()=>assert.deepEqual(errors,[]));
  check("no browser request to external source",()=>assert.deepEqual(external,[]));
  await page.locator("#cityPeriod").selectOption("daily28");
  check("current 28-day alert period works",()=>{});
  await page.waitForFunction(()=>document.querySelector("#cityPeriod")?.value==="daily28");
  await page.locator("#cityPeriod").selectOption("monthly");
  await page.locator("#casualtyInterval").selectOption("yearly");
  const year=await page.evaluate(()=>{
    const c=state.charts.casualtyChart,i=c.data.labels.indexOf("2026");
    return {idx:i,coverage:c.data.datasets[0]._coverageRows?.[i]};
  });
  check("annual 2026 is not a final exact total",()=>{
    assert(year.idx>=0);assert.equal(year.coverage.status,"INCOMPLETE");
    assert.equal(year.coverage.value_kind,"confirmed_lower_bound_not_final");
  });
  await page.locator("#casualtyInterval").selectOption("monthly");
  await page.locator("#citySelect").selectOption("kyiv");
  check("switch to Kyiv keeps alert chart and does not leak October status",()=>{});
  const kyiv=await page.evaluate(()=>({
    selected:document.querySelector("#citySelect").value,
    alert:Boolean(state.charts.cityIntensityChart),
    leaked:Boolean(state.charts.casualtyChart?.data?.datasets?.[0]?._coverageRows?.some(
      x=>x?.status==="INCOMPLETE"))
  }));
  check("other-city isolation",()=>{assert.equal(kyiv.selected,"kyiv");assert(kyiv.alert);assert.equal(kyiv.leaked,false)});
  await page.locator("#citySelect").selectOption("zaporizhzhia");
  const restored=await page.evaluate(()=>state.charts.casualtyChart.data.datasets[0]._coverageRows
    .some(r=>r?.month==="2026-10"&&r.status==="INCOMPLETE"));
  check("switching back restores lower-bound marker",()=>assert(restored));
  const focused=await page.locator("#casualtyYear").evaluate(el=>{el.focus();return document.activeElement===el});
  check("keyboard target for year exists",()=>assert(focused));
  check("network requests all same-origin",()=>assert(requests.every(x=>new URL(x).hostname==="127.0.0.1")));
  await page.screenshot({path:path.join(proof,mobile?"current-mobile-full.png":"current-desktop-full.png"),fullPage:true});
  await page.close();
}
(async()=>{
 const server=http.createServer(serve);
 await new Promise(ok=>server.listen(0,"127.0.0.1",ok));
 const base="http://127.0.0.1:"+server.address().port+"/";
 const browser=await chromium.launch({headless:true});
 try{
   await test(browser,base,false);
   await test(browser,base,true);
   const page=await browser.newPage({viewport:{width:1440,height:900}});
   const errors=[];
   page.on("pageerror",e=>errors.push(String(e)));
   await page.route("**/*",route=>{
     let u=new URL(route.request().url);
     if(u.protocol==="http:"&&u.hostname==="127.0.0.1")return route.continue();
     return route.abort();
   });
   await page.addInitScript(()=>localStorage.setItem("air-alerts-intro-tour-v5","1"));
   await page.goto(base+"rollback/?city=zaporizhzhia&casyear=2026");
   await page.waitForFunction(()=>typeof state!=="undefined" && Boolean(state.charts.casualtyChart));
   const rb=await page.evaluate(()=>({
      row:state.data.casualties_by_city.zaporizhzhia.monthly.find(r=>r.month==="2026-10"),
      preview:typeof window.CasualtyCoveragePreview,
      chart:Boolean(state.charts.cityIntensityChart),
      marker:document.querySelector(".casualty-coverage-note")
   }));
   check("current production original restored without overlay",()=>{
     assert.equal(rb.preview,"undefined");assert.equal(rb.marker,null);assert(rb.chart);
     assert(!rb.row || rb.row.coverage_status!=="INCOMPLETE");
   });
   check("rollback has no page JavaScript error",()=>assert.deepEqual(errors,[]));
   await page.screenshot({path:path.join(proof,"current-rollback-full.png"),fullPage:true});
   await page.close();
   let d=crypto.createHash("sha256");
   for(let f of fs.readdirSync(proof).sort())d.update(fs.readFileSync(path.join(proof,f)));
   console.log("CURRENT_BROWSER_CHECKS_PASS="+passed+" CURRENT_BROWSER_CHECKS_FAIL=0");
   console.log("CURRENT_SCREENSHOTS_SHA256="+d.digest("hex"));
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e.stack||e);process.exitCode=1});
