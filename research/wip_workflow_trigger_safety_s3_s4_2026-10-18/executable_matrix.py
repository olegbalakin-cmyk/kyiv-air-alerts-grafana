#!/usr/bin/env python3
"""Read-only Git ref and Actions-state assessment. Unsupported cases stay UNKNOWN."""
import json,os,subprocess
from pathlib import Path
from urllib.request import Request,urlopen
from safety_core import MONITOR,PIN,can_run,event_context,run_event,source
OUT=Path("/tmp/wip-s3s4-outputs");OUT.mkdir(exist_ok=True)
ROOT="https://api.github.com/repos/olegbalakin-cmyk/kyiv-air-alerts-grafana"
def git(*args):return subprocess.check_output(["git",*args],text=True).strip()
def save(name,value):(OUT/name).write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
def api(path):
 r=Request(ROOT+path,headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json"})
 with urlopen(r,timeout=40) as f:return json.load(f)
branches=[x.split(" ",1) for x in git("for-each-ref","--format=%(refname:short) %(objectname)","refs/remotes/origin/").splitlines() if x]
branches=[(name.removeprefix("origin/"),sha) for name,sha in branches if name!="origin/HEAD"]
assert len(branches)>50
inventory=[]
for name,sha in branches:
 path=sha+":"+MONITOR
 chk=subprocess.run(["git","rev-parse","--verify",path],capture_output=True,text=True)
 if chk.returncode:
  inventory.append({"ref":name,"commit":sha,"blob":None,"state":"ABSENT"})
  continue
 wf=source(sha,MONITOR)
 m=can_run(wf,default_registered=True,ctx=event_context(branch=name))
 inventory.append({"ref":name,"commit":sha,"blob":chk.stdout.strip(),
  "dispatch":"workflow_dispatch" in wf["on"],
  "state":"EXECUTABLE" if "monitor" in m.get("executable",[]) else "UNKNOWN" if m.get("unknown") else "HELD"})
taglines=git("ls-remote","--tags","origin").splitlines()
tags={line.split()[1].removeprefix("refs/tags/"):line.split()[0] for line in taglines if not line.split()[1].endswith("^{}")}
save("git_ref_inventory.json",{"branches":inventory,"tags":tags})
risky=[r for r in inventory if r["state"]=="EXECUTABLE" and r.get("dispatch")]
save("manual_dispatch_s3_matrix.json",{"branch_count":len(branches),"tag_count":len(tags),
 "unique_blobs":len(set(r["blob"] for r in inventory if r["blob"])),
 "unsafe_refs":risky,"unsafe_count":len(risky),"tag_dispatch_eligibility":"UNKNOWN" if tags else "NONE",
 "global_safety":"BLOCKED" if risky else "UNKNOWN"})
wf=source("origin/main",".github/workflows/live-due-orchestration-readback.yml")
assert wf
cases=[]
for sha in [PIN,"0"*40]:
 for conclusion in ["success","failure","cancelled","skipped",None]:
  x=run_event(wf,"Monitor explosion metric WIP",{"head_sha":sha,
     "head_branch":"multicity-wip-2026-09-16","conclusion":conclusion})
  cases.append({"sha":sha,"conclusion":conclusion,"state":x["state"],
                "jobs_executable":x.get("jobs_executable",[]),"jobs_unknown":x.get("jobs_unknown",[])})
assert any(x["jobs_executable"] for x in cases if x["sha"]==PIN and x["conclusion"]=="success")
assert all(not x["jobs_executable"] for x in cases if x["sha"]!=PIN or x["conclusion"]!="success")
save("workflow_run_s4_matrix.json",{"pinned_sha":PIN,"cases":cases})
edges=[("Apply historical source-retention repairs","historical-replay-orchestrator.yml"),
 ("Historical explosion replay orchestrator","historical-replay-qa.yml"),
 ("Historical explosion replay QA bundles","historical-replay-source-retention.yml"),
 ("Historical replay source-retention audit","historical-source-retention-repair-preflight.yml")]
cascade=[]
for upstream,name in edges:
 file=".github/workflows/"+name
 default=source("origin/main",file)
 candidate=source("HEAD",file)
 row={"upstream":upstream,"consumer":name,"default_present":default is not None,
  "candidate_present":candidate is not None,"conclusions":[]}
 for result in ["success","failure","cancelled","skipped",None]:
  a=run_event(default,upstream,{"head_branch":"multicity-wip-2026-09-16",
     "head_sha":PIN,"conclusion":result},default_present=default is not None)
  row["conclusions"].append({"conclusion":result,"state":a["state"],
     "jobs_executable":a.get("jobs_executable",[]),"jobs_unknown":a.get("jobs_unknown",[])})
 cascade.append(row)
save("historical_cascade_matrix.json",cascade)
active={}
for status in ["queued","in_progress","waiting","pending","requested"]:
 items=[];page=1
 while True:
  result=api("/actions/runs?status="+status+"&per_page=100&page="+str(page))
  batch=result.get("workflow_runs",[])
  items.extend({"id":v["id"],"name":v["name"],"status":v["status"],"event":v["event"],
                "head_sha":v["head_sha"],"head_branch":v["head_branch"]} for v in batch)
  if len(batch)<100:break
  page+=1
  assert page<40
 active[status]=items
save("inflight_actions_inspection.json",active)
save("execution_receipt.json",{"unsafe_dispatch_ref_count":len(risky),
 "active_run_count":sum(map(len,active.values())),"status":"RESIDUAL_RISK_OR_UNKNOWN",
 "main_guard_blob":git("rev-parse","origin/main:"+MONITOR),
 "candidate_guard_blob":git("rev-parse","HEAD:"+MONITOR)})
print("S3-S4_REAL_MATRIX_COMPLETED unsafe branches",len(risky))
