/* Research preview only. This module NEVER mutates verified dashboard data or KPI. */
(function(root,factory) {
  "use strict";
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.KyivEarlyPreview=api;
  if(root?.document) {
    const launch=()=>api.mount(root.document,root.fetch.bind(root),
      new URL("/kyiv-early-2022-preview.json",root.location.origin).href);
    if(root.document.readyState==="loading")root.document.addEventListener("DOMContentLoaded",launch);
    else launch();
  }
})(typeof window!=="undefined"?window:null,function() {
  "use strict";
  const DAYS=["2022-02-24","2022-02-25","2022-02-26","2022-02-27"];
  const CLOCK=/^2022-02-2[4-8]T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+02:00$/;
  const assert=(v,reason)=>{if(!v)throw new Error(reason);};
  const localDay=ms=>new Date(ms+7200000).toISOString().slice(0,10);
  const midnightAfter=ms=>Date.parse(localDay(ms)+"T00:00:00Z")+86400000-7200000;
  function unionSeconds(parts) {
    let end=-Infinity,seconds=0;
    for(const [a,b] of parts.sort((x,y)=>x[0]-y[0])) {
      seconds+=Math.max(0,b-Math.max(a,end));
      end=Math.max(end,b);
    }
    return Math.round(seconds/1000);
  }
  function validate(data) {
    assert(data?.schema==="kyiv-early-2022-preview-v1"&&data.city_key==="kyiv"&&
      data.status==="provisional_estimated_not_canonical"&&
      data.not_in_verified_kpi===true&&data.not_published_to_neon===true&&
      data.range_start===DAYS[0]&&data.range_end===DAYS[3]&&
      data.start_count===24&&data.timezone==="Europe/Kyiv","BAD_PREVIEW_CONTRACT");
    assert(Array.isArray(data.source_files)&&data.source_files.length===4&&
      DAYS.every(day=>data.source_files.some(s=>s.date===day&&/^[a-f0-9]{64}$/.test(s.sha256))),"BAD_SOURCE_HASH");
    assert(Array.isArray(data.events)&&data.events.length===24,"BAD_EVENT_COUNT");
    const map=Object.fromEntries(DAYS.map(d=>[d,{count:0,segments:[]}]));
    const carry=[],seen=new Set();
    let eventSeconds=0,thirty=0;
    for(const e of data.events) {
      assert(CLOCK.test(e.start)&&CLOCK.test(e.estimated_end)&&
        e.confirmed_end===null&&e.confidence==="unverified"&&
        e.source_file==="alerts_"+e.start.slice(0,10)+".csv"&&
        DAYS.includes(e.start.slice(0,10)),"BAD_EVENT_EVIDENCE");
      const start=Date.parse(e.start),end=Date.parse(e.estimated_end);
      assert(Number.isFinite(start)&&Number.isFinite(end)&&
        end>start&&end-start<=86400000&&!seen.has(start),"BAD_INTERVAL");
      seen.add(start);eventSeconds+=(end-start)/1000;
      if(end-start===1800000)thirty++;
      map[e.start.slice(0,10)].count++;
      for(let cursor=start;cursor<end;) {
        const stop=Math.min(end,midnightAfter(cursor)),day=localDay(cursor);
        assert(stop>cursor,"BAD_SPLIT");
        if(map[day])map[day].segments.push([cursor,stop]);
        else {assert(day==="2022-02-28","BAD_SPILLOVER");carry.push([cursor,stop]);}
        cursor=stop;
      }
    }
    const counts=DAYS.map(d=>map[d].count),daily=DAYS.map(d=>unionSeconds(map[d].segments));
    const carrySeconds=unionSeconds(carry),earlySeconds=daily.reduce((a,b)=>a+b,0);
    assert(counts.join(",")==="1,9,6,8"&&daily.join(",")==="3600,15300,10800,11466"&&
      carrySeconds===1416&&earlySeconds===41166&&eventSeconds===42582&&thirty===19,
      "SOURCE_TOTAL_MISMATCH");
    return {counts,daily,earlySeconds,carrySeconds,thirty};
  }
  function fmt(seconds,en) {
    const s=Math.round(seconds),h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
    return h+" "+(en?"hr":"год")+" "+String(m).padStart(2,"0")+" "+(en?"min":"хв")+
      (x?" "+String(x).padStart(2,"0")+" "+(en?"sec":"с"):"");
  }
  function write(doc,id,a,b,en) {
    const n=doc.getElementById(id);if(n)n.textContent=en?b:a;
  }
  function row(doc,tbody,cells) {
    const tr=doc.createElement("tr");
    for(const cell of cells) {
      const td=doc.createElement("td");td.textContent=String(cell);tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  function render(doc,data,proof) {
    const en=doc.documentElement.lang==="en";
    write(doc,"kyivEarlyTitle","Рання історія Києва · 24–27 лютого 2022","Kyiv early history · 24–27 February 2022",en);
    write(doc,"kyivEarlyTag","Тест · орієнтовно","Test · approximate",en);
    write(doc,"kyivEarlyNote","Дані alerts.in.ua за 24–27 лютого 2022 року неповні. Час відбою міг бути умовним, часто через 30 хвилин. Ці години не є підтвердженими й не входять до основних KPI.","Early alerts.in.ua records may be incomplete; all-clears may be estimated, frequently at 30 minutes. These hours are unverified and excluded from the main KPIs.",en);
    write(doc,"kyivEarlyTotal",data.events.length+" оголошення · "+fmt(proof.earlySeconds,false)+" орієнтовно",data.events.length+" announcements · "+fmt(proof.earlySeconds,true)+" approximate",en);
    write(doc,"kyivEarlySpill","Ще "+fmt(proof.carrySeconds,false)+" 28 лютого з тривоги попереднього дня (не враховані в підтвердженій статистиці).","A further "+fmt(proof.carrySeconds,true)+" falls on 28 February from the previous day's alert (not included in verified statistics).",en);
    write(doc,"kyivEarlyToggle","Усі 24 оголошення та орієнтовні відбої","All 24 announcements and approximate all-clears",en);
    const a=doc.getElementById("kyivEarlyDaily"),b=doc.getElementById("kyivEarlyEvents");
    assert(a&&b,"MISSING_PREVIEW_TABLES");a.replaceChildren();b.replaceChildren();
    DAYS.forEach((day,i)=>row(doc,a,[day.split("-").reverse().join("."),proof.counts[i],fmt(proof.daily[i],en),en?"Approximate":"Орієнтовно"]));
    for(const e of data.events)row(doc,b,[e.start.slice(0,19).replace("T"," "),e.estimated_end.slice(0,19).replace("T"," "),
      fmt((Date.parse(e.estimated_end)-Date.parse(e.start))/1000,en),en?"Unverified":"Не підтверджено"]);
    for(const [id,ua,eng] of [
      ["kyivEarlyDayHead","Дата","Date"],["kyivEarlyCountHead","Оголошень","Announcements"],
      ["kyivEarlyHoursHead","Час під тривогою","Time under alert"],["kyivEarlyQualityHead","Якість","Quality"],
      ["kyivEarlyStartHead","Початок (Київ)","Start (Kyiv)"],
      ["kyivEarlyEndHead","Відбій із джерела (Київ)","Source all-clear (Kyiv)"],
      ["kyivEarlyDurationHead","Тривалість","Duration"],["kyivEarlyStatusHead","Статус","Status"],
      ["kyivEarlyMethodLink","Методологія alerts.in.ua","alerts.in.ua methodology"]])write(doc,id,ua,eng,en);
  }
  function mount(doc,fetcher,url) {
    const box=doc.getElementById("kyivEarlyPreviewSection"),select=doc.getElementById("citySelect");
    if(!box||!select)return null;
    let active=false,requested=false;
    async function sync() {
      box.hidden=select.value!=="kyiv";
      if(box.hidden||active||requested)return;
      requested=true;
      try {
        const response=await fetcher(url,{cache:"no-store"});
        assert(response?.ok,"PREVIEW_FETCH_FAILED");
        const payload=await response.json(),proof=validate(payload);
        render(doc,payload,proof);active=true;
      } catch(e) {
        box.dataset.error=e.message;
        write(doc,"kyivEarlyTotal","Тестові дані недоступні","Preview unavailable",false);
      }
    }
    select.addEventListener("change",sync);
    if(typeof MutationObserver!=="undefined")new MutationObserver(sync).observe(select,{childList:true});
    Promise.resolve().then(sync);
    return {sync};
  }
  return {validate,render,mount,fmt};
});
