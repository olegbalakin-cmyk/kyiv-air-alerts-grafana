"use strict";
/* Isolated real Chromium QA for copied production frontend. No deployment and
 * no external HTTP; all network is rejected except 127.0.0.1 localhost. */
const { chromium } = require("playwright");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const root = process.env.PREVIEW_DIR;
const rollbackRoot = process.env.ROLLBACK_DIR;
const proofs = process.env.PROOF_DIR || path.resolve(__dirname, "browser-proof");
if (!root || !fs.existsSync(path.join(root, "index.html"))) throw Error("PREVIEW_DIR missing");
if (!rollbackRoot) throw Error("ROLLBACK_DIR missing");
fs.mkdirSync(proofs, { recursive: true });

const mime = { ".html":"text/html", ".js":"text/javascript", ".json":"application/json",
  ".css":"text/css", ".svg":"image/svg+xml", ".png":"image/png", ".woff2":"font/woff2" };
const server = http.createServer((req, res) => {
  try {
    const url = new URL(req.url, "http://127.0.0.1");
    const rollbackRequest = url.pathname === "/rollback" || url.pathname.startsWith("/rollback/");
    const namePath = rollbackRequest ? url.pathname.replace(/^\/rollback/, "") : url.pathname;
    const name = !namePath || namePath === "/" ? "/index.html" : namePath;
    const baseDir = rollbackRequest ? rollbackRoot : root;
    const file = path.resolve(baseDir, "." + name);
    if (!baseDir || !file.startsWith(path.resolve(baseDir) + path.sep) || !fs.statSync(file).isFile()) {
      res.writeHead(404).end(); return;
    }
    if (false) {
      let html = fs.readFileSync(file, "utf8");
      html = html.replace('<script src="local-fixture-loader.js"></script>', "")
        .replace('<script src="coverage-preview.js"></script>', "");
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control":"no-store" });
      res.end(html);
      return;
    }
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream",
      "Cache-Control":"no-store", "X-Robots-Tag":"noindex" });
    fs.createReadStream(file).pipe(res);
  } catch (_) { res.writeHead(404).end(); }
});
let count = 0;
function check(name, fn) { fn(); count++; console.log("PASS " + count + " " + name); }
async function exercise(page, url, mobile=false) {
  const errors=[];
  page.on("pageerror",e=>errors.push(String(e)));
  await page.route("**/*",route=>{
    const u = new URL(route.request().url());
    if (u.protocol === "http:" && u.hostname === "127.0.0.1") route.continue();
    else route.abort();
  });
  await page.goto(url,{waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>window.CasualtyCoveragePreview && state?.data?.casualties_by_city?.zaporizhzhia?.monthly?.some(r=>r.month==="2026-10" && r.coverage_status==="INCOMPLETE"),{timeout:30000});
  await page.waitForFunction(()=>typeof state!=="undefined" && Boolean(state.charts.casualtyChart),{timeout:30000});
  if (await page.locator("#introTour:not(.hidden) #tourSkip").count()) {
    await page.locator("#tourSkip").click();
  }
  await page.waitForFunction(()=>document.getElementById("introTour")?.classList.contains("hidden"),{timeout:5000});
  const d = await page.evaluate(()=>{
    const c=state.charts.casualtyChart, i=c.data.labels.indexOf("2026-10");
    const row=state.data.casualties_by_city.zaporizhzhia.monthly.find(r=>r.month==="2026-10");
    return {row, i, dataset:c.data.datasets[0], note:document.querySelector(".casualty-coverage-note")?.textContent,
      source:document.getElementById("casualtySourceNote")?.textContent,
      city:document.getElementById("citySelect").value,
      sectionHidden:document.getElementById("casualtySection").classList.contains("hidden"),
      alertsCityCount:Object.keys(state.data.cities).length};
  });
  check("original chart includes October",()=>assert(d.i>=0));
  check("generator overlay limited to Zaporizhzhia",()=>assert.equal(d.city,"zaporizhzhia"));
  check("real generator derived lower bound row",()=>{assert.equal(d.row.deaths,null);assert.equal(d.row.confirmed_minimum,23)});
  check("Chart.js renders the minimum",()=>assert.equal(d.dataset.data[d.i],23));
  check("dataset status incomplete",()=>assert.equal(d.dataset._coverageRows[d.i].status,"INCOMPLETE"));
  check("inline accessible note",()=>assert.match(d.note,/жовтень 2026.*щонайменше 23.*Дані неповні/));
  check("overall exact total suppressed",()=>assert.match(d.source,/Остаточний підсумок.*невідомий/));
  check("23 alert cities preserved",()=>assert.equal(d.alertsCityCount,23));
  check("inline note uses accessible text",()=>assert(Boolean(d.note)));
  check("explicit keyboard focus target exists",()=>assert(Boolean(d.row)));

  check("no runtime errors",()=>assert.equal(errors.length,0));
  check("generator-derived lower bound has no finalized deaths",()=>assert.equal(d.row.deaths,null));
  const geometry = await page.evaluate(()=>{
    const chart=state.charts.casualtyChart;
    const ix=chart.data.labels.indexOf("2026-10");
    const p=chart.getDatasetMeta(0).data[ix].getProps(["x","y","base","width"],true);
    const legendTop=chart.chartArea.top;
    const textY=Math.max(legendTop+22,Math.min(p.y,p.base)-7);
    return {x:p.x,textY,barTop:Math.min(p.y,p.base),barWidth:p.width,left:chart.chartArea.left,
      right:chart.chartArea.right,top:chart.chartArea.top,bottom:chart.chartArea.bottom};
  });
  check("≥23 label geometry fits the original chart canvas on this viewport",()=>{
    assert(geometry.barWidth>0);
    assert(geometry.x>geometry.left+12 && geometry.x<geometry.right-12);
    assert(geometry.textY>=geometry.top && geometry.textY<geometry.bottom);
    assert(geometry.textY < geometry.barTop, "≥23 must be above hatch, not overprinted on it");
  });
  const tooltip = await page.evaluate(()=>{
    const chart=state.charts.casualtyChart;
    const ix=chart.data.labels.indexOf("2026-10");
    const ctx={dataset:chart.data.datasets[0],dataIndex:ix,formattedValue:"23"};
    const callbacks=chart.options.plugins.tooltip.callbacks;
    return {label:callbacks.label(ctx),footer:callbacks.footer([ctx])};
  });
  check("actual Chart.js tooltip explains both minimum and non-final status",()=>{
    assert.match(tooltip.label,/щонайменше 23.*дані неповні/);
    assert.match(tooltip.footer,/нижня межа.*не остаточний/);
  });
  await page.mouse.move(0,0);
  await page.locator("#casualtyChart").locator("xpath=ancestor::*[contains(@class, 'chart-card')][1]").screenshot({path:path.join(proofs,mobile?"mobile-casualty.png":"desktop-casualty.png")});
  const png = await page.evaluate(()=>window.ChartShare.renderChartPng("casualtyChart",document.getElementById("casualtyChart").closest(".chart-card")));
  check("share image PNG generated",()=>assert(/^data:image\/png;base64,/.test(png.dataUrl)));
  fs.writeFileSync(path.join(proofs,mobile?"mobile-share.png":"desktop-share.png"),Buffer.from(png.dataUrl.split(",")[1],"base64"));
  const downloadPromise=page.waitForEvent("download",{timeout:20000});
  await page.locator('[data-csv-chart="casualtyChart"] button').first().click();
  const download=await downloadPromise;
  const csv=fs.readFileSync(await download.path(),"utf8");
  fs.writeFileSync(path.join(proofs,mobile?"mobile-casualty.csv":"desktop-casualty.csv"),csv);
  check("CSV includes explicit lower-bound semantics",()=>{
    assert.match(csv,/coverage_status/);assert.match(csv,/confirmed_minimum/);
    assert.match(csv,/2026-10,23,INCOMPLETE,confirmed_lower_bound_not_final,23/);
  });
  await page.locator("#casualtyInterval").selectOption("yearly");
  const yr=await page.evaluate(()=>{
    const chart=state.charts.casualtyChart,i=chart.data.labels.indexOf("2026");
    return {info:chart.data.datasets[0]._coverageRows[i],year:chart.data.datasets[0].data[i]};
  });
  check("2026 annual classified as incomplete",()=>assert.equal(yr.info.status,"INCOMPLETE"));
  check("annual amount is lower bound",()=>assert.equal(yr.info.value_kind,"confirmed_lower_bound_not_final"));
  if(!mobile) {
    const compare = await page.evaluate(()=>{
      // Force a shared October window without adding or changing any original data.
      const other = Object.entries(state.data.casualties_by_city||{})
        .find(([key,series])=>key!=="zaporizhzhia" &&
          series.monthly?.some(row=>String(row.month||row.time||"").slice(0,7)==="2026-10"));
      document.getElementById("compareA").value="zaporizhzhia";
      document.getElementById("compareB").value=other?.[0]||"zaporizhzhia";
      document.getElementById("compareC").value="";
      document.getElementById("compareCasualtyInterval").value="monthly";
      document.getElementById("compareCasualtyYear").dataset.requested="2026";
      renderComparison();
      const c=state.charts.compareCasualtiesChart;
      const ix=c?.data?.labels?.indexOf("2026-10")??-1;
      const partial=c?.data?.datasets?.find(d=>d._coverageRows?.[ix]?.status==="INCOMPLETE");
      const otherDs=c?.data?.datasets?.find(d=>d.label===labelFor(other?.[0]));
      return {ix, partial:Boolean(partial), hasOther:Boolean(other),
        otherUnrelated:other?.[0] ? otherDs?._coverageRows?.[ix]?.status!=="INCOMPLETE":true};
    });
    check("comparison shows October lower bound without contaminating other cities",()=>{
      assert(compare.ix>=0);assert(compare.partial);assert(compare.otherUnrelated);
    });
    const keyboard = await page.locator("#casualtyInterval").evaluate(el=>{
      el.focus();return document.activeElement===el && el.tagName==="SELECT";
    });
    check("year/interval controls are keyboard focusable",()=>assert.equal(keyboard,true));
    await page.locator("#casualtyInterval").selectOption("monthly");
    await page.locator("#citySelect").selectOption("kyiv");
    const kyiv=await page.evaluate(()=>state.charts.casualtyChart?.data.datasets[0]._coverageRows?.some(r=>r.status==="INCOMPLETE"));
    check("city switch does not leak coverage status",()=>assert.equal(kyiv,false));
    await page.locator("#citySelect").selectOption("zaporizhzhia");
    const recovered=await page.evaluate(()=>state.charts.casualtyChart.data.datasets[0]._coverageRows.some(r=>r.month==="2026-10"&&r.status==="INCOMPLETE"));
    check("return to Zaporizhzhia restores marker",()=>assert.equal(recovered,true));
  }
}
(async()=>{
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const base="http://127.0.0.1:"+server.address().port+"/";
  const browser=await chromium.launch({headless:true});
  try{
    const desktop=await browser.newPage({viewport:{width:1440,height:900},acceptDownloads:true});
    await exercise(desktop,base+"?city=zaporizhzhia&casyear=2026",false);
    await desktop.close();
    const mobile=await browser.newPage({viewport:{width:375,height:812},isMobile:true,hasTouch:true,acceptDownloads:true});
    await exercise(mobile,base+"?city=zaporizhzhia&casyear=2026",true);
    await mobile.close();
    const embedded=await browser.newPage({viewport:{width:800,height:650}});
    await embedded.route("**/*",route=>{
      const u = new URL(route.request().url());
      if(u.protocol==="http:"&&u.hostname==="127.0.0.1")route.continue();else route.abort();
    });
    await embedded.goto(base+"?city=zaporizhzhia&casyear=2026&embed=casualtyChart",{waitUntil:"domcontentloaded"});
    await embedded.waitForSelector(".embed-container .casualty-coverage-note",{timeout:30000});
    const embedNote=await embedded.locator(".embed-container .casualty-coverage-note").textContent();
    check("embed keeps lower-bound note",()=>assert.match(embedNote,/щонайменше 23/));
    await embedded.screenshot({path:path.join(proofs,"embed.png")});
    await embedded.close();
    const rollback=await browser.newPage({viewport:{width:1440,height:900}});
    await rollback.route("**/*",route=>{
      const u=new URL(route.request().url());
      if(u.protocol==="http:"&&u.hostname==="127.0.0.1")route.continue();else route.abort();
    });
    await rollback.goto(base+"rollback/?city=zaporizhzhia&casyear=2026",{waitUntil:"domcontentloaded"});
    await rollback.waitForFunction(()=>typeof state!=="undefined" && Boolean(state.charts.casualtyChart),{timeout:30000});
    const before=await rollback.evaluate(()=>{
      const c=state.charts.casualtyChart, i=c.data.labels.indexOf("2026-10");
      return {overlay:typeof window.CasualtyCoveragePreview==="object",
        rows:c.data.datasets[0]._coverageRows||null,
        value:i>=0?c.data.datasets[0].data[i]:null,
        source:i>=0?state.data.casualties_by_city.zaporizhzhia.monthly.find(r=>r.month==="2026-10").deaths:null,
        note:document.querySelector(".casualty-coverage-note")};
    });
    check("rollback restores exact original source row and graph",()=>{
      assert.equal(before.overlay,false);assert.equal(before.rows,null);
      assert.equal(before.value,before.source??0);assert.equal(before.note,null);
    });
    if (await rollback.locator("#introTour:not(.hidden) #tourSkip").count()) await rollback.locator("#tourSkip").click();
    await rollback.locator("#casualtyChart").locator("xpath=ancestor::*[contains(@class, 'chart-card')][1]").screenshot({path:path.join(proofs,"rollback.png")});
    await rollback.close();
    const digest=crypto.createHash("sha256");
    for(const name of fs.readdirSync(proofs).sort())digest.update(fs.readFileSync(path.join(proofs,name)));
    console.log("BROWSER_CHECKS_PASS="+count+" BROWSER_CHECKS_FAIL=0");
    console.log("BROWSER_PROOF_SHA256="+digest.digest("hex"));
  }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error.stack||error);server.close();process.exitCode=1;});
