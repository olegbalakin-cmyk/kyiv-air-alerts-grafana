import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path("_active23_diagnostic")
OUT.mkdir(exist_ok=True)
JS="""() => {
 const chart=window.Chart?.getChart(document.getElementById('cityIntensityChart'));
 const v=(id)=>document.getElementById(id)?.value||'';
 const d=window.state?.data?.cities?.kyiv;
 return { href:location.href, city:v('citySelect'), period:v('cityPeriod'), rangeFrom:v('cityDateFrom'),rangeTo:v('cityDateTo'),
   maxTo:document.getElementById('cityDateTo')?.max,
   chartLabels:chart?.data?.labels?.slice(-5),chartDatasets:chart?.data?.datasets?.map(x=>({label:x.label,vals:x.data?.slice(-3)})),
   hasChart:!!chart,banner:document.getElementById('freshnessBanner')?.textContent };
}"""
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
  all_results=[]
  for lang in ['uk','en']:
   page=await browser.new_page(viewport={'width':1366,'height':900},timezone_id='Europe/Kyiv')
   errors=[];failures=[]
   page.on('pageerror',lambda e: errors.append(str(e)))
   page.on('requestfailed',lambda req:failures.append({'url':req.url,'failure':req.failure}))
   url='https://ukraine-air-alerts.netlify.app/'+('en/' if lang=='en' else '')+'?city=kyiv&period=daily28'
   try:
    response=await page.goto(url,wait_until='domcontentloaded',timeout=90000)
    await page.wait_for_function("() => !!window.Chart?.getChart(document.getElementById('cityIntensityChart'))",timeout=90000)
    result={'language':lang,'status':response.status if response else None,'date':await page.evaluate("new Date().toISOString()"),'view':await page.evaluate(JS),'errors':errors,'failures':failures}
    await page.locator('#cityIntensityChart').screenshot(path=str(OUT/(lang+'-chart.png')))
    for path in ['dashboard_data.json','site_derived.json','active23_source_capture.json']:
     pass
    result['sourceReads']=await page.evaluate("""async () => {
     const base='https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/';
     const res={};
     for(const f of ['dashboard_data.json','site_derived.json','active23_source_capture.json']) {
       try {const r=await fetch(base+f+'?diagnostic='+Date.now(),{cache:'no-store'});
         if (!r.ok) {res[f]={http:r.status};continue;}
         const j=await r.json();
         res[f]={http:r.status,generated:j.meta?.generated_at||j.source_generated_at,release:j.meta?.publication_authority?.release_manifest_sha256||j.release_manifest_sha256,
           last:j.cities?.kyiv?.daily28?.at(-1)?.date,derivedDay:j.explorations?.daily28_current?.meta?.current_day,
           derivedKyiv:j.explorations?.daily28_current?.cities?.kyiv?.total_alert_duration_hours,
           snapshotDay:j.cities?.kyiv?.date};
       }catch(e){res[f]={error:String(e)}}
     }
     return res;
   }""")
   except Exception as e: result={'language':lang,'error':str(e),'errors':errors,'failures':failures}
   all_results.append(result)
   print('ACTIVE23_PRODUCTION_BROWSER_DIAGNOSTIC',json.dumps(result,ensure_ascii=False)[:18000],flush=True)
   await page.close()
  await browser.close()
  (OUT/'result.json').write_text(json.dumps(all_results,ensure_ascii=False,indent=2))
if __name__=='__main__':asyncio.run(main())
