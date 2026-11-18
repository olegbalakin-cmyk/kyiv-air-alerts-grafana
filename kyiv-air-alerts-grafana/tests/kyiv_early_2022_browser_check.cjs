"use strict";
/* Real browser QA on separately deployed manual Netlify alias only. */
const {chromium}=require("playwright");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {URL}=require("node:url");
const raw=process.env.KYIV_EARLY_TEST_PREVIEW_URL||"";
const u=new URL(raw);
assert.equal(u.protocol,"https:");
assert.match(u.hostname,/^kyiv-early-pr199-20261118--ukraine-air-alerts\.netlify\.app$/);
const proof=path.resolve(process.env.KYIV_EARLY_BROWSER_PROOF_DIR||"_preview-proof");
fs.mkdirSync(proof,{recursive:true});
const report={url:u.origin,checks:[],console_page_errors:[],screenshots:[]};
async function main(){
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900},locale:"uk-UA"});
async function checks(locale,viewport) {
  const page=await context.newPage();
  if(viewport)await page.setViewportSize(viewport);
  const errors=[];
  page.on("pageerror",err=>errors.push(err.message));
  const target=new URL(locale==="en"?"/en/":"/",u);
  await page.goto(target.toString(),{waitUntil:"domcontentloaded",timeout:60000});
  await page.waitForSelector('#citySelect option[value="kyiv"]',{state:"attached",timeout:60000});
  await page.selectOption("#citySelect","kyiv");
  await page.waitForFunction(()=>{
    const panel=document.getElementById("kyivEarlyPreviewSection");
    return panel&&!panel.hidden&&!panel.dataset.error&&
      document.querySelectorAll("#kyivEarlyDaily tr").length===4 &&
      document.querySelectorAll("#kyivEarlyEvents tr").length===24;
  },null,{timeout:60000});
  const panel=page.locator("#kyivEarlyPreviewSection");
  const title=await page.locator("#kyivEarlyTitle").innerText();
  assert.match(title,locale==="en"?/early history/i:/Рання історія/);
  const totals=await page.locator("#kyivEarlyTotal").innerText();
  assert.match(totals,/24 /);
  const status=await page.locator("#kyivEarlyNote").innerText();
  assert.match(status,locale==="en"?/unverified|incomplete/i:/неповн|умовним/);
  const kpiBefore=await page.locator("#kpiAlerts").innerText();
  const selectedRangeBefore=await page.locator("#cityDateFrom").inputValue()+"|"+await page.locator("#cityDateTo").inputValue();
  assert(kpiBefore&&!["—","-"].includes(kpiBefore),"Primary verified KPI is unavailable");
  assert.equal(await page.locator("#kyivEarlyDaily tr").count(),4);
  assert.equal(await page.locator("#kyivEarlyEvents tr").count(),24);
  assert.equal(await page.locator("#kyivEarlyEvents tr").last().locator("td").count(),4);
  const filename="kyiv_"+locale+(viewport?"_mobile":"_desktop")+".png";
  await panel.screenshot({path:path.join(proof,filename)});
  report.screenshots.push(filename);
  if(!viewport) {
    await page.selectOption("#citySelect","lviv");
    await page.waitForFunction(()=>document.getElementById("kyivEarlyPreviewSection").hidden);
    await page.selectOption("#citySelect","kyiv");
    await page.waitForFunction(()=>!document.getElementById("kyivEarlyPreviewSection").hidden);
    await page.waitForFunction(()=>{const el=document.getElementById("kpiAlerts");return el&&el.textContent.trim()&&el.textContent.trim()!=="—";},{},{timeout:20000});
    await page.waitForTimeout(600);
    const selectedRangeAfter=await page.locator("#cityDateFrom").inputValue()+"|"+await page.locator("#cityDateTo").inputValue();
    const kpiAfter=await page.locator("#kpiAlerts").innerText();
    if(selectedRangeAfter===selectedRangeBefore) {
      assert.equal(kpiAfter,kpiBefore,"Verified Kyiv alert KPI changed for exactly the same date range");
    }
    report.checks.push({locale,city_switch:"PASS",range_before:selectedRangeBefore,
      range_after:selectedRangeAfter,kpi_before:kpiBefore,kpi_after:kpiAfter,
      range_change_expected:selectedRangeBefore!==selectedRangeAfter});
  } else {
    const b=await panel.boundingBox();
    assert(b&&b.x>=-3&&b.x+b.width<=viewport.width+3,"Mobile preview card overflows viewport");
  }
  assert(!await panel.getAttribute("data-error"),"Shadow preview JS reported an error");
  report.checks.push({locale,viewport:viewport||"desktop",title,totals,verified_kpi:kpiBefore,
                      row_count:24,daily_rows:4,city_switch:!viewport?"PASS":"not-applicable"});
  report.console_page_errors.push(...errors.map(message=>({locale,message})));
  await page.close();
}
try {
  await checks("uk");
  await checks("en");
  await checks("uk",{width:390,height:844});
  assert.equal(report.checks.length,5);
  // A pageerror in unrelated currently deployed code is reported, not silently called a pass.
  if(report.console_page_errors.length>0)throw new Error("Browser page errors: "+JSON.stringify(report.console_page_errors).slice(0,1000));
  report.status="PASS";
  fs.writeFileSync(path.join(proof,"browser-report.json"),JSON.stringify(report,null,2)+"\n");
  console.log("KYIV_EARLY_ACTUAL_BROWSER_PASS "+JSON.stringify(report.checks));
} catch(error) {
  report.status="FAIL";
  report.error=String(error);
  fs.writeFileSync(path.join(proof,"browser-report.json"),JSON.stringify(report,null,2)+"\n");
  throw error;
} finally {
  await context.close();
  await browser.close();
}

}
main().catch(err=>{console.error(err);process.exitCode=1});
