/* Issue #245: mutually pinned casualty sidecar + dashboard reader.
   Canonical production mode NEVER falls back to a test fixture.
   Frozen preview is explicitly opted in by an isolated-site feature file. */
(function(root){
  "use strict";
  const REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana";
  const BASE="https://raw.githubusercontent.com/"+REPO+"/";
  const PART="kyiv-air-alerts-grafana/data/";
  const CANONICAL=BASE+"site-prod/"+PART+"casualty_partial_months.json";
  const HEAD_URL="https://api.github.com/repos/"+REPO+"/git/ref/heads/site-prod";
  function reject(reason){throw new Error("Casualty source binding: "+reason);}
  async function getText(url,request){
    const response=await request(url,{cache:"no-store"});
    if(!response?.ok)reject("HTTP "+(response?.status||"no response")+" at "+url);
    return response.text();
  }
  async function getSha(url,request){
    const body=JSON.parse(await getText(url,request));
    const sha=body?.object?.sha;
    if(!/^[a-f0-9]{40}$/.test(sha||""))reject("invalid site-prod HEAD");
    return sha;
  }
  async function digest(text){
    if(!root.crypto?.subtle||typeof TextEncoder!=="function")reject("SHA-256 not available");
    const h=await root.crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));
    return [...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,"0")).join("");
  }
  async function load(mode,request=root.fetch.bind(root)){
    if(mode==="frozen_test"){
      const binding=JSON.parse(await getText("casualty-test-binding.json",request));
      if(binding?.schema!=="casualty-245-frozen-binding-v1"||
         binding.mode!=="frozen_test"||
         !/^[a-f0-9]{40}$/.test(binding.site_prod_sha||"")||
         !/^[a-f0-9]{64}$/.test(binding.dashboard_sha256||"")||
         !/^[a-f0-9]{64}$/.test(binding.sidecar_sha256||"")||
         binding.promotion!=="OFF"||binding.production===true)
        reject("invalid isolated-preview binding manifest");
      const [dash,side]=await Promise.all([
        getText("data.json",request),
        getText("casualty_partial_months.json",request)
      ]);
      if(await digest(dash)!==binding.dashboard_sha256||
         await digest(side)!==binding.sidecar_sha256)
        reject("frozen test bundle checksum drift");
      const sidecar=JSON.parse(side);
      if(sidecar.baseline_ref!=="site-prod@"+binding.site_prod_sha)
        reject("sidecar frozen baseline differs from dashboard release pin");
      return {dashboard:JSON.parse(dash),sidecar,sourceSha:binding.site_prod_sha,mode};
    }
    if(mode==="canonical_site_prod"){
      const before=await getSha(HEAD_URL,request);
      const pin=BASE+before+"/"+PART;
      const [dash,side,pinnedSide]=await Promise.all([
        getText(pin+"dashboard_data.json",request),
        getText(CANONICAL,request),
        getText(pin+"casualty_partial_months.json",request)
      ]);
      if(await digest(side)!==await digest(pinnedSide))
        reject("canonical branch sidecar differs from pinned same-commit sidecar");
      const after=await getSha(HEAD_URL,request);
      if(after!==before)reject("site-prod advanced during source read");
      return {dashboard:JSON.parse(dash),sidecar:JSON.parse(side),sourceSha:before,mode};
    }
    reject("unapproved mode");
  }
  const api=Object.freeze({load,digest,CANONICAL,HEAD_URL});
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  else root.CasualtyPartialSource=api;
})(typeof window!=="undefined"?window:globalThis);
