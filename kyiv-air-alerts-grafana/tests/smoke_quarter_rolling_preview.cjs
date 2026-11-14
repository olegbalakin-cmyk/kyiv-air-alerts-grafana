const fs=require("node:fs"),puppeteer=require("puppeteer-core");
const url=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url||""))throw Error("Expected isolated Netlify preview URL");
(async()=>{
const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",
args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage();const errors=[],http=[];
page.on("pageerror",e=>errors.push(String(e)));page.on("console",m=>{if(m.type()==="error")errors.push(m.text())});
page.on("response",r=>{if(r.status()>=400)http.push(r.status()+" "+r.url())});
await page.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
await page.waitForFunction(()=>document.querySelector("#citySelect")?.options?.length>=23 &&
  window.Chart?.getChart(document.querySelector("#cityIntensityChart")),{timeout:110000});
const baseline=await page.evaluate(()=>({cities:document.querySelector("#citySelect").options.length,
menus:["cityPeriod","comparePeriod"].map(id=>[...document.querySelector("#"+id).options].some(o=>o.value==="quarterly")),
allQuarter:[...document.querySelector("#allCitiesRange").options].some(o=>o.value==="quarter"),
model:typeof window.QuarterRollingPreview?.rollingForecast,
trendOff:!document.querySelector("#showTrend")?.checked}));
if(!baseline.menus.every(Boolean)||!baseline.allQuarter||!baseline.trendOff||baseline.model!=="function")errors.push("BASELINE "+JSON.stringify(baseline));

await page.select("#cityPeriod","monthly");
const monthOff=await page.evaluate(()=>{
 const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
 return {legend:chart.legend.legendItems.map(x=>x.text),
   forecast:chart.data.datasets.filter(d=>d._isForecast).length,
   subtitle:document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent};
});
if(monthOff.forecast||monthOff.legend.some(x=>/Прогноз|Forecast/.test(x))||monthOff.subtitle.includes("EWMA 0,3:"))
 errors.push("MONTH_OFF "+JSON.stringify(monthOff));
await page.click("#showTrend");
const monthOn=await page.evaluate(()=>{
 const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
 const fn=chart.options.plugins.tooltip.filter;
 const labelsAt=index=>chart.data.datasets.filter((dataset,datasetIndex)=>fn({dataset,datasetIndex,
    dataIndex:index,parsed:{y:dataset.data[index]}},chart.data)).map(d=>d.label);
 return {legend:chart.legend.legendItems.map(x=>x.text),
   forecast:chart.data.datasets.filter(d=>d._isForecast).length,
   actualTip:labelsAt(chart.data.labels.length-2),
   forecastTip:labelsAt(chart.data.labels.length-1),
   subtitle:document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent};
});
if(monthOn.forecast!==2||monthOn.legend.some(x=>/Прогноз|Forecast/.test(x))||
 monthOn.actualTip.length!==2||monthOn.actualTip.some(x=>/Прогноз|Forecast/.test(x))||
 monthOn.forecastTip.length!==2||monthOn.forecastTip.some(x=>!/Прогноз|Forecast/.test(x))||
 !monthOn.subtitle.includes("EWMA 0,3: останнє спостереження має вагу 30%"))
 errors.push("MONTH_LEGEND_TOOLTIP_EWMA "+JSON.stringify(monthOn));
await page.click("#showTrend");
await page.select("#cityPeriod","quarterly");
const city=await page.evaluate(()=>({labels:window.Chart.getChart(document.querySelector("#cityIntensityChart"))?.data.labels||[],
  forecastVisible:!document.querySelector("#showTrend")?.closest("label")?.classList.contains("hidden")}));
if(!city.labels.some(x=>String(x).includes("Q")))errors.push("CITY_QUARTER "+JSON.stringify(city));
await page.select("#comparePeriod","quarterly");
const comparison=await page.evaluate(()=>window.Chart.getChart(document.querySelector("#compareAlertsChart"))?.data.labels||[]);
if(!comparison.some(x=>String(x).includes("Q")))errors.push("COMPARE_QUARTER "+JSON.stringify(comparison));
await page.select("#allCitiesRange","quarter");
const all=await page.evaluate(()=>({rows:document.querySelectorAll("#allCitiesTable tr").length,
 note:document.querySelector("#allCitiesRangeNote").textContent,
 range:document.querySelector("#allCitiesRange").value}));
if(all.rows!==23||!all.note.includes("2026")||all.range!=="quarter")errors.push("TABLE_QUARTER "+JSON.stringify(all));
const rolling=[];
for(const mode of ["rolling30","rolling90","rolling180"]){
  await page.select("#cityPeriod",mode);
  const before=await page.evaluate(()=>({control:!document.querySelector("#showTrend").closest("label").classList.contains("hidden"),
    n:window.Chart.getChart(document.querySelector("#cityIntensityChart"))?.data.labels.length}));
  if(before.control){
    await page.click("#showTrend");
    const after=await page.evaluate(()=>{
      const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
      const fn=chart.options.plugins.tooltip.filter;
      const labelsAt=index=>chart.data.datasets.filter((dataset,datasetIndex)=>fn({dataset,datasetIndex,
        dataIndex:index,parsed:{y:dataset.data[index]}},chart.data)).map(d=>d.label);
      return {labels:chart.data.labels,forecast:chart.data.datasets.filter(d=>d._isForecast).length,
        legend:chart.legend.legendItems.map(x=>x.text),
        actualTip:labelsAt(chart.data.labels.length-2),
        forecastTip:labelsAt(chart.data.labels.length-1),
        subtitle:document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent};
    });
    if(after.labels.length!==before.n+1||after.forecast!==2||
      after.legend.some(x=>/Прогноз|Forecast/.test(x))||
      after.actualTip.length!==2||after.actualTip.some(x=>/Прогноз|Forecast/.test(x))||
      after.forecastTip.length!==2||after.forecastTip.some(x=>!/Прогноз|Forecast/.test(x))||
      !after.subtitle.includes("EWMA 0,3:"))
      errors.push("ROLL_FORECAST_TOOLTIP_"+mode+" "+JSON.stringify(after));
    await page.click("#showTrend");
  }
  rolling.push({mode,...before});
}
await page.setViewport({width:375,height:812});
await page.select("#cityPeriod","monthly");
await page.click("#showTrend");
const mobile=await page.evaluate(()=>{
 const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
 const p=document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle");
 return {width:window.innerWidth,legend:chart.legend.legendItems.map(x=>x.text),
   ewma:p.textContent.includes("EWMA 0,3: останнє спостереження має вагу 30%"),
   wraps:getComputedStyle(p).whiteSpace!=="nowrap"};
});
if(mobile.width!==375||!mobile.ewma||!mobile.wraps||
  mobile.legend.some(x=>/Прогноз|Forecast/.test(x)))
 errors.push("MOBILE_EWMA_LEGEND "+JSON.stringify(mobile));
await page.screenshot({path:"quarter-rolling-browser.png"});
const report={url,baseline,monthOff,monthOn,city,comparison,all,rolling,mobile,errors,http};
fs.writeFileSync("quarter-rolling-browser.json",JSON.stringify(report,null,2));
console.log("QUARTER_ROLLING_BROWSER "+JSON.stringify(report));
await browser.close();
if(errors.length||http.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
