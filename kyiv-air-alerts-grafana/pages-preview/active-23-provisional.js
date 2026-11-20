/* Production Git-only source-at-capture sidecar. Not a real-time status feed.
   Validate the published generation before this module is called; each use
   independently rejects stale source clocks, including after Kyiv midnight. */
(function(root,factory){
  "use strict";
  const api=factory();
  if(root)root.Active23Provisional=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const MAX_MS=8*3600000;
  const PERIODS=Object.freeze(["day","week","last7","last28","last30","last90","last180","month","quarter","allTime"]);
  const iso=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(d)&&Number.isFinite(Date.parse(d));
  const day=dt=>{
    const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Kyiv",
      year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(dt));
    const f=k=>parts.find(p=>p.type===k)?.value;
    return f("year")+"-"+f("month")+"-"+f("day");
  };
  function evaluate(snapshot,key,period="day",now=new Date()){
    if(!snapshot||snapshot.schema!=="c6-active-23-source-capture-v1"||
       snapshot.capture_scope!=="observed_at_last_collection_not_live"||
       snapshot.test_only!==false||snapshot.publication_allowed!==true||
       snapshot.delivery!=="site-prod-git"||
       snapshot.authoritative_live_status!==false||
       !/^[a-f0-9]{64}$/.test(snapshot.archive_sha256||"")||
       !/^[a-f0-9]{64}$/.test(snapshot.same_run_dashboard_sha256||"")||
       !/^[a-f0-9]{64}$/.test(snapshot.same_run_derived_sha256||"")||
       !/^[a-f0-9]{64}$/.test(snapshot.release_manifest_sha256||"")||
       typeof snapshot.source_generated_at!=="string"||
       !Number.isFinite(Date.parse(snapshot.source_generated_at))||
       snapshot.timezone!=="Europe/Kyiv"||snapshot.count_cities!==23||
       snapshot.count_source_open+snapshot.count_source_no_open!==23||
       !snapshot.cities||Object.keys(snapshot.cities).length!==23||
       !PERIODS.includes(period)||!Object.hasOwn(snapshot.cities,key))return null;
    const x=snapshot.cities[key],p=x.periods?.[period];
    if(x.city_key!==key||
       !["open_at_source_capture","no_open_at_source_capture"].includes(x.state)||
       !/^[a-f0-9]{64}$/.test(x.source_sha256||"")||
       !iso(x.capture_at)||typeof x.date!=="string"||x.date!==day(x.capture_at)||
       x.state==="open_at_source_capture"!==Boolean(x.start_at)||
       (x.start_at!==null&&!iso(x.start_at))||
       !p||!/^\d{4}-\d{2}-\d{2}$/.test(p.from)||p.through!==x.date)return null;
    const closed=p.closed_seconds,open=p.provisional_seconds,total=p.combined_seconds;
    if(![closed,open,total].every(n=>typeof n==="number"&&Number.isFinite(n)&&n>=0)||
       Math.abs(total-(closed+open))>.005||
       (x.state==="no_open_at_source_capture"&&open!==0)||
       (x.state==="open_at_source_capture"&&open<=0))return null;
    const capture=Date.parse(x.capture_at),start=x.start_at?Date.parse(x.start_at):null;
    if(start!==null&&start>=capture)return null;
    const nowTs=now instanceof Date?now.getTime():NaN;
    const fresh=Number.isFinite(nowTs)&&capture<=nowTs+120000&&
      nowTs-capture<=MAX_MS&&day(nowTs)===x.date;
    if(!fresh)return null;
    const elapsedToCapture=total/3600;
    return Object.freeze({key,period,from:p.from,through:p.through,closed,open,total,
      capturedAt:x.capture_at,source:x.source_key,
      scope:x.source_provenance,hadOpen:x.state==="open_at_source_capture",
      fresh:!!fresh,archival:true,elapsedToCapture});
  }
  return Object.freeze({evaluate,periods:PERIODS});
});
