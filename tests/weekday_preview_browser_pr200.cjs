/* Browser smoke test for isolated PR #200 Netlify preview. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const {chromium} = require("playwright");

(async () => {
  const url = process.env.WEEKDAY_PREVIEW_URL;
  assert.match(url || "", /^https:\/\/weekday-pr200-20261119--ukraine-air-alerts\.netlify\.app\/$/);
  fs.mkdirSync("_preview-proof", {recursive:true});
  const browser = await chromium.launch({headless:true});
  const evidence = {url, tests:[], pageErrors:[]};
  async function ready(page) {
    try { await page.waitForFunction(() => {
      const meta=document.getElementById("weekdayMeta")?.textContent||"";
      const one=document.getElementById("weekdayStartsChart");
      const two=document.getElementById("weekdayHoursChart");
      return meta.includes("20") && window.Chart && one && two &&
        Chart.getChart(one)?.data?.datasets?.[0]?.data?.length === 7 &&
        Chart.getChart(two)?.data?.datasets?.[0]?.data?.length === 7;
    }, null, {timeout:20000}); } catch(error) {
      const diagnostic = await page.evaluate(() => ({url:location.href,ready:document.readyState,chart:typeof Chart,meta:document.querySelector("#weekdayMeta")?.textContent,section:!!document.querySelector("#weekdaySection"),scripts:[...document.scripts].map(x=>x.src),errors:document.querySelector("#freshnessBanner")?.textContent}));
      console.error("WEEKDAY_DIAGNOSTIC",JSON.stringify(diagnostic));
      await page.screenshot({path:"_preview-proof/failed-browser-state.png",fullPage:true});
      throw error;
    }
  }
  try {
    const ua = await browser.newPage({viewport:{width:1440,height:900},acceptDownloads:true});
    ua.on("pageerror", error => evidence.pageErrors.push("UA: "+error.message));
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
    await ua.screenshot({path:"_preview-proof/weekday-ua-desktop.png",fullPage:true});

    const en=await browser.newPage({viewport:{width:1440,height:900}});
    en.on("pageerror", error=>evidence.pageErrors.push("EN: "+error.message));
    await en.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
    await ready(en);
    await en.locator("#langEn").click();
    await en.waitForFunction(()=>document.querySelector("#weekdaySection h2")?.textContent==="Air alerts by weekday",null,{timeout:10000});
    assert.match(await en.locator("#weekdayMeta").innerText(),/completed days/);
    evidence.tests.push("English copy and charts rendered");
    await en.screenshot({path:"_preview-proof/weekday-en-desktop.png",fullPage:true});

    const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
    mobile.on("pageerror",error=>evidence.pageErrors.push("Mobile: "+error.message));
    await mobile.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
    await ready(mobile);
    assert.equal(await mobile.locator("#weekdaySection").isVisible(),true);
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
