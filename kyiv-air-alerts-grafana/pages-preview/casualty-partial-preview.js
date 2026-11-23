/* Issue #245: display-only partial casualty months from the canonical #240 sidecar.
   No revisions, credits, promotion or mutation. Unknown != zero. */
(function(root) {
  "use strict";
  const SEP="2026-09", OCT="2026-10";
  const CUTS=Object.freeze({kyiv:"2026-09-15",kherson:"2026-09-17",
    odesa:"2026-09-18",zaporizhzhia:"2026-09-18"});
  function reject(message){throw new Error("Unsafe casualty sidecar: "+message);}
  const integer=n=>Number.isSafeInteger(n)&&n>=0;
  function validate(payload,originalSeries) {
    if (!payload || payload.schema!=="casualty-partial-months-v1" ||
        payload.promotion!=="OFF" || payload.publication_allowed!==false ||
        payload.published_monthly_overwrite!==false ||
        payload.contains_exact_monthly_totals!==false ||
        payload.is_complete!==false || payload.latest_exact_month!=="2026-08" ||
        !/^site-prod@[0-9a-f]{40}$/.test(payload.baseline_ref||"") ||
        !/^[0-9a-f]{40}$/.test(payload.baseline_sha||"") ||
        payload.canonical_data_url!=="https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/casualty_partial_months.json" ||
        !payload.year_2026_policy?.includes("January-August") ||
        payload.source_frozen_git_blob_shas?.["research/casualty_publisher_240/october_2026_verified_events_frozen.json"]!=="444973fba6295c58c3a6423ff4e872774f273d99")
      reject("top-level publisher contract or immutable reviewed-source pin");
    const keys=Object.keys(originalSeries||{}).sort();
    if(keys.length!==23 || Object.keys(payload.cities||{}).length!==23)
      reject("23-city cardinality");
    const cities={};const seenIncidents=new Set();
    for(const key of keys) {
      const monthly=originalSeries[key]?.monthly;
      const months=payload.cities[key];
      if(!Array.isArray(monthly)||monthly.length===0 ||
         monthly.at(-1)?.month!==SEP ||
         monthly.some(r=>r.month>=OCT||r.is_partial_period===true) ||
         !months || Object.keys(months).sort().join(",")!==[OCT,SEP].sort().join(","))
        reject("baseline drift/extra month: "+key);
      const sep=months[SEP],oct=months[OCT];
      if(!sep||!oct||sep.is_complete!==false||oct.is_complete!==false ||
         sep.monthly_exact_total!==null||oct.monthly_exact_total!==null ||
         sep.status!=="partial_baseline" ||
         !integer(sep.confirmed_baseline_deaths) ||
         sep.confirmed_baseline_deaths!==monthly.at(-1).deaths ||
         sep.confirmed_event_lower_bound!==null ||
         sep.coverage_through!==(CUTS[key]||null) ||
         sep.coverage_unknown!==(sep.coverage_through===null) ||
         !Array.isArray(sep.verified_individual_event_dates) ||
         JSON.stringify(sep.verified_individual_event_dates)!==JSON.stringify(key==="sumy"?["2026-09-20"]:[]) ||
         sep.provenance?.baseline_ref!==payload.baseline_ref ||
         sep.provenance?.source_git_blob_shas?.["kyiv-air-alerts-grafana/data/casualties/master_20cities_monthly_wide.csv"]!==payload.baseline_sha ||
         oct.confirmed_baseline_deaths!==null)
        reject("September coverage/baseline or exact-month contamination: "+key);
      const bound=oct.confirmed_event_lower_bound;
      if(bound===null) {
        if(oct.status!=="unknown"||oct.provenance!==null||oct.last_verified_at!==null)
          reject("unknown October cell: "+key);
      } else {
        if(!Number.isSafeInteger(bound)||bound<=0||oct.status!=="verified_incident_lower_bound" ||
           !Array.isArray(oct.provenance?.incident_ids)||oct.provenance.incident_ids.length<1 ||
           !Array.isArray(oct.provenance?.source_urls)||oct.provenance.source_urls.length<2 ||
           oct.provenance.research_git_blob_sha!=="444973fba6295c58c3a6423ff4e872774f273d99" ||
           !/^\d{4}-\d{2}-\d{2}$/.test(oct.last_verified_at||""))
          reject("unreviewed event minimum: "+key);
        for(const incident of oct.provenance.incident_ids) {
          if(typeof incident!=="string"||!incident.startsWith("incident:"+key+":")||seenIncidents.has(incident))
            reject("duplicate/unscoped event identity");
          seenIncidents.add(incident);
        }
        if(oct.provenance.source_urls.some(url=>typeof url!=="string"||!url.startsWith("https://")))
          reject("invalid source URL: "+key);
      }
      cities[key]=Object.freeze({city_slug:key,september:sep,october:oct,
        lower_bound:bound,month:OCT});
    }
    const expected={lutsk:6,poltava:1,"ivano-frankivsk":1,khmelnytskyi:3};
    if(seenIncidents.size!==4 || Object.values(cities).reduce((s,c)=>s+(c.lower_bound||0),0)!==11 ||
       keys.some(k=>cities[k].lower_bound!==(Object.hasOwn(expected,k)?expected[k]:null)))
      reject("reviewed October incident allowlist or sum mismatch");
    if(Object.values(cities).reduce((s,c)=>s+c.september.confirmed_baseline_deaths,0)!==56)
      reject("September existing baseline/Sumy anti-dedup mismatch");
    return Object.freeze({month:OCT,cities:Object.freeze(cities),
      verified_event_groups:seenIncidents.size,
      verified_minimum:Object.values(cities).reduce((sum,c)=>sum+(c.lower_bound||0),0),
      source_baseline_ref:payload.baseline_ref});
  }
  function rows(originalMonthly,key,view) {
    if(!view)return originalMonthly||[];
    if(!Array.isArray(originalMonthly)||!view.cities[key])reject("invalid display series");
    const rec=view.cities[key],old=originalMonthly.at(-1);
    if(old?.month!==SEP||old.deaths!==rec.september.confirmed_baseline_deaths)
      reject("post-validation source drift");
    const baseline=rec.september.confirmed_baseline_deaths;
    const september={...old,deaths:null,is_partial_period:true,
      partial_through:rec.september.coverage_through,
      coverage_unknown:rec.september.coverage_unknown,
      confirmed_event_lower_bound:baseline>0?baseline:null,
      _casualty_status:baseline>0?"september_partial_confirmed_lower_bound":"september_unknown_not_zero"};
    const october={time:OCT+"-01T00:00:00",month:OCT,deaths:null,
      is_partial_period:true,partial_through:null,
      confirmed_event_lower_bound:rec.lower_bound,
      _casualty_status:rec.lower_bound===null?"unknown_not_zero":"verified_incident_lower_bound_not_monthly_total"};
    return [...originalMonthly.slice(0,-1),september,october];
  }
  function describeRow(row,en) {
    if(!row?.is_partial_period)return "";
    const name=row.month===SEP?(en?"September":"Вересень"):(en?"October":"Жовтень");
    const label=row.confirmed_event_lower_bound===null?
      (en?"unknown (not zero)":"невідомо (це не нуль)"):
      (en?"at least "+row.confirmed_event_lower_bound+" confirmed":
        "щонайменше "+row.confirmed_event_lower_bound+" підтверджених");
    const coverage=row.month===SEP?
      (row.partial_through?
        (en?"; baseline through "+row.partial_through:"; базова перевірка до "+row.partial_through):
        (en?"; coverage cutoff unknown":"; дата завершення охоплення невідома")):"";
    return name+" 2026 — "+label+coverage+
      (en?"; incomplete, not a final monthly total.":"; неповний, не остаточний місячний підсумок.");
  }
  function description(key,view,en) {
    const row=rows([{month:SEP,deaths:view?.cities[key]?.september?.confirmed_baseline_deaths}],key,view).at(-1);
    return row?describeRow(row,en):"";
  }
  function sourceFor(key,view) {
    return view?.cities?.[key]?.october?.provenance?.source_urls?.[0]||null;
  }
  const api=Object.freeze({validate,rows,description,describeRow,sourceFor});
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  else root.CasualtyPartialPreview=api;
})(typeof window!=="undefined"?window:globalThis);
