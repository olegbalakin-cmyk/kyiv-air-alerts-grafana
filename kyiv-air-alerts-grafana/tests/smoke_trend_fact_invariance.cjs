const fs=require("node:fs");
const assert=require("node:assert/strict");
const puppeteer=require("puppeteer-core");
const url=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url||""))throw Error("Expected immutable nonproduction Netlify draft URL");
(async()=>{
  const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",
    args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
  const page=await browser.newPage();
  const baseline=await browser.newPage();
  const baselineUrl="https://ukraine-air-alerts.netlify.app/";
  const faults=[],report={url,baselineUrl,cases:[],faults};
  page.on("pageerror",e=>faults.push("JS "+String(e)));
  page.on("response",r=>{if(r.status()>=400)faults.push("HTTP "+r.status()+" "+r.url().slice(0,160))});
  async function snapshot(target=page){
    return target.evaluate(()=>{
      const chart=window.Chart?.getChart(document.querySelector("#cityIntensityChart"));
      if(!chart)throw Error("missing chart");
      const main=chart.data.datasets.slice(0,2);
      const values=main.map(d=>d.data.map(x=>Number.isFinite(x)?x:null));
      const points=main.map((d,i)=>chart.getDatasetMeta(i).data.map(e=>{
        if(!e||e.skip)return null;
        const p=e.getProps(["x","y","base","width"],true);
        return {x:p.x,y:p.y,base:p.base,width:p.width};
      }));
      const axis={hours:chart.scales.yHours.max,alerts:chart.scales.yAlerts.max};
      const completion=chart.data.datasets.filter(d=>d._isCompletion).map(d=>({
        type:d.type,values:d.data.filter(Number.isFinite),pointStyle:d.pointStyle
      }));
      const subtitle=document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent;
      return {period:document.querySelector("#cityPeriod").value,city:document.querySelector("#citySelect").value,
        dashboardGeneration:document.querySelector("#updatedAt")?.textContent,
        labels:[...chart.data.labels],values,points,axis,completion,subtitle,
        checked:document.querySelector("#showTrend").checked,
        visible:!document.querySelector("#showTrend").closest("label").classList.contains("hidden")};
    });
  }
  try{
    await page.setViewport({width:375,height:812,deviceScaleFactor:1});
    await baseline.setViewport({width:375,height:812,deviceScaleFactor:1});
    await Promise.all([
      page.goto(url,{waitUntil:"domcontentloaded",timeout:60000}),
      baseline.goto(baselineUrl,{waitUntil:"domcontentloaded",timeout:60000})
    ]);
    await Promise.all([page,baseline].map(target=>target.waitForFunction(()=>
      document.querySelector("#citySelect")?.options?.length>=23 &&
      window.Chart?.getChart(document.querySelector("#cityIntensityChart")),
      {timeout:120000})));
    for(const period of ["quarterly","monthly","calendarWeekly","daily28"]){
      await page.select("#cityPeriod",period);
      await baseline.select("#cityPeriod",period);
      const old=await snapshot(baseline);
      const off=await snapshot();
      assert.equal(off.dashboardGeneration,old.dashboardGeneration,
        period+" live data refreshed midtest; cannot compare different source versions");
      assert.deepEqual(off.labels,old.labels,
        period+" original X-axis labels changed even with trend OFF");
      assert.deepEqual(off.values,old.values,
        period+" original factual metrics changed vs untouched live production");
      assert.equal(off.checked,false,period+" initial checkbox");
      if(!off.visible){report.cases.push({period,eligible:false});continue;}
      assert.equal(off.completion.length,0,period+" off contains zero forecast");
      await page.click("#showTrend");
      const on=await snapshot();
      assert.equal(on.checked,true,period+" on checkbox");
      assert.deepEqual(on.labels,off.labels,period+" chart labels changed");
      assert.deepEqual(on.values,off.values,period+" ACTUAL DATA CHANGED");
      assert.deepEqual(on.axis,off.axis,period+" AXIS CHANGED");
      for(let i=0;i<2;i++)for(let j=0;j<off.points[i].length;j++){
        const a=off.points[i][j],b=on.points[i][j];
        if(a===null||b===null){assert.equal(a,b,period+" missing bar changed");continue;}
        assert(Math.abs(a.y-b.y)<0.15,period+" pixel y position changed");
        assert(Math.abs(a.x-b.x)<0.15,period+" pixel x position changed");
      }
      assert.equal(on.completion.length,2,period+" expected only forecast hour+count markers");
      assert(on.completion.every(c=>c.type==="line"&&c.values.length===1),period+" forecast is not two markers");
      const before=off.values[0].at(-1),after=on.values[0].at(-1);
      report.cases.push({period,eligible:true,
        liveOriginalHours:old.values[0].at(-1),
        testOFFHours:before,testONHours:after,
        liveOriginalAlerts:old.values[1].at(-1),
        testOFFAlerts:off.values[1].at(-1),testONAlerts:on.values[1].at(-1),
        forecast:on.completion,axis:on.axis});
      if(period==="quarterly")await page.screenshot({path:"trend-fact-invariance-mobile.png"});
      await page.click("#showTrend");
      const reset=await snapshot();
      assert.deepEqual(reset.values,off.values,period+" actual changed on toggle OFF");
    }
    assert(report.cases.find(x=>x.period==="quarterly"&&x.eligible),
      "Kyiv Q4 completion must be present in current published sources");
    console.log("TREND_FACT_BROWSER_INVARIANCE_PASS",JSON.stringify(report));
  }catch(e){faults.push(String(e));console.error(e)}
  fs.writeFileSync("trend-fact-invariance-browser.json",JSON.stringify(report,null,2));
  await browser.close();
  if(faults.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
