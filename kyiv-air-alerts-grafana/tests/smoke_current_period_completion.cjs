const fs=require("node:fs"),puppeteer=require("puppeteer-core");
const url=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url||""))throw Error("unsafe preview origin");
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",
   args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
 const page=await browser.newPage(),errors=[],http=[];
 page.on("pageerror",e=>errors.push("JS "+String(e)));
 page.on("console",m=>{if(m.type()==="error")errors.push("CONSOLE "+m.text())});
 page.on("response",r=>{if(r.status()>=400)http.push(r.status()+" "+r.url())});
 await page.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
 await page.waitForFunction(()=>document.querySelector("#citySelect")?.options?.length===23 &&
   window.Chart?.getChart(document.querySelector("#cityIntensityChart")),{timeout:110000});
 const modes=["calendarWeekly","monthly","quarterly"],out=[];
 for(const mode of modes){
   await page.select("#cityPeriod",mode);
   const initial=await page.evaluate(()=>{
     const c=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
     return {trendOff:!document.querySelector("#showTrend").checked,
       completion:c.data.datasets.filter(d=>d._isCompletion).length,
       legend:c.legend.legendItems.map(i=>i.text)};
   });
   if(initial.completion!==0||!initial.trendOff)errors.push("OFF_"+mode+" "+JSON.stringify(initial));
   const visible=await page.evaluate(()=>!document.querySelector("#showTrend").closest("label").classList.contains("hidden"));
   if(!visible){out.push({mode,eligible:false});continue}
   await page.click("#showTrend");
   const measured=await page.evaluate(()=>{
     const c=window.Chart.getChart(document.querySelector("#cityIntensityChart")),last=c.data.labels.length-1,
       actual=c.data.datasets[0].data[last],remaining=c.data.datasets.find(d=>d._isCompletion&&d.type==="bar")?.data[last],
       green=c.data.datasets.find(d=>d._isCompletion&&d.type==="line")?.data[last],
       subtitle=document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent;
     return {labels:c.data.labels.slice(-2),actual,remaining,green,stacked:c.options.scales.yHours.stacked,
       completion:c.data.datasets.filter(d=>d._isCompletion).length,
       nextForecast:c.data.datasets.filter(d=>d._isForecast).length,
       legend:c.legend.legendItems.map(x=>x.text),
       subtitle,chartRows:c.data.labels.length};
   });
   if(measured.completion!==2||measured.nextForecast||!measured.stacked||
     !Number.isFinite(measured.actual)||!Number.isFinite(measured.remaining)||!Number.isFinite(measured.green)||
     measured.remaining<0||measured.green<0||!measured.subtitle.includes("Штрихована частина")||
     measured.legend.some(x=>/Оцінка|Estimated|Прогноз|Forecast/.test(x)))
       errors.push("ON_"+mode+" "+JSON.stringify(measured));
   out.push({mode,eligible:true,...measured});
   await page.click("#showTrend");
 }
 const unsupported=[];
 for(const mode of ["daily28","weekly","rolling30","rolling90","rolling180","allTime"]){
   await page.select("#cityPeriod",mode);
   const current=await page.evaluate(()=>{
     const control=document.querySelector("#showTrend");
     const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
     return {hidden:control.closest("label").classList.contains("hidden"),
       completion:chart.data.datasets.filter(x=>x._isCompletion).length,
       futures:chart.data.datasets.filter(x=>x._isForecast).length,
       forecastLabels:chart.data.labels.filter(x=>String(x).includes("Прогноз:")).length};
   });
   if(!current.hidden||current.completion!==0||current.futures!==0||current.forecastLabels!==0)
     errors.push("UNIFIED_TREND_"+mode+" "+JSON.stringify(current));
   unsupported.push({mode,...current});
 }
 await page.setViewport({width:375,height:812});
 await page.select("#cityPeriod","quarterly");
 const mobile=await page.evaluate(()=>{
   const c=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
   return {width:window.innerWidth,labels:c.data.labels.slice(-3),
     noCompletion:c.data.datasets.every(d=>!d._isCompletion),
     quarterOption:[...document.querySelector("#cityPeriod").options].some(x=>x.value==="quarterly")};
 });
 if(mobile.width!==375||!mobile.noCompletion||!mobile.quarterOption)errors.push("MOBILE "+JSON.stringify(mobile));
 await page.screenshot({path:"period-completion-mobile.png",fullPage:false});
 await page.setViewport({width:1280,height:850});
 const report={url,cityCount:23,modes:out,unsupported,mobile,errors,http};
 fs.writeFileSync("period-completion-browser.json",JSON.stringify(report,null,2));
 console.log("PERIOD_COMPLETION_BROWSER "+JSON.stringify(report));
 await browser.close();
 if(!out.some(x=>x.eligible)||errors.length||http.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
