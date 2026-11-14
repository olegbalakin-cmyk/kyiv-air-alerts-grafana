"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const puppeteer=require("puppeteer-core");

(async()=>{
  const site=(process.env.PREVIEW_URL||"").replace(/\/+$/,"");
  if(!/^https:\/\/[a-z0-9-]+\.netlify\.app$/.test(site))throw Error("Expected an immutable Netlify deploy preview URL");
  const chrome=process.env.CHROME_BIN||"/usr/bin/google-chrome";
  const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
  const result={site,cases:[],pageErrors:[]};
  async function visit(path,expectLocale,expectedCanonical){
    const page=await browser.newPage();
    await page.setViewport({width:390,height:844,isMobile:true,deviceScaleFactor:1});
    page.on("pageerror",e=>result.pageErrors.push(String(e)));
    await page.goto(site+path,{waitUntil:"domcontentloaded",timeout:30000});
    const facts=await page.evaluate(()=>({
      language:document.documentElement.lang,
      canonical:document.querySelector('link[rel="canonical"]')?.href,
      alternate:[...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(x=>x.hreflang),
      title:document.title,
      currentUrl:location.href,
      scriptLoaded:typeof window.ChartShare!=="undefined",
      cssLoaded:[...document.styleSheets].some(x=>x.href?.includes("styles.css")),
      selectedEN:document.getElementById("langEn")?.getAttribute("aria-pressed")
    }));
    assert.equal(facts.language,expectLocale,JSON.stringify(facts));
    assert.equal(facts.canonical,expectedCanonical);
    assert.deepEqual(facts.alternate.sort(),["en","uk","x-default"]);
    assert.equal(facts.scriptLoaded,true);
    assert.equal(facts.cssLoaded,true);
    result.cases.push({path,locale:expectLocale,status:"PASS",canonical:facts.canonical});
    await page.close();
  }
  try {
    await visit("/","uk","https://ukraine-air-alerts.netlify.app/");
    await visit("/en/","en","https://ukraine-air-alerts.netlify.app/en/");
    const page=await browser.newPage();
    await page.goto(site+"/?lang=en&city=kyiv&period=monthly#chart-cityIntensityChart",{waitUntil:"domcontentloaded",timeout:30000});
    await page.waitForFunction(()=>location.pathname==="/en/"&&!location.search.includes("lang="),{timeout:10000});
    const redirected=new URL(page.url());
    assert.equal(redirected.pathname,"/en/");
    assert.equal(redirected.searchParams.get("city"),"kyiv");
    assert.equal(redirected.searchParams.get("period"),"monthly");
    assert.equal(redirected.hash,"#chart-cityIntensityChart");
    result.cases.push({path:"legacy-lang-en",status:"PASS"});
    await page.close();
    const switchPage=await browser.newPage();
    await switchPage.goto(site+"/en/?city=kyiv&period=monthly",{waitUntil:"domcontentloaded"});
    await switchPage.click("#langUk");
    await switchPage.waitForFunction(()=>location.pathname==="/",{timeout:10000});
    const switched=new URL(switchPage.url());
    assert.equal(switched.pathname,"/");
    assert.equal(switched.searchParams.get("city"),"kyiv");
    assert.equal(switched.searchParams.get("period"),"monthly");
    result.cases.push({path:"switch-language-with-filters",status:"PASS"});
    await switchPage.close();
    assert.deepEqual(result.pageErrors,[],JSON.stringify(result.pageErrors));
    result.status="PASS";
  }finally{
    await browser.close();
    fs.writeFileSync("bilingual-browser.json",JSON.stringify(result,null,2)+"\n");
  }
  console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
