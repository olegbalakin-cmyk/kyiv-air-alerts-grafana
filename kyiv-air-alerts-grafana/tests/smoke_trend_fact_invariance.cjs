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
       visible:!document.querySelector("#showTrend").closest("label").classList.contains("hidden")};
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
       report.cases.push({mode,eligible:false,reason:off.reason,actual:off.values.map(v=>v.at(-1))});
       continue;
     }
     await page.click("#showTrend");
     const on=await snapshot();
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
     if(mode==="quarterly")await page.screenshot({path:"trend-fact-invariance-mobile.png"});
     await page.click("#showTrend");
     const reset=await snapshot();
     assert.deepEqual(reset.values,off.values,mode+" fact changed on reset");
     report.cases.push({mode,eligible:true,factHours:off.values[0].at(-1),
       factAlerts:off.values[1].at(-1),forecastHours:on.options.forecastHoursPerDay,
       forecastAlerts:on.forecast[0].points[0],originalHours:old.values[0].at(-1)});
   }
   console.log("TREND_FACT_BROWSER_INVARIANCE_PASS",JSON.stringify(report));
 }catch(e){report.faults.push(String(e));console.error(e);}
 fs.writeFileSync("trend-fact-invariance-browser.json",JSON.stringify(report,null,2));
 await browser.close();
 if(report.faults.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
