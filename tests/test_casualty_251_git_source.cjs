"use strict";
/* Exact candidate Git source is fetched from the immutable commit over HTTPS.
   Only the site-prod HEAD response/canonical alias are simulated pre-GO;
   this is NOT a claim that the production sidecar exists. */
const assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const repo="olegbalakin-cmyk/kyiv-air-alerts-grafana";
const root=path.resolve(__dirname,"..");
const src=require(path.join(root,"kyiv-air-alerts-grafana/pages-preview/casualty-partial-source.js"));
const adapter=require(path.join(root,"kyiv-air-alerts-grafana/pages-preview/casualty-partial-preview.js"));
globalThis.crypto ||= crypto.webcrypto;
const head=process.env.GITHUB_SHA;
if(!/^[a-f0-9]{40}$/.test(head||""))throw Error("exact commit required");
const BASE="https://raw.githubusercontent.com/"+repo+"/"+head+"/kyiv-air-alerts-grafana/data/";
const local=(file)=>fs.readFileSync(path.join(root,"kyiv-air-alerts-grafana/data",file),"utf8");
const digest=text=>crypto.createHash("sha256").update(text).digest("hex");
const jsonResp=(body,status=200)=>({ok:status===200,status,text:async()=>body});
(async()=>{
  const fetchExact=async name=>{
    const response=await fetch(BASE+name,{cache:"no-store",signal:AbortSignal.timeout(45000)});
    assert.equal(response.status,200,"immutable Git GET "+name);
    return response.text();
  };
  const [dash,side]=await Promise.all([
    fetchExact("dashboard_data.json"),fetchExact("casualty_partial_months.json")
  ]);
  assert.equal(digest(dash),digest(local("dashboard_data.json")),"actual Git C6 dashboard bytes");
  assert.equal(digest(side),digest(local("casualty_partial_months.json")),"actual Git sidecar bytes");
  const shaResp=()=>jsonResp(JSON.stringify({object:{sha:head}}));
  const requests=[];
  const req=async url=>{
    requests.push(url);
    if(url===src.HEAD_URL)return shaResp();
    if(url===src.CANONICAL || url===BASE+"casualty_partial_months.json")return jsonResp(side);
    if(url===BASE+"dashboard_data.json")return jsonResp(dash);
    return jsonResp("not found",404);
  };
  const actual=await src.load("canonical_site_prod",req);
  assert.equal(actual.mode,"canonical_site_prod");
  assert.equal(actual.sourceSha,head);
  const view=adapter.validate(actual.sidecar,actual.dashboard.casualties_by_city);
  assert.equal(view.verified_minimum,11);
  assert.equal(view.verified_event_groups,4);
  assert.equal(requests.filter(u=>u===src.HEAD_URL).length,2);
  assert.ok(requests.includes(BASE+"dashboard_data.json"));
  assert.ok(requests.includes(BASE+"casualty_partial_months.json"));
  assert.ok(requests.includes(src.CANONICAL));
  const faulty=async (kind)=>{
    let seen=0;
    const response=async url=>{
      if(url===src.HEAD_URL) {
        seen++;
        if(kind==="advanced"&&seen===2)return jsonResp(JSON.stringify({object:{sha:"a".repeat(40)}}));
        return shaResp();
      }
      if(kind==="404"&&url===src.CANONICAL)return jsonResp("missing",404);
      if(kind==="missing_dashboard"&&url.endsWith("/dashboard_data.json"))return jsonResp("",404);
      if(url===src.CANONICAL)return jsonResp(kind==="tamper"?"{}":side);
      if(url===BASE+"casualty_partial_months.json")return jsonResp(side);
      if(url===BASE+"dashboard_data.json")return jsonResp(dash);
      return jsonResp("not found",404);
    };
    await assert.rejects(()=>src.load("canonical_site_prod",response),
      kind==="tamper"?/differs/:kind==="advanced"?/advanced/:/HTTP/);
  };
  for(const kind of ["tamper","advanced","404","missing_dashboard"])await faulty(kind);
  await assert.rejects(()=>src.load("frozen_test",async()=>jsonResp("",404)),/HTTP/);
  const token=process.env.GITHUB_TOKEN;
  assert.ok(token && token.length>10,"read-only GitHub Actions token required for authenticated API HEAD");
  const liveHead=await fetch("https://api.github.com/repos/"+repo+"/git/ref/heads/site-prod",
    {headers:{"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,
      "X-GitHub-Api-Version":"2022-11-28"},signal:AbortSignal.timeout(20000)});
  assert.equal(liveHead.status,200,"real live HEAD GET");
  const siteProdSha=(await liveHead.json()).object.sha;
  assert.match(siteProdSha,/^[a-f0-9]{40}$/);
  const productionAdvanced=siteProdSha!=="f7e0681ca6aa98405638dae7a63c884f4ed55d20";
  if(productionAdvanced)console.log("CASUALTY_251_REPIN_REQUIRED",siteProdSha);
  const productionSidecar=await fetch("https://raw.githubusercontent.com/"+repo+"/site-prod/kyiv-air-alerts-grafana/data/casualty_partial_months.json",
    {signal:AbortSignal.timeout(20000)});
  assert.equal(productionSidecar.status,404,
    "production sidecar unexpectedly exists; STOP before owner-GO");
  const report={schema:"casualty-251-immutable-git-transport-v1",candidate_head:head,
    site_prod_head:siteProdSha,
    dashboard_sha256:digest(dash),sidecar_sha256:digest(side),
    same_commit_transport:true,production_sidecar_http_status:404,
    canonical_live_verified:false,canonical_candidate_replay_verified:true,
    production_advanced_requires_fresh_C6_gate:productionAdvanced,
    negative_cases:["tamper","advanced","404","missing_dashboard"],promotion:"OFF"};
  fs.writeFileSync("casualty-251-git-source.json",JSON.stringify(report,null,2)+"\n");
  console.log("CASUALTY_251_CANONICAL_CANDIDATE_REAL_GIT_PASS",JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
