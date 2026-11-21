import test from "node:test";
import assert from "node:assert/strict";
import { decide, checkAndMaybeDispatch, config } from "../netlify/functions/c6-backup.mjs";

const current = "2026-11-21T23:47:00.000Z";
const ago = (h) => new Date(Date.parse(current)-h*3600000).toISOString();
const run = (h, status="completed", event="schedule") => ({
  created_at: ago(h), status, event,
});
const verdict = (runs, sincePublishHours=8) => decide({
  now: current, runs, lastDataCommitAt: ago(sincePublishHours),
});
test("hourly independent UTC cron is fixed and no HTTP route is exposed", () => {
  assert.deepEqual(config, {schedule:"47 * * * *"});
});
test("no retry inside four hour twenty minute gap", () => {
  assert.equal(verdict([run(3)], 9).reason, "C6_ATTEMPT_RECENT");
});
test("freshly published data do not cause unnecessary GitHub attempt", () => {
  assert.equal(verdict([run(8)], 3).reason, "C6_DATA_RECENT");
});
test("stale data and no recent attempts permit one backup dispatch", () => {
  assert.equal(verdict([run(8)], 9).reason, "C6_CATCHUP_REQUIRED");
});
test("failed and successful attempts both count towards spacing", () => {
  assert.equal(verdict([run(2),run(9)], 10).dispatch, false);
});
test("queued, waiting and in-progress are never doubled", () => {
  for (const status of ["queued","waiting","in_progress","pending","requested"]) {
    assert.equal(verdict([run(8),run(4.5,status)], 12).reason,
                 "C6_ACTIVE_OR_QUEUED");
  }
});
test("daily cap counts manual and native scheduled starts", () => {
  assert.equal(verdict(Array.from({length:6},(_,i)=>run(5+i)), 12).reason,
               "C6_DAILY_ATTEMPT_CAP");
});
test("push-only PR CI is never a sufficient history", () => {
  assert.throws(()=>verdict([run(9,"completed","push")], 12),
                /C6_RUN_HISTORY_MISSING/);
});
test("malformed, missing and future proof all fail closed", () => {
  assert.throws(()=>verdict([], 12), /RUN_HISTORY_MISSING/);
  assert.throws(()=>verdict([{}], 12), /INVALID_RUN_STATE/);
  assert.throws(()=>decide({now:current,runs:[run(9)],
    lastDataCommitAt:"2026-11-22T03:00:00Z"}), /FUTURE_DATA_CLOCK/);
});
test("no token or disabled flag ever POST", async () => {
  const calls=[];
  const fetchImpl = async (url, options) => {
    calls.push({url,options});
    if (url.includes("/commits?")) return {
      ok:true, json:async()=>[{
        sha:"a".repeat(40), commit:{committer:{date:ago(10)}}
      }]};
    return {ok:true,json:async()=>({workflow_runs:[run(9)]})};
  };
  const one=await checkAndMaybeDispatch({now:new Date(current),fetchImpl,
    enabled:false,token:"owner-secret-token"});
  assert.equal(one.action,"DRY_RUN_ONLY");
  const two=await checkAndMaybeDispatch({now:new Date(current),fetchImpl,
    enabled:true,token:""});
  assert.equal(two.reason,"OWNER_TOKEN_MISSING");
  assert.ok(calls.every(x=>x.options.method==="GET"));
  assert.ok(calls.every(x=>!JSON.stringify(x.options.headers).includes("owner-secret")));
});
test("owner-gated dispatch uses exact C6 controls and no Netlify", async () => {
  const calls=[];
  const fetchImpl=async(url, options)=>{
    calls.push({url,options});
    if (url.includes("/commits?")) return {
      ok:true, json:async()=>[{sha:"a".repeat(40),
          commit:{committer:{date:ago(10)}}}]};
    if (options.method==="POST") return {status:204};
    return {ok:true, json:async()=>({workflow_runs:[run(9)]})};
  };
  const got=await checkAndMaybeDispatch({now:new Date(current),fetchImpl,
    enabled:true,token:"owner-secret-token"});
  assert.equal(got.action,"DISPATCH_ACCEPTED");
  assert.equal(calls.filter(x=>x.options.method==="POST").length,1);
  const post=calls.find(x=>x.options.method==="POST");
  assert.ok(post.url.endsWith("/actions/workflows/update-netlify-site.yml/dispatches"));
  assert.deepEqual(JSON.parse(post.options.body),{
    ref:"main",inputs:{
      c6_run_now:"true",c6_neon_git_pilot:"false",
      c6_final_prepare_only:"false",c6_neon_git_release:"false"
    }
  });
});
test("recheck blocks a race with new scheduled run", async () => {
  let gets=0;const calls=[];
  const fetchImpl=async(url,options)=>{
    calls.push(options.method);
    if (url.includes("/commits?")) return {ok:true,json:async()=>[{
      sha:"a".repeat(40),commit:{committer:{date:ago(12)}}}]};
    gets++;
    return {ok:true,json:async()=>({workflow_runs:gets===1?
       [run(9)]:[run(0.01),run(9)]})};
  };
  const got=await checkAndMaybeDispatch({
    now:new Date(current),fetchImpl,enabled:true,token:"owner-secret-token"});
  assert.equal(got.action,"NONE");
  assert.equal(calls.filter(x=>x==="POST").length,0);
});
test("GitHub 403 or unreadable data blocks all writes",async()=>{
  let post=0;
  const fetchImpl=async(_url,opts)=>{
    if(opts.method==="POST") post++;
    return {ok:false,status:403};
  };
  await assert.rejects(checkAndMaybeDispatch({
    now:new Date(current),fetchImpl,enabled:true,token:"owner-secret-token"}),
    /GITHUB_READ_UNAVAILABLE/);
  assert.equal(post,0);
});
