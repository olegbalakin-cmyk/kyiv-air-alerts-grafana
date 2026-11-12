const fs = require("node:fs");
const puppeteer = require("puppeteer-core");
const url = process.env.PREVIEW_URL;
if (!url || !/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url)) throw new Error("Expected Netlify draft permalink");
(async () => {
  const browser = await puppeteer.launch({
    headless: true, executablePath: process.env.CHROME_BIN || "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
  });
  const errors = [], failed = [], network = [];
  const page = await browser.newPage();
  page.on("pageerror", err => errors.push(String(err)));
  page.on("console", msg => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("requestfailed", req => failed.push({url:req.url().slice(0,250), error:req.failure()?.errorText}));
  page.on("response", res => { if (res.status() >= 400) network.push({url:res.url().slice(0,250),status:res.status()}); });
  let navigationError = null;
  try { await page.goto(url, {waitUntil:"domcontentloaded",timeout:60000}); }
  catch (err) { navigationError=String(err); }
  try {
    await page.waitForFunction(() => {
      const select = document.getElementById("citySelect");
      return select && select.options.length >= 23 && window.Chart &&
        window.Chart.getChart(document.getElementById("cityIntensityChart"));
    }, {timeout:100000});
  } catch (err) { errors.push("SMOKE_READY_TIMEOUT: " + String(err)); }
  const snapshot = await page.evaluate(() => {
    const select = document.getElementById("citySelect");
    const chartCanvas=document.getElementById("cityIntensityChart");
    const chart=window.Chart && window.Chart.getChart(chartCanvas);
    return {
      title:document.title,
      cityOptions:select?.options?.length ?? -1,
      cityTitle:document.getElementById("cityTitle")?.textContent,
      generated:document.getElementById("updatedAt")?.textContent,
      banner:document.getElementById("freshnessBanner")?.textContent,
      bannerVisible:!document.getElementById("freshnessBanner")?.classList.contains("hidden"),
      chartHasInstance:!!chart,
      chartLabels:chart?.data?.labels?.length,
      forecastLabels:chart?.data?.labels?.filter(x=>String(x).includes("Прогноз")||String(x).includes("Forecast")).length,
      numericData:chart?.data?.datasets?.flatMap(ds=>ds.data||[]).filter(x=>typeof x==="number" && Number.isFinite(x)).length,
      appLoaded:typeof window.ForecastTrend!=="undefined",
      hasKpiRange:typeof window.KpiRange!=="undefined"
    };
  });
  const countForecast = async () => page.evaluate(() => {
    const chart=window.Chart?.getChart(document.getElementById("cityIntensityChart"));
    const labels=chart?.data?.labels||[];
    const indices=labels.map((x,i)=>String(x).includes("Прогноз")||String(x).includes("Forecast")?i:-1).filter(i=>i>=0);
    const counts=chart?.data?.datasets?.filter(d=>String(d.label).includes("EWMA"))||[];
    return {
      forecastCount:indices.length,
      forecastLabels:indices.map(i=>labels[i]),
      forecastDatasets:counts.length,
      forecastDataPoints:counts.map(d=>indices.filter(i=>Number.isFinite(d.data[i])).length),
      checked:document.getElementById("showTrend")?.checked,
      controlVisible:document.getElementById("showTrend")?.closest("label")?.getClientRects().length>0
    };
  });
  snapshot.toolbar = await page.evaluate(() => {
    const card=document.getElementById("cityIntensityChart")?.closest(".chart-card");
    const row=card?.querySelector('[data-csv-chart="cityIntensityChart"]');
    const checkbox=row?.querySelector("#showTrend");
    const csv=row?.querySelector(".csv-export-button:not(.chart-image-button):not(.chart-embed-button)");
    const share=row?.querySelector('[data-share-image="cityIntensityChart"]');
    const embed=row?.querySelector('[data-embed-chart="cityIntensityChart"]');
    const rect=node=>{const r=node?.getBoundingClientRect();return r?{left:r.left,right:r.right,top:r.top,bottom:r.bottom}:null};
    return {singleToolbar:card?.querySelectorAll('[data-csv-chart="cityIntensityChart"]').length,
      checkbox:!!checkbox,csv:!!csv,share:!!share,embed:!!embed,
      order:[checkbox,csv,share,embed].map(n=>n?.getBoundingClientRect().left),
      checkboxRect:rect(checkbox?.closest("label")),csvRect:rect(csv),shareRect:rect(share)};
  });
  if(snapshot.toolbar.singleToolbar!==1||!snapshot.toolbar.checkbox||!snapshot.toolbar.csv||
     !snapshot.toolbar.share||!snapshot.toolbar.embed) errors.push("CHART_TOOLBAR_INCOMPLETE:"+JSON.stringify(snapshot.toolbar));
  // The trend checkbox belongs in the same compact right-aligned group as CSV/Share.
  if(!snapshot.toolbar.checkboxRect||!snapshot.toolbar.csvRect||
     Math.abs(snapshot.toolbar.checkboxRect.top-snapshot.toolbar.csvRect.top)>5||
     snapshot.toolbar.csvRect.left-snapshot.toolbar.checkboxRect.right<0||
     snapshot.toolbar.csvRect.left-snapshot.toolbar.checkboxRect.right>20)
    errors.push("TREND_NOT_ADJACENT_TO_CSV:"+JSON.stringify(snapshot.toolbar));
  snapshot.initialTrend = await countForecast();
  if (snapshot.initialTrend.checked !== false || snapshot.initialTrend.forecastCount !== 0 ||
      snapshot.initialTrend.forecastDatasets !== 0) errors.push("DEFAULT_TREND_NOT_OFF:"+JSON.stringify(snapshot.initialTrend));

  // Supported scales: off by default, on -> one period, off -> no forecast.
  snapshot.forecastsByPeriod = {};
  for (const period of ["daily28","calendarWeekly","monthly","allTime"]) {
    await page.select("#cityPeriod",period);
    const initial=await countForecast();
    if(initial.forecastCount!==0||initial.checked!==false||!initial.controlVisible)
      errors.push("TREND_SHOULD_BE_HIDDEN_IN_CHART:"+period+":"+JSON.stringify(initial));
    await page.click("#showTrend");
    const on=await countForecast();
    if(on.forecastCount!==1||on.forecastDatasets!==2||on.forecastDataPoints.some(n=>n!==1)||!on.checked)
      errors.push("TREND_OPT_IN_FAILED:"+period+":"+JSON.stringify(on));
    await page.click("#showTrend");
    const off=await countForecast();
    if(off.forecastCount!==0||off.forecastDatasets!==0||off.checked)
      errors.push("TREND_OPT_OUT_FAILED:"+period+":"+JSON.stringify(off));
    snapshot.forecastsByPeriod[period]={initial,on,off};
  }
  // Preserve the user's opt-in across supported interval and city changes.
  await page.click("#showTrend");
  await page.select("#cityPeriod","monthly");
  const retained=await countForecast();
  if(!retained.checked||retained.forecastCount!==1)errors.push("TREND_NOT_PRESERVED_BETWEEN_SCALES:"+JSON.stringify(retained));
  const cityChoices=await page.$$eval("#citySelect option", options=>options.map(x=>x.value).filter(Boolean));
  if(cityChoices.length>1) {
    await page.select("#citySelect",cityChoices[1]);
    const cityResult=await countForecast();
    if(!cityResult.checked||cityResult.forecastCount!==1)errors.push("TREND_NOT_PRESERVED_BETWEEN_CITIES:"+JSON.stringify(cityResult));
  }
  // Unsupported rolling scales retain opt-in but never add forecast points.
  snapshot.rolling = {};
  for (const period of ["weekly","rolling30","rolling90","rolling180"]) {
    await page.select("#cityPeriod",period);
    const rolling=await countForecast();
    snapshot.rolling[period]=rolling;
    if(rolling.forecastCount!==0||rolling.forecastDatasets!==0||rolling.controlVisible)
      errors.push("TREND_ON_ROLLING:"+period+":"+JSON.stringify(rolling));
  }
  await page.select("#cityPeriod","daily28");
  const restored=await countForecast();
  if(!restored.checked||restored.forecastCount!==1)errors.push("TREND_NOT_RESTORED:"+JSON.stringify(restored));
  await page.click("#showTrend");
  snapshot.finalTrend=await countForecast();
  snapshot.daily28ForecastLabels=snapshot.finalTrend.forecastCount;
  if(snapshot.finalTrend.checked||snapshot.finalTrend.forecastCount!==0)errors.push("FINAL_TREND_NOT_OFF:"+JSON.stringify(snapshot.finalTrend));
  // Small-screen check: the same row must contain all chart actions without horizontal overflow.
  await page.setViewport({width:375,height:812,deviceScaleFactor:1});
  await page.reload({waitUntil:"domcontentloaded",timeout:60000});
  await page.waitForFunction(() => {
    const row=document.querySelector('[data-csv-chart="cityIntensityChart"]');
    return row?.querySelectorAll("button").length===3 && window.Chart?.getChart(document.getElementById("cityIntensityChart"));
  },{timeout:60000});
  snapshot.mobileToolbar = await page.evaluate(() => {
    const row=document.querySelector('[data-csv-chart="cityIntensityChart"]');
    const card=document.getElementById("cityIntensityChart")?.closest(".chart-card");
    const r=row?.getBoundingClientRect(),c=card?.getBoundingClientRect();
    return {viewport:innerWidth,rowLeft:r?.left,rowRight:r?.right,cardLeft:c?.left,cardRight:c?.right,
      hasCheckbox:!!row?.querySelector("#showTrend"),
      buttonCount:row?.querySelectorAll("button").length,
      controls:[...row?.children||[]].map(node=>{const x=node.getBoundingClientRect();return {tag:node.tagName,left:x.left,right:x.right,top:x.top,bottom:x.bottom}}),
      bodyWidth:document.documentElement.scrollWidth};
  });
  if(!snapshot.mobileToolbar.hasCheckbox||snapshot.mobileToolbar.buttonCount!==3||
     snapshot.mobileToolbar.rowLeft<0||snapshot.mobileToolbar.rowRight>375||
     snapshot.mobileToolbar.controls.some(x=>x.left<0||x.right>375))
    errors.push("MOBILE_TOOLBAR_INVALID:"+JSON.stringify(snapshot.mobileToolbar));
  try { await page.screenshot({path:"forecast-browser.png",fullPage:true}); } catch {}
  const output = {url,navigationError,errors,failed,network,snapshot};
  fs.writeFileSync("forecast-browser.json",JSON.stringify(output,null,2));
  console.log("FORECAST_BROWSER",JSON.stringify(output));
  await browser.close();
  if (snapshot.cityOptions < 23 || !snapshot.chartHasInstance ||
      !snapshot.numericData || !snapshot.generated || snapshot.daily28ForecastLabels !== 0 || errors.length || failed.length || network.length) process.exitCode=1;
})().catch(err=>{console.error("SMOKE_EXCEPTION",err);process.exitCode=1;});
