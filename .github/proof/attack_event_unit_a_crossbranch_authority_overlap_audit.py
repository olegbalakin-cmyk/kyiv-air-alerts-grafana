#!/usr/bin/env python3
"""Read-only, bounded structural probe before the cross-branch authority audit."""
import json
import os
import subprocess

BRANCHES = [
 "kyiv-postcutoff-historical-backfill-shadow-2026-10-07",
 "kyiv-historical-development-classifier-replay-2026-10-08",
 "kyiv-historical-development-failure-diagnosis-2026-10-08",
 "kyiv-historical-discovery-calibration-pilot-2026-10-08",
 "kyiv-historical-google-news-url-resolution-repair-2026-10-08",
 "kyiv-historical-source-set-revision-pilot-2026-10-09",
 "kyiv-historical-source-set-stage2-2026-10-09",
 "kyiv-historical-variant-a-development-diagnosis-2026-10-09",
 "kyiv-new-immutable-development-runner-proof-2026-10-09",
]
TARGETS = [
 ("UNIT_A", "HEAD", "research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"),
 ("UNIT_A_A3", "HEAD", "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"),
 ("POSTCUTOFF", "kyiv-postcutoff-historical-backfill-shadow-2026-10-07", "research/kyiv_postcutoff_historical_backfill_shadow_2026-10-07.json"),
 ("DEV_67", "kyiv-new-immutable-development-runner-proof-2026-10-09", "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"),
]

def git(*args, check=True):
 p = subprocess.run(["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
 if p.returncode and check:
  raise RuntimeError("git " + " ".join(args[:4]) + ": " + p.stderr[:400])
 return p.stdout if p.returncode == 0 else None

def structure(obj, level=0):
 if level > 3: return type(obj).__name__
 if isinstance(obj, dict):
  return {k: structure(v,level+1) for k,v in list(obj.items())[:24]}
 if isinstance(obj, list):
  return {"type":"array","n":len(obj),"sample_shape":structure(obj[0],level+1) if obj else None}
 return type(obj).__name__

for branch in BRANCHES:
 lookup=git("ls-remote","--heads","origin","refs/heads/"+branch) or ""
 if not lookup:
  print(json.dumps({"branch":branch,"status":"MISSING"}))
  continue
 sha=lookup.split()[0]
 git("-c","protocol.version=2","fetch","--no-tags","--depth=1","--filter=blob:none","origin","refs/heads/"+branch+":refs/remotes/origin/"+branch)
 tree=git("ls-tree","-r","--name-only",sha,"research/") or ""
 paths=[p for p in tree.splitlines() if "kyiv" in p.lower() and any(k in p.lower() for k in ["historical","development","source_set","postcutoff","variant","calibration","classifier","runner","diagnosis"])]
 print(json.dumps({"branch":branch,"head":sha,"research_paths":paths[-45:]}))
for name,rev,path in TARGETS:
 if rev!="HEAD":
  rev="refs/remotes/origin/"+rev
 text=git("show",rev+":"+path,check=False)
 if text is None:
  print(json.dumps({"source":name,"path":path,"status":"MISSING"}))
  continue
 try:
  data=json.loads(text)
  print(json.dumps({"source":name,"path":path,"size":len(text.encode()),"shape":structure(data)}))
 except Exception as exc: print(json.dumps({"source":name,"path":path,"error":str(exc)[:250]}))
