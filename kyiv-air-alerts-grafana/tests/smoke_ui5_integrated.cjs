const fs=require("node:fs");
const puppeteer=require("puppeteer-core");
const url=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url||""))throw Error("Bad preview URL");
(async()=>{
const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage(),errors=[],bad=[];
page.on("pageerror",e=>errors.push(String(e)));page.on("console",m=>{if(m.type()==="error")errors.push(m.text())});page.on("response",r=>{if(r.status()>=400)bad.push(r.status()+" "+r.url().slice(0,180))});
await page.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
await page.waitForFunction(()=>document.querySelector("#citySelect")?.options?.length>=23&&window.Chart?.getChart(document.getElementById("cityIntensityChart")),{timeout:90000});
const initial=await page.evaluate(()=>{
const chart=id=>window.Chart?.getChart(document.getElementById(id));
return {cityCount:document.getElementById("citySelect").options.length,city:document.getElementById("citySelect").value,
years:!!document.querySelector("#extremesYear")&&!!document.querySelector("#burdenYear"),
causeOptions:[...document.querySelector("#kyivCausePeriod").options].map(x=>x.value),
causeLabels:chart("kyivThreatCausesChart")?.data?.labels||[],
daypartMinutes:chart("daypartChart")?.data?.datasets?.flatMap(x=>x.durationMinutes||[]).filter(Number.isFinite).length||0,
trendOff:document.querySelector("#showTrend")?.checked===false};
});
if(initial.city!=="kyiv"||initial.cityCount<23||!initial.years||!initial.trendOff||initial.daypartMinutes===0)errors.push("INITIAL "+JSON.stringify(initial));
if(!["7","14","28","all"].every(x=>initial.causeOptions.includes(x)))errors.push("CAUSE_PERIODS "+JSON.stringify(initial.causeOptions));
if(initial.causeLabels.length<64||initial.causeLabels[0]!=="2026-09-10")errors.push("CAUSE_HISTORY "+JSON.stringify([initial.causeLabels.length,initial.causeLabels[0],initial.causeLabels.at(-1)]));
await page.select("#kyivCausePeriod","7");
const seven=await page.evaluate(()=>window.Chart?.getChart(document.querySelector("#kyivThreatCausesChart"))?.data?.labels?.length);
if(seven!==7)errors.push("CAUSE_7 "+seven);
await page.select("#kyivCausePeriod","all");
const all=await page.evaluate(()=>window.Chart?.getChart(document.querySelector("#kyivThreatCausesChart"))?.data?.labels?.length);
if(all<64)errors.push("CAUSE_ALL "+all);
const years=await page.evaluate(()=>[...document.querySelector("#extremesYear").options].map(x=>x.value));
if(years.includes("2024")){const before=await page.$eval("#burdenYear",x=>x.value);await page.select("#extremesYear","2024");const after=await page.$eval("#burdenYear",x=>x.value);if(before!==after)errors.push("YEAR_LINKED");}
await page.select("#cityPeriod","monthly");
await page.click("#showTrend");
const forecast=await page.evaluate(()=>window.Chart?.getChart(document.querySelector("#cityIntensityChart"))?.data?.labels?.filter(x=>String(x).includes("Прогноз")||String(x).includes("Forecast")).length);
if(forecast!==1)errors.push("TREND_ON "+forecast);
await page.click("#showTrend");
const cleared=await page.evaluate(()=>window.Chart?.getChart(document.querySelector("#cityIntensityChart"))?.data?.labels?.filter(x=>String(x).includes("Прогноз")||String(x).includes("Forecast")).length);
if(cleared!==0)errors.push("TREND_OFF "+cleared);
await page.screenshot({path:"ui5-browser.png"});
const out={url,initial,seven,all,forecast,cleared,errors,bad};fs.writeFileSync("ui5-browser.json",JSON.stringify(out,null,2));console.log("UI5_BROWSER "+JSON.stringify(out));
await browser.close();if(errors.length||bad.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
