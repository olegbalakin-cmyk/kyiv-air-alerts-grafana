const fs = require("node:fs");
const puppeteer = require("puppeteer-core");
const base = process.env.PREVIEW_URL;
if (!/^https:\/\/[a-z0-9-]+(?:--[a-z0-9-]+)?\.netlify\.app\/?$/.test(base || "") ||
    !base.includes("casualty-partial-239-draft-preview")) throw Error("ISOLATED_NETLIFY_URL_REQUIRED");
(async () => {
  const browser = await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN || "/usr/bin/google-chrome",
    args:["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]});
  const checks = [], errors = [], screenshots = [];
  const check = (name, ok, detail) => { checks.push({name,pass:!!ok,detail}); if(!ok) errors.push(name); };
  for (const lang of ["uk","en"]) {
    const page = await browser.newPage();
    await page.setViewport(lang==="en"?{width:390,height:844,isMobile:true,deviceScaleFactor:1}:{width:1400,height:900});
    const failures=[];
    page.on("pageerror", e => failures.push(String(e)));
    await page.goto(base.replace(/\/$/,"")+(lang==="en"?"/en/":"/")+"?city=lutsk&casyear=2026&ccasyear=2026",{waitUntil:"domcontentloaded",timeout:60000});
    await page.waitForFunction(() => {
      const c = document.querySelector("#casualtyChart");
      return document.querySelector("#citySelect")?.options.length===23 && c && window.Chart?.getChart(c)?.data.labels.includes("2026-10");
    },{timeout:90000});
    const snapshot = await page.evaluate(() => {
      const chart=id=>window.Chart.getChart(document.getElementById(id));
      const c=chart("casualtyChart");
      const ix=c.data.labels.indexOf("2026-09"), io=c.data.labels.indexOf("2026-10");
      const cmp=chart("compareCasualtiesChart");
      return {city:document.querySelector("#citySelect").value, cities:document.querySelector("#citySelect").options.length,
        labels:c.data.labels, sep:c.data.datasets.map(d=>({value:d.data[ix],status:d._exportRows?.[ix]?._casualty_status})),
        oct:c.data.datasets.map(d=>({value:d.data[io],status:d._exportRows?.[io]?._casualty_status})),
        note:document.querySelector("#casualtySourceNote").textContent,
        compareNote:document.querySelector("#compareCasualtiesNote").textContent,
        compareLabels:cmp?.data.labels, width:document.documentElement.scrollWidth, viewport:innerWidth,
        sourceVisible:!!document.querySelector("#casualtyEvidence a"),
        yearOption:[...document.querySelector("#casualtyYear").options].map(e=>e.value)};
    });
    check(lang+"-23-city",snapshot.cities===23,snapshot.cities);
    check(lang+"-sep-partial",snapshot.sep.some(v=>v.status==="september_partial_confirmed_lower_bound"),snapshot.sep);
    check(lang+"-oct-minimum",snapshot.oct.some(v=>v.value===6 && v.status==="verified_incident_lower_bound_not_monthly_total"),snapshot.oct);
    check(lang+"-labels",snapshot.compareLabels.includes("2026-09")&&snapshot.compareLabels.includes("2026-10"),snapshot.compareLabels);
    check(lang+"-note",lang==="uk"?/Вересень/.test(snapshot.note)&&/Жовтень/.test(snapshot.note):/September/.test(snapshot.note)&&/October/.test(snapshot.note),snapshot.note);
    check(lang+"-source",snapshot.sourceVisible,true);
    check(lang+"-mobile-width",snapshot.width<=snapshot.viewport+3,[snapshot.width,snapshot.viewport]);
    const screen="casualty-239-"+lang+".png";await page.screenshot({path:screen,fullPage:true});screenshots.push(screen);
    await page.select("#citySelect","kyiv");
    const unknown=await page.evaluate(()=>({note:document.querySelector("#casualtySourceNote").textContent,
      monthValues:window.Chart.getChart(document.querySelector("#casualtyChart"))?.data?.datasets?.map(d=>d.data.at(-1))}));
    check(lang+"-oct-unknown",unknown.monthValues.every(v=>v===null),unknown.monthValues);
    check(lang+"-unknown-copy",lang==="uk"?/невідомо/.test(unknown.note):/unknown/.test(unknown.note),unknown.note);
    await page.select("#casualtyInterval","yearly");
    const annual=await page.evaluate(()=>({note:document.querySelector("#casualtySourceNote").textContent,
      labels:window.Chart.getChart(document.querySelector("#casualtyChart"))?.data?.labels}));
    check(lang+"-annual-cutoff",lang==="uk"?/січень–серпень/.test(annual.note):/January–August/.test(annual.note),annual.note);
    check(lang+"-2026-year",annual.labels.includes("2026"),annual.chart.labels);
    await page.select("#compareA","lutsk");await page.select("#compareB","kyiv");await page.select("#compareC","khmelnytskyi");
    const comparison=await page.evaluate(()=>{
      const ch=window.Chart.getChart(document.querySelector("#compareCasualtiesChart"));
      const ix=ch.data.labels.indexOf("2026-10");
      return {labels:ch.data.datasets.map(d=>d.label),values:ch.data.datasets.map(d=>d.data[ix]),
        statuses:ch.data.datasets.map(d=>d._exportRows?.[ix]?._casualty_status)};
    });
    check(lang+"-three-city-comparison",comparison.values.includes(6)&&comparison.values.includes(3)&&comparison.values.includes(null),comparison);
    const dl=await page.evaluate(()=>{
      const chart=window.Chart.getChart(document.querySelector("#compareCasualtiesChart"));
      return chart.data.datasets.map(d=>d._exportRows?.find(r=>r?.key==="2026-10")?._casualty_status);
    });
    check(lang+"-csv-status-backed",dl.includes("unknown_not_zero")&&dl.includes("verified_incident_lower_bound_not_monthly_total"),dl);
    check(lang+"-no-pageerrors",failures.length===0,failures);
    await page.close();
  }
  fs.writeFileSync("casualty-239-browser.json",JSON.stringify({url:base,checks,errors,screenshots,runHead:process.env.GITHUB_SHA},null,2));
  console.log("CASUALTY_239_BROWSER "+JSON.stringify({checks:checks.length,failures:errors}));
  await browser.close();
  if(errors.length)process.exitCode=1;
})().catch(err=>{console.error(err);process.exit(1)});
