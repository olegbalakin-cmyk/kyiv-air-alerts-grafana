const fs=require("node:fs");
const assert=require("node:assert/strict");
const puppeteer=require("puppeteer-core");
const url=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+\.netlify\.app\/?$/.test(url||""))throw Error("Must be immutable nonproduction Netlify draft");
const baselineUrl="https://6afa019d1d413ed7e10c27b1--ukraine-air-alerts.netlify.app/";
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",
   protocolTimeout:45000,args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
 const report={url,baselineUrl,cases:[],faults:[]},modes=["quarterly","monthly","calendarWeekly","daily28"];
 const page=await browser.newPage();
 page.on("pageerror",e=>report.faults.push("JS: "+String(e)));
 await page.setViewport({width:375,height:812,deviceScaleFactor:1});
 async function goto(target){
   await page.goto(target,{waitUntil:"domcontentloaded",timeout:60000});
   // Check the real main page, not only the occasionally stalled Puppeteer
   // waitForFunction isolated world. Fail-closed on missing data or canvas.
   for(let n=0;n<15;n++){
     const x=await page.evaluate(()=>({
       count:document.querySelector("#citySelect")?.options?.length||0,
       chart:!!window.Chart?.getChart(document.querySelector("#cityIntensityChart")),
       generation:document.querySelector("#updatedAt")?.textContent||""
     }));
     if(x.count===23&&x.chart&&x.generation)return x;
     await new Promise(r=>setTimeout(r,500));
   }
   throw new Error("23-city chart readiness unavailable at "+target);
 }
 async function setPeriod(mode){
   await page.select("#cityPeriod",mode);
 }
 async function snapshot(){
   return page.evaluate(()=>{
     const c=window.Chart?.getChart(document.querySelector("#cityIntensityChart"));
     if(!c)throw Error("no physical Chart.js chart");
     const main=c.data.datasets.slice(0,2);
     const values=main.map(d=>d.data.map(x=>Number.isFinite(x)?x:null));
     const canvas=main.map((d,i)=>c.getDatasetMeta(i).data.map(e=>{
       if(!e||e.skip)return null;
       const p=e.getProps(["x","y","base","width"],true);
       return {x:p.x,y:p.y,base:p.base,width:p.width};
     }));
     const forecast=c.data.datasets.filter(d=>d._isCompletion).map(d=>({
       type:d.type,points:d.data.filter(Number.isFinite),pointStyle:d.pointStyle
     }));
     return {period:document.querySelector("#cityPeriod").value,city:document.querySelector("#citySelect").value,
       generation:document.querySelector("#updatedAt")?.textContent,
       labels:[...c.data.labels],values,canvas,
       axis:{hours:c.scales.yHours.max,alerts:c.scales.yAlerts.max},
       options:c.config.options?.plugins?.periodForecastDeltaHatch||null,
       registeredPlugin:Array.isArray(c.config.plugins)&&c.config.plugins.some(p=>p.id==="periodForecastDeltaHatch"),
       forecast,
       checked:document.querySelector("#showTrend").checked,
       enabled:!document.querySelector("#showTrend").disabled,
       reason:document.querySelector("#showTrend").title||"",
       visible:!document.querySelector("#showTrend").closest("label").classList.contains("hidden"),
       helpVisible:document.querySelector("#trendHelp") ? !document.querySelector("#trendHelp").hidden : false,
       helpText:document.querySelector("#trendHelpTooltip")?.textContent||"",
       subtitle:document.querySelector("#cityIntensityChart").closest(".chart-card").querySelector(".chart-subtitle").textContent};
   });
 }
 try{
   // Load & release the baseline BEFORE loading the draft. Never keep both
   // heavy dashboard Chart.js documents alive in one browser.
   await goto(baselineUrl);
   const original={};
   for(const mode of modes){await setPeriod(mode);original[mode]=await snapshot();}
   await page.goto("about:blank",{waitUntil:"domcontentloaded"});
   await goto(url);
   for(const mode of modes){
     await setPeriod(mode);
     const off=await snapshot(),old=original[mode];
     assert.equal(off.generation,old.generation,mode+" source generation parity");
     assert.deepEqual(off.labels,old.labels,mode+" source labels changed");
     assert.deepEqual(off.values,old.values,mode+" FACT CHANGED VS ORIGINAL PRODUCTION");
     assert.equal(off.checked,false,mode+" OFF expected");
     assert.equal(off.visible,true,mode+" trend checkbox unexpectedly HIDDEN");
     if(!off.enabled){
       assert(off.reason.length>=12,mode+" disabled trend must explain source condition");
       assert.equal(off.helpVisible,true,mode+" disabled trend info icon must be visible");
       assert.equal(off.helpText,off.reason,mode+" hover text must match disabled reason");
       assert(!off.subtitle.includes(off.reason),mode+" reason must not clutter chart description");
       await page.click("#trendHelp");
       const helpState=await page.evaluate(()=>({
         expanded:document.querySelector("#trendHelp").getAttribute("aria-expanded"),
         visible:getComputedStyle(document.querySelector("#trendHelpTooltip")).display!=="none"
       }));
       assert.equal(helpState.expanded,"true",mode+" touch help expands");
       assert.equal(helpState.visible,true,mode+" tooltip must be visibly rendered");
       await page.click("#trendHelp");
       report.cases.push({mode,eligible:false,reason:off.reason,actual:off.values.map(v=>v.at(-1))});
       continue;
     }
     assert.equal(off.helpVisible,false,mode+" enabled trend should hide info icon");
     await page.$eval("#showTrend",el=>{
       el.checked=!el.checked;
       el.dispatchEvent(new Event("change",{bubbles:true}));
     });
     const on=await snapshot();
     if(!on.checked){
       const debug=await page.evaluate(()=>({
         checkbox:{checked:document.querySelector("#showTrend")?.checked,
           disabled:document.querySelector("#showTrend")?.disabled,
           title:document.querySelector("#showTrend")?.title,
           html:document.querySelector("#showTrend")?.closest("label")?.outerHTML},
         selector:document.querySelector("#cityPeriod")?.value,
         updatedAt:document.querySelector("#updatedAt")?.textContent,
         selectedCity:document.querySelector("#citySelect")?.value,
         now:new Date().toISOString(),
         historicalEnd:window.state?.historicalDaily?.cities?.[document.querySelector("#citySelect")?.value]?.end,
         partialDate:window.state?.data?.cities?.[document.querySelector("#citySelect")?.value]?.daily28?.at(-1)?.date
       }));
       console.error("TREND_CONTROL_DEBUG",JSON.stringify({mode,off,on,debug}));
     }
     assert.equal(on.checked,true,mode+" ON expected");
     assert.deepEqual(on.values,off.values,mode+" FACT CHANGED WHEN TREND ON");
     assert.deepEqual(on.labels,off.labels,mode+" labels moved");
     assert.deepEqual(on.axis,off.axis,mode+" axes changed");
     for(let i=0;i<2;i++)for(let k=0;k<off.canvas[i].length;k++){
       const a=off.canvas[i][k],b=on.canvas[i][k];
       if(a===null||b===null){assert.equal(a,b,mode+" missing bar");continue;}
       assert(Math.abs(a.x-b.x)<0.25&&Math.abs(a.y-b.y)<0.25,
         mode+" factual bar/line pixel changed at "+i+"/"+k);
     }
     assert.equal(on.forecast.length,1,mode+" only alert forecast remains independent dataset");
     assert.equal(on.forecast[0].type,"line");
     assert.equal(on.registeredPlugin,true,mode+" hatched segment plugin registered");
     assert.equal(on.options.index,off.labels.length-1,mode+" hatching targets current period only");
     assert.equal(on.options.observedHoursPerDay,off.values[0].at(-1),
       mode+" hatching uses unchanged actual bar");
     assert(Number.isFinite(on.options.forecastHoursPerDay),mode+" forecast hours supported");
     // Use the real chart callback attached after rendering. The footer must
     // be readable and must not leak ISO timestamps / microseconds / offsets.
     const renderedFooter=await page.evaluate(()=>{
       const chart=window.Chart.getChart(document.querySelector("#cityIntensityChart"));
       const index=chart.data.labels.length-1;
       const cb=chart.config.options.plugins.tooltip.callbacks.footer;
       return cb([{dataIndex:index}]);
     });
     assert(Array.isArray(renderedFooter)&&renderedFooter.length===2,
       mode+" tooltip must have two concise cutoff lines");
     assert(renderedFooter.every(line=>!line.includes("T09:")&&!/\\d{4}-\\d{2}-\\d{2}T\\d{2}:/.test(line)),
       mode+" raw ISO cutoff found in tooltip: "+JSON.stringify(renderedFooter));
     assert(!JSON.stringify(renderedFooter).includes("+02:00") &&
       !JSON.stringify(renderedFooter).includes(".366"),
       mode+" timezone/microseconds leaked in tooltip");
     report.cases.push({mode,eligible:true,factHours:off.values[0].at(-1),
       factAlerts:off.values[1].at(-1),forecastHours:on.options.forecastHoursPerDay,
       forecastAlerts:on.forecast[0].points[0],originalHours:old.values[0].at(-1),
       tooltipFooter:renderedFooter});
     if(mode==="quarterly")await page.screenshot({path:"trend-fact-invariance-mobile.png"});
     await page.$eval("#showTrend",el=>{
       el.checked=!el.checked;
       el.dispatchEvent(new Event("change",{bubbles:true}));
     });
     const reset=await snapshot();
     assert.deepEqual(reset.values,off.values,mode+" fact changed on reset");

   }
   // Quarterly current period is sourced from completed October. A
   // November-only window hides its original Q4 bar; explain the correct
   // date-range condition instead of claiming that verified data are stale.
   await setPeriod("quarterly");
   await page.$eval("#cityDateFrom",el=>{
     el.value="2026-11-01";
     el.dispatchEvent(new Event("change",{bubbles:true}));
   });
   await page.$eval("#cityDateTo",el=>{
     el.value="2026-11-15";
     el.dispatchEvent(new Event("change",{bubbles:true}));
   });
   const excluded=await snapshot();
   assert.equal(excluded.enabled,false,"Nov-only window excludes October-sourced Q4 bar");
   assert.equal(excluded.helpVisible,true,"unavailable quarter has info icon");
   assert.equal(excluded.helpText,
     "Для прогнозу IV кварталу виберіть діапазон від 01.10.2026 або раніше.",
     "quarter tooltip must show precise earliest date");
   assert(!excluded.reason.includes("свіжого"),"do not suggest stale data for a range problem");
   await page.$eval("#cityDateFrom",el=>{
     el.value="2026-10-01";
     el.dispatchEvent(new Event("change",{bubbles:true}));
   });
   const included=await snapshot();
   assert.equal(included.enabled,true,"including October start restores valid Q4 forecast");
   assert.equal(included.helpVisible,false,"valid quarter hides unavailability info icon");
   report.quarterRange={excludedReason:excluded.helpText,
     restoredForecast:included.enabled,actualQ4:included.values[0].at(-1)};
   console.log("TREND_FACT_BROWSER_INVARIANCE_PASS",JSON.stringify(report));
 }catch(e){report.faults.push(String(e));console.error(e);}
 fs.writeFileSync("trend-fact-invariance-browser.json",JSON.stringify(report,null,2));
 await browser.close();
 if(report.faults.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
