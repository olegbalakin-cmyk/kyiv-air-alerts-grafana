/* TEST ONLY: immutable same-run 23-city source capture and Neon-closed intervals.
   NOT live status. No mutation of KPI, charts, exports, Neon or production JSON. */
(function(root,factory){
  "use strict";
  const api=factory();
  if(root)root.Active23Provisional=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const RUN=44680696823, MAX_MS=8*3600000;
  const ARCHIVE="3f822042ceaaea06746dca2683f5fcc7eabf1dc6539752db2069f9aaf464d641";
  const DASHBOARD="b88357df3bb324807f278d9e4ddc3d9d9ca3d1307ece107046374933a1422e2e";
  const PERIODS=Object.freeze(["day","week","last7","last28","last30","last90","last180","month","quarter","allTime"]);
  const iso=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(d)&&Number.isFinite(Date.parse(d));
  const day=dt=>{
    const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Kyiv",
      year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(dt));
    const f=k=>parts.find(p=>p.type===k)?.value;
    return f("year")+"-"+f("month")+"-"+f("day");
  };
  function evaluate(snapshot,key,period="day",now=new Date()){
    if(!snapshot||snapshot.schema!=="c2-active-23-source-snapshot-test-v1"||
       snapshot.test_only!==true||snapshot.publication_allowed!==false||
       snapshot.c2_run_id!==RUN||snapshot.c2_run_attempt!==1||
       snapshot.archive_sha256!==ARCHIVE||
       snapshot.same_run_dashboard_sha256!==DASHBOARD||
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
    const elapsedToCapture=total/3600;
    return Object.freeze({key,period,from:p.from,through:p.through,closed,open,total,
      capturedAt:x.capture_at,source:x.source_key,
      scope:x.source_provenance,hadOpen:x.state==="open_at_source_capture",
      fresh:!!fresh,archival:true,elapsedToCapture});
  }
  return Object.freeze({evaluate,periods:PERIODS});
});
