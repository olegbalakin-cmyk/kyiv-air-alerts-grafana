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
  // Three supported calendar scales must show exactly one forecast.
  snapshot.forecastsByPeriod = {};
  for (const period of ["daily28", "calendarWeekly", "monthly", "allTime"]) {
    await page.select("#cityPeriod", period);
    await page.waitForFunction(p => {
      const chart=window.Chart?.getChart(document.getElementById("cityIntensityChart"));
      return chart && document.getElementById("cityPeriod").value === p;
    }, {timeout:25000}, period);
    const result = await page.evaluate(() => {
      const chart=window.Chart?.getChart(document.getElementById("cityIntensityChart"));
      const labels=chart?.data?.labels||[];
      const indices=labels.map((x,i)=>String(x).includes("Прогноз")||String(x).includes("Forecast")?i:-1).filter(i=>i>=0);
      const counts=chart?.data?.datasets?.filter(d=>String(d.label).includes("EWMA"))||[];
      return {forecastCount:indices.length, forecastLabels:indices.map(i=>labels[i]), forecastDatasets:counts.length, forecastDataPoints:counts.map(d=>indices.filter(i=>Number.isFinite(d.data[i])).length)};
    });
    snapshot.forecastsByPeriod[period] = result;
    if (result.forecastCount !== 1 || result.forecastDatasets !== 2 || result.forecastDataPoints.some(n=>n!==1)) errors.push("INVALID_ONE_PERIOD_FORECAST:"+period+":"+JSON.stringify(result));
  }
  for (const period of ["weekly", "rolling30", "rolling90", "rolling180"]) {
    await page.select("#cityPeriod",period);
    const count=await page.evaluate(() => {
      const chart=window.Chart?.getChart(document.getElementById("cityIntensityChart"));
      return chart?.data?.labels?.filter(x=>String(x).includes("Прогноз")||String(x).includes("Forecast")).length||0;
    });
    if(count!==0)errors.push("FORECAST_ON_ROLLING:"+period+":"+count);
  }
  await page.select("#cityPeriod", "daily28");
  snapshot.daily28ForecastLabels = snapshot.forecastsByPeriod.daily28.forecastCount;
  try { await page.screenshot({path:"forecast-browser.png",fullPage:true}); } catch {}
  const output = {url,navigationError,errors,failed,network,snapshot};
  fs.writeFileSync("forecast-browser.json",JSON.stringify(output,null,2));
  console.log("FORECAST_BROWSER",JSON.stringify(output));
  await browser.close();
  if (snapshot.cityOptions < 23 || !snapshot.chartHasInstance ||
      !snapshot.numericData || !snapshot.generated || snapshot.daily28ForecastLabels !== 1 || errors.length) process.exitCode=1;
})().catch(err=>{console.error("SMOKE_EXCEPTION",err);process.exitCode=1;});
