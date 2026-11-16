/* Browser proof for full static archive with real JS and without it. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
 const base = process.env.SEO_PREVIEW_BASE || 'http://127.0.0.1:8765';
 const output = path.resolve('seo-full-history-proof');
 fs.mkdirSync(output, {recursive:true});
 const manifest = JSON.parse(fs.readFileSync('_site/static-archive-manifest.json'));
 const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
 const checks=[];
 try {
  for(const screen of [{name:'desktop',width:1440,height:900},{name:'mobile',width:390,height:844}]) {
   for(const lang of ['uk','en']) {
    for(const allowJs of [false,true]) {
     const context=await browser.newContext({viewport:{width:screen.width,height:screen.height},javaScriptEnabled:allowJs});
     await context.route('**/*',route=>{
       const host=new URL(route.request().url()).hostname;
       return host==='127.0.0.1'||host==='localhost'?route.continue():route.abort();
     });
     const page=await context.newPage();
     const index=lang==='uk'?'/stats/':'/en/stats/';
     const dashboard=lang==='uk'?'/':'/en/';
     let response=await page.goto(base+dashboard,{waitUntil:'domcontentloaded'});
     assert.equal(response.status(),200);
     if(allowJs) await page.waitForTimeout(1300);
     const link=page.locator('footer #staticStatsFooterLink');
     assert.equal(await link.count(),1);
     assert.equal((await link.innerText()).trim(),lang==='uk'?'Статистика у таблицях':'Data tables');
     assert.equal(await link.getAttribute('href'),index);
     assert.ok(await link.isVisible());
     if(allowJs&&lang==='en') assert.match(await page.locator('footer > span').first().innerText(),/Data and code/);
     await link.scrollIntoViewIfNeeded();
     await page.locator('footer').screenshot({path:path.join(output,screen.name+'-'+lang+'-'+(allowJs?'js':'nojs')+'-footer.png')});
     checks.push({screen:screen.name,lang,allowJs,type:'dashboard-footer',pass:true});
     await link.click();
     await page.waitForURL('**'+index);
     assert.equal(await page.locator('tbody tr').count(),23);
     checks.push({screen:screen.name,lang,allowJs,type:'archive-index',count:23,pass:true});
     if(!allowJs) {
      const city=index+'kyiv/';
      response=await page.goto(base+city,{waitUntil:'domcontentloaded'});
      assert.equal(response.status(),200);
      assert.ok((await page.locator('a[href*="/2022/"]').count())>0);
      assert.ok((await page.locator('a[href*="/2026/"]').count())>0);
      assert.ok((await page.locator('a[href*="/2026-10/"]').count())>0);
      await page.screenshot({path:path.join(output,screen.name+'-'+lang+'-kyiv-years.png')});
      checks.push({screen:screen.name,lang,allowJs,type:'kyiv-years',pass:true});
      const partial=index+'kyiv/2022/';
      response=await page.goto(base+partial,{waitUntil:'domcontentloaded'});
      assert.equal(response.status(),200);
      assert.match(await page.locator('main').innerText(),lang==='uk'?/Частковий рік/:/Partial year/);
      checks.push({screen:screen.name,lang,allowJs,type:'partial-year',pass:true});
      for(const [slug,expected] of [['kyiv',224],['kharkiv',326],['lviv',37]]) {
       const route=index+slug+'/2026-10/';
       response=await page.goto(base+route,{waitUntil:'domcontentloaded'});
       assert.equal(response.status(),200);
       assert.equal(await page.locator('tbody tr').count(),31);
       assert.equal(Number(await page.locator('[data-month-count]').getAttribute('data-month-count')),expected);
       assert.equal(await page.locator('script[type="application/ld+json"]').count(),1);
       if(slug==='lviv')assert.match(await page.locator('main').innerText(),lang==='uk'?/район/:/Raion/);
       let overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
       assert.ok(overflow<=2,slug+': overflow '+overflow);
       if(slug==='lviv') await page.screenshot({path:path.join(output,screen.name+'-'+lang+'-lviv-month.png')});
       checks.push({screen:screen.name,lang,allowJs,type:'daily-month',slug,days:31,pass:true});
      }
     }
     await context.close();
    }
   }
  }
 } finally {await browser.close();}
 assert.equal(manifest.cities,23);
 assert.equal(manifest.verified_full_months,392);
 assert.equal(manifest.month_pages_both_languages,784);
 fs.writeFileSync(path.join(output,'browser-checks.json'),JSON.stringify({manifest,checks},null,2));
 process.stdout.write('SEO_FULL_HISTORY_BROWSER_PASS: '+checks.length+' checks, JS on/off, UA/EN, desktop/mobile, 23-city index and historical navigation\n');
})().catch(err=>{process.stderr.write('SEO_FULL_HISTORY_BROWSER_FAIL: '+(err.stack||err)+'\n');process.exitCode=1;});
