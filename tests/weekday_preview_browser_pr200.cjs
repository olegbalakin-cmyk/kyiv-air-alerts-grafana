/* Browser smoke test for isolated PR #200 Netlify preview. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const {chromium} = require("playwright");

(async () => {
  const url = process.env.WEEKDAY_PREVIEW_URL;
  assert.match(url || "", /^https:\/\/weekday-pr200-20261119--ukraine-air-alerts\.netlify\.app\/$/);
  fs.mkdirSync("_preview-proof", {recursive:true});
  const browser = await chromium.launch({headless:true});
  const evidence = {url, tests:[], pageErrors:[], consoleErrors:[], network:[]};
  async function ready(page) {
    try { await page.waitForFunction(() => {
      const meta=document.getElementById("weekdayMeta")?.textContent||"";
      const one=document.getElementById("weekdayStartsChart");
      const two=document.getElementById("weekdayHoursChart");
      return meta.includes("20") && window.Chart && one && two &&
        Chart.getChart(one)?.data?.datasets?.[0]?.data?.length === 7 &&
        Chart.getChart(two)?.data?.datasets?.[0]?.data?.length === 7;
    }, null, {timeout:8000}); } catch(error) {
      const diagnostic = await page.evaluate(() => ({url:location.href,ready:document.readyState,chart:typeof Chart,meta:document.querySelector("#weekdayMeta")?.textContent,section:!!document.querySelector("#weekdaySection"),scripts:[...document.scripts].map(x=>x.src),errors:document.querySelector("#freshnessBanner")?.textContent, kpi:document.querySelector("#kpiAlerts")?.textContent, city:document.querySelector("#cityTitle")?.textContent, weekdayApi:!!window.WeekdayUI, weekdayLogic:!!window.WeekdayDistribution, resources:performance.getEntriesByType("resource").slice(-12).map(x=>({name:x.name,duration:x.duration,bytes:x.transferSize}))}));
      console.error("WEEKDAY_DIAGNOSTIC",JSON.stringify(diagnostic),"PAGE_ERRORS",JSON.stringify(evidence.pageErrors),"CONSOLE_ERRORS",JSON.stringify(evidence.consoleErrors),"NETWORK",JSON.stringify(evidence.network));
      await page.screenshot({path:"_preview-proof/failed-browser-state.png",fullPage:true});
      throw error;
    }
  }
  try {
    const ua = await browser.newPage({viewport:{width:1440,height:900},acceptDownloads:true});
    ua.on("pageerror", error => evidence.pageErrors.push("UA: "+error.message));
    ua.on("console", msg=>{if(msg.type()==="error") evidence.consoleErrors.push(msg.text());});
    ua.on("response", response=>{if(/weekday-(ui|distribution)\.js/.test(response.url())) evidence.network.push({url:response.url(),status:response.status(),contentType:response.headers()["content-type"]});});
    const response = await ua.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
    assert.equal(response.status(), 200, "preview HTTP 200");
    await ready(ua);
    const initial=await ua.locator("#weekdayMeta").innerText();
    assert.match(initial,/завершених днів/);
    evidence.tests.push("UA: both 7-day charts rendered");
    await ua.selectOption("#weekdayRange","90d");
    const ninety=await ua.locator("#weekdayMeta").innerText();
    assert.notEqual(ninety,initial,"90d filter changes totals");
    evidence.tests.push("90-day period filter changes displayed statistics");
    await ua.selectOption("#weekdayRange","180d");
    const oneEighty=await ua.locator("#weekdayMeta").innerText();
    assert.notEqual(oneEighty,ninety,"180d filter differs from 90d with sufficient city history");
    evidence.tests.push("180-day filter recalculates both charts");
    const end=await ua.locator("#weekdayDateTo").inputValue();
    await ua.selectOption("#weekdayRange","custom");
    await ua.locator("#weekdayDateFrom").fill(end);
    await ua.locator("#weekdayDateFrom").dispatchEvent("change");
    const custom=await ua.locator("#weekdayMeta").innerText();
    assert.ok(custom.startsWith(end+" — "+end),"custom date field updates both charts");
    evidence.tests.push("Custom From/To date filter applies");
    const downloadPromise=ua.waitForEvent("download",{timeout:15000});
    await ua.locator("#weekdayCsv").click();
    const download=await downloadPromise;
    assert.ok(download.suggestedFilename().endsWith(".csv"));
    evidence.tests.push("CSV download available");
    await ua.selectOption("#weekdayRange","28d");
    await ua.locator("#weekdaySplitEnabled").check();
    await ua.waitForFunction(() =>
      document.querySelector("#weekdaySplitStatus")?.textContent?.includes("Точний розподіл"),
      null,{timeout:20000});
    const fourBands=await ua.evaluate(()=>Chart.getChart(document.querySelector("#weekdayHoursChart")).data.datasets.length);
    assert.equal(fourBands,4,"four locally timed bands from verified source");
    await ua.selectOption("#weekdaySplitMode","daynight");
    const twoBands=await ua.evaluate(()=>Chart.getChart(document.querySelector("#weekdayHoursChart")).data.datasets.map(x=>x.label));
    assert.equal(twoBands.length,2,"day and evening-night datasets");
    assert.match(twoBands[0],/09–18/);
    evidence.tests.push("Four exact bands and day/evening-night switch render with daily parity");
    await ua.locator("#weekdaySplitEnabled").uncheck();
    const totalDatasetCount=await ua.evaluate(()=>Chart.getChart(document.querySelector("#weekdayHoursChart")).data.datasets.length);
    assert.equal(totalDatasetCount,1,"unchecked split returns verified base chart");
    evidence.tests.push("Checkbox restores original hours chart");
    await ua.screenshot({path:"_preview-proof/weekday-ua-desktop.png",fullPage:true});

    const en=await browser.newPage({viewport:{width:1440,height:900}});
    en.on("pageerror", error=>evidence.pageErrors.push("EN: "+error.message));
    await en.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
    await ready(en);
    await en.locator("#langEn").click();
    await en.waitForFunction(()=>document.querySelector("#weekdaySection h2")?.textContent==="Air alerts by weekday",null,{timeout:10000});
    assert.match(await en.locator("#weekdayMeta").innerText(),/completed days/);
    assert.match(await en.locator(".weekday-split-check span").innerText(),/Split by time of day/);
    evidence.tests.push("English weekday split and tour copy localized");
    evidence.tests.push("English copy and charts rendered");
    await en.screenshot({path:"_preview-proof/weekday-en-desktop.png",fullPage:true});

    const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
    mobile.on("pageerror",error=>evidence.pageErrors.push("Mobile: "+error.message));
    await mobile.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
    await ready(mobile);
    assert.equal(await mobile.locator("#weekdaySection").isVisible(),true);
    assert.equal(await mobile.locator("#weekdaySplitEnabled").isVisible(),true);
    evidence.tests.push("Mobile 390x844: split checkbox displayed");
    evidence.tests.push("Mobile 390x844: weekday charts rendered");
    evidence.mobileHorizontalOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
    await mobile.screenshot({path:"_preview-proof/weekday-ua-mobile.png",fullPage:true});
    fs.writeFileSync("_preview-proof/browser-report.json",JSON.stringify(evidence,null,2)+"\n");
    console.log("WEEKDAY_BROWSER_QA_PASS",JSON.stringify(evidence));
    assert.equal(evidence.pageErrors.length,0,"No JS page errors");
  } finally {
    await browser.close();
  }
})().catch(err=>{console.error(err);process.exitCode=1;});
