/* TEST ONLY: source-bound provisional Kyiv active interval; never enter certified history. */
(function(root,factory){
  const api=factory();
  if(root)root.KyivActiveProvisional=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const MAX_AGE_MS=8*3600000;
  const localDay=instant=>new Intl.DateTimeFormat("en-CA",{
    timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit"
  }).format(new Date(instant));
  const iso=d=>typeof d==="string"&&/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})$/.test(d)&&Number.isFinite(Date.parse(d));
  function evaluate(snapshot,now=new Date()){
    if(snapshot?.schema!=="kyiv-active-provisional-test-v1"||snapshot?.test_only!==true||
       snapshot?.source!=="kyiv_digital_live"||
       snapshot?.status!=="unclosed_at_source_capture"||
       snapshot?.alert_type!=="AIR"||snapshot?.city_key!=="kyiv"||
       snapshot?.ends_at!==null||!iso(snapshot?.started_at)||
       !iso(snapshot?.captured_at)||!/^\\d{4}-\\d{2}-\\d{2}$/.test(snapshot?.date||"")||
       !/^[a-f0-9]{64}$/.test(snapshot?.source_body_sha256||"")||
       snapshot?.github_run_id!==44680696823||snapshot?.github_run_attempt!==1)return null;
    const start=Date.parse(snapshot.started_at),at=Date.parse(snapshot.captured_at),
          current=now instanceof Date?now.getTime():NaN;
    if(!Number.isFinite(current)||start>=at||at>current+120000||
       current-at>MAX_AGE_MS||at-start>26*3600000)return null;
    if(localDay(start)!==snapshot.date||localDay(at)!==snapshot.date||
       localDay(current)!==snapshot.date)return null;
    const totalMinutes=Math.floor((at-start)/60000);
    if(totalMinutes<=0)return null;
    return Object.freeze({date:snapshot.date,minutes:totalMinutes,
      hours:Math.floor(totalMinutes/60),remainingMinutes:totalMinutes%60,
      started_at:snapshot.started_at,captured_at:snapshot.captured_at,
      source_body_sha256:snapshot.source_body_sha256});
  }
  return Object.freeze({evaluate});
});
