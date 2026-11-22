/* PR226 Chromium browser test of unpublished Netlify draft. */
"use strict";
const fs=require("node:fs"),assert=require("node:assert/strict");
const {chromium}=require("playwright");
const url=process.env.WEEKDAY_PREVIEW_URL;
const proof="_preview-proof";
const report={url,cities:[],cases:[],errors:[],status:"FAIL"};
async function ready(p){
  await p.waitForFunction(()=>!!(window.Chart&&window.WeekdayUI&&Chart.getChart(document.querySelector("#weekdayHoursChart"))?.data?.datasets?.length&&document.querySelector("#weekdayMeta")?.textContent?.includes(" · ")),null,{timeout:40000});
}
async function split(p,n){
  await p.waitForFunction(expected=>{
    const s=document.querySelector("#weekdaySplitStatus")?.textContent||"";
    const d=window.Chart?.getChart(document.querySelector("#weekdayHoursChart"))?.data?.datasets||[];
    return /Точний розподіл|Exact Europe/.test(s)&&d.length===expected;
  },n,{timeout:12000});
  const key=await p.locator("#weekdayShareLegend .weekday-share-item").allTextContents();
  assert.equal(key.length,n,"Color key matches the time bands");
  for(const entry of key)assert.doesNotMatch(entry,/\d+[,.]\d\s*(год|h)\s*·|%/);
  const tooltip=await p.evaluate(()=>{
    const chart=Chart.getChart(document.querySelector("#weekdayHoursChart"));
    const callbacks=chart.options.plugins.tooltip.callbacks;
    const all=chart.data.datasets.map(d=>d.data);
    const first=chart.data.labels.findIndex((_,i)=>all.some(part=>(part[i]||0)>0));
    const i=first<0?0:first;
    const values=all.map(part=>Number(part[i]||0));
    const lines=chart.data.datasets.map((dataset,datasetIndex)=>
      String(callbacks.label({dataset,datasetIndex,dataIndex:i,parsed:{y:values[datasetIndex]}})));
    const footer=callbacks.footer([{dataIndex:i}]);
    return {values,lines,footer};
  });
  const total=tooltip.values.reduce((a,b)=>a+b,0);
  assert.equal(tooltip.lines.length,n);
  for(let i=0;i<n;i++){
    assert.match(tooltip.lines[i],/(год\/день|hr\/day)\s*·\s*\d+[,.]\d%$/);
    const m=tooltip.lines[i].match(/·\s*(\d+[,.]\d)%$/);
    assert.ok(m,"Percent is shown for the clicked weekday bar");
    const shown=Number(m[1].replace(",","."));
    const expected=total>0?100*tooltip.values[i]/total:0;
    assert.ok(Math.abs(shown-expected)<=0.11,"Time-band percentage refers to this weekday bar");
  }
  assert.ok(tooltip.footer.some(t=>String(t).includes(total>0?"100%":"0%")));
  report.cases.push({city:await p.locator("#citySelect").inputValue(),
    range:await p.locator("#weekdayRange").inputValue(),
    bands:n,status:"PASS",colorKey:key,tooltip:tooltip.lines});
}
async function page(browser,path,width,height){
  const p=await browser.newPage({viewport:{width,height}});
  p.on("pageerror",err=>report.errors.push(String(err)));
  const res=await p.goto(new URL(path,url).toString(),{waitUntil:"domcontentloaded",timeout:60000});
  assert.equal(res.status(),200);
  await ready(p);return p;
}
(async()=>{
  assert.match(url||"",/^https:\/\/weekday-pr226-20261122--ukraine-air-alerts\.netlify\.app\/?$/);
  fs.mkdirSync(proof,{recursive:true});
  const b=await chromium.launch();
  try{
    const p=await page(b,"",1440,900);
    const cities=await p.locator("#citySelect option").evaluateAll(o=>o.map(x=>x.value).filter(Boolean));
    assert.equal(cities.length,23);
    await p.selectOption("#weekdayRange","28d");
    await p.locator("#weekdaySplitEnabled").check();
    await split(p,4);
    await p.selectOption("#weekdaySplitMode","daynight");await split(p,2);
    await p.screenshot({path:proof+"/ua-desktop.png",fullPage:true});
    for(const city of cities){
      await p.selectOption("#citySelect",city);
      await p.selectOption("#weekdayRange","28d");
      await p.selectOption("#weekdaySplitMode","four");await split(p,4);
      await p.selectOption("#weekdaySplitMode","daynight");await split(p,2);
      report.cities.push(city);
    }
    await p.selectOption("#citySelect","kyiv");
    for(const range of ["90d","180d","year","all"]){
      await p.selectOption("#weekdayRange",range);
      await p.selectOption("#weekdaySplitMode","four");await split(p,4);
    }
    await p.selectOption("#weekdayRange","28d");
    const end=await p.locator("#weekdayDateTo").inputValue();
    await p.selectOption("#weekdayRange","custom");
    await p.locator("#weekdayDateFrom").fill(end);
    await p.locator("#weekdayDateFrom").dispatchEvent("change");
    await split(p,4);
    assert.ok((await p.locator("#weekdayMeta").innerText()).startsWith(end+" — "+end));
    await p.locator("#weekdaySplitEnabled").uncheck();
    assert.equal(await p.evaluate(()=>Chart.getChart(document.querySelector("#weekdayHoursChart")).data.datasets.length),1);
    assert.equal(await p.locator("#weekdayShareLegend .weekday-share-item").count(),0);
    const en=await page(b,"en/",1440,900);
    await en.selectOption("#weekdayRange","28d");
    await en.locator("#weekdaySplitEnabled").check();await split(en,4);
    await en.selectOption("#weekdaySplitMode","daynight");await split(en,2);
    await en.screenshot({path:proof+"/en-desktop.png",fullPage:true});
    const mobile=await page(b,"",390,844);
    await mobile.selectOption("#weekdayRange","28d");
    await mobile.locator("#weekdaySplitEnabled").check();await split(mobile,4);
    await mobile.selectOption("#weekdaySplitMode","daynight");await split(mobile,2);
    const overflow=await mobile.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
    assert.ok(overflow<=8,"Mobile horizontal overflow="+overflow);
    await mobile.screenshot({path:proof+"/ua-mobile.png",fullPage:true});
    assert.deepEqual(report.errors,[]);
    report.status="PASS";
    console.log("PR226_BROWSER_PASS",JSON.stringify({cities:report.cities.length,cases:report.cases.length,overflow,url}));
  }catch(e){report.errors.push(String(e.stack||e));console.error("PR226_BROWSER_FAIL",e);throw e}
  finally{fs.writeFileSync(proof+"/browser-report.json",JSON.stringify(report,null,2)+"\n");await b.close()}
})().catch(()=>process.exitCode=1);
