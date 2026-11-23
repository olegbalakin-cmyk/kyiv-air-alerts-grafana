const fs=require("node:fs"),puppeteer=require("puppeteer-core");
const base=process.env.PREVIEW_URL;
if(!/^https:\/\/[a-z0-9-]+--casualty-partial-239-draft-preview\.netlify\.app\/?$/.test(base||""))throw Error("ISOLATED_ONLY");
const checks=[],errors=[],screens=[];
const check=(name,ok,details)=>{checks.push({name,pass:!!ok,details});if(!ok)errors.push(name);};
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
 try{
 for(const lang of ["uk","en"])for(const mode of ["desktop","mobile"]){
  const page=await browser.newPage();
  await page.setViewport(mode==="mobile"?{width:390,height:844,isMobile:true}:{width:1400,height:900});
  const failures=[];page.on("pageerror",e=>failures.push(String(e)));
  const url=base.replace(/\/$/,"")+(lang==="en"?"/en/":"/")+"?city=lutsk&casyear=2026&ccasyear=2026";
  await page.goto(url,{waitUntil:"domcontentloaded",timeout:90000});
  await page.waitForFunction(()=>document.documentElement.dataset.casualtyStatus==="verified"&&
    document.querySelector("#citySelect")?.options.length===23&&window.Chart?.getChart(document.querySelector("#casualtyChart"))?.data.labels.includes("2026-10"),{timeout:100000});
  check(lang+mode+"source",await page.evaluate(()=>document.documentElement.dataset.casualtySourceMode==="frozen_test"&&/^[a-f0-9]{40}$/.test(document.documentElement.dataset.casualtySourceSha)));
  const keys=await page.$$eval("#citySelect option",els=>els.map(e=>e.value).filter(Boolean));
  const verified={lutsk:6,poltava:1,"ivano-frankivsk":1,khmelnytskyi:3};
  for(const key of keys){
   await page.select("#citySelect",key);
   const r=await page.evaluate(()=>{
    const ch=window.Chart.getChart(document.querySelector("#casualtyChart"));
    const s=ch.data.labels.indexOf("2026-09"),o=ch.data.labels.indexOf("2026-10");
    return {sep:ch.data.datasets.map(d=>({n:d.data[s],st:d._exportRows?.[s]?._casualty_status})),
      oct:ch.data.datasets.map(d=>({n:d.data[o],st:d._exportRows?.[o]?._casualty_status})),
      source:!!document.querySelector("#casualtyEvidence a")};
   });
   const sep=r.sep.find(v=>v.st?.startsWith("september_"));
   const oct=r.oct.find(v=>v.st==="unknown_not_zero"||v.st==="verified_incident_lower_bound_not_monthly_total");
   check(lang+mode+key,!!sep&&!!oct&&r.sep.some(v=>v.n===null)&&
     oct.n===(verified[key]??null)&&r.source===Object.hasOwn(verified,key),r);
  }
  const screenshot="casualty-245-"+lang+"-"+mode+".png";
  await page.select("#citySelect","lutsk");await page.screenshot({path:screenshot,fullPage:true});screens.push(screenshot);
  await page.select("#casualtyInterval","yearly");
  const annual=await page.evaluate(()=>({labels:window.Chart.getChart(document.querySelector("#casualtyChart")).data.labels,
    note:document.querySelector("#casualtySourceNote").textContent}));
  check(lang+mode+"annual",annual.labels.includes("2026")&&
    (lang==="uk"?annual.note.includes("січень–серпень"):annual.note.includes("January–August")),annual);
  await page.select("#compareA","lutsk");await page.select("#compareB","kyiv");await page.select("#compareC","khmelnytskyi");
  const comparison=await page.evaluate(()=>{
   const ch=window.Chart.getChart(document.querySelector("#compareCasualtiesChart"));
   const ix=ch.data.labels.indexOf("2026-10");
   return {values:ch.data.datasets.map(d=>d.data[ix]),statuses:ch.data.datasets.map(d=>d._exportRows?.[ix]?._casualty_status)};
  });
  check(lang+mode+"compare",comparison.values.length===3&&comparison.values.includes(6)&&
    comparison.values.includes(3)&&comparison.values.includes(null)&&
    comparison.statuses.includes("unknown_not_zero"),comparison);
  await page.select("#compareCasualtyInterval","yearly");
  await page.reload({waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>document.documentElement.dataset.casualtyStatus==="verified",{timeout:90000});
  check(lang+mode+"reload",await page.evaluate(()=>document.documentElement.dataset.casualtySourceMode==="frozen_test"));
  check(lang+mode+"pageerrors",failures.length===0,failures);
  await page.close();
 }
 const blocked=await browser.newPage();
 await blocked.setRequestInterception(true);
 blocked.on("request",r=>r.url().endsWith("/casualty_partial_months.json")?
  r.respond({status:404,contentType:"application/json",body:"{}"}).catch(()=>{}):r.continue().catch(()=>{}));
 await blocked.goto(base.replace(/\/$/,"")+"/?city=lutsk",{waitUntil:"domcontentloaded",timeout:90000});
 await blocked.waitForFunction(()=>document.documentElement.dataset.casualtyStatus==="blocked",{timeout:90000});
 const fail=await blocked.evaluate(()=>({blocked:document.documentElement.dataset.casualtyStatus==="blocked",
    noChart:!window.Chart?.getChart(document.querySelector("#casualtyChart")),
    notice:document.querySelector("#casualtySourceNote").textContent}));
 check("HTTP404-fail-closed",fail.blocked&&fail.noChart&&fail.notice.includes("недоступні"),fail);
 await blocked.close();
 }finally{await browser.close();}
 fs.writeFileSync("casualty-245-browser.json",JSON.stringify({url:base,head:process.env.GITHUB_SHA,checks,errors,screens,promotion:"OFF"},null,2));
 console.log("CASUALTY_245_BROWSER "+JSON.stringify({checks:checks.length,errors}));
 if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
