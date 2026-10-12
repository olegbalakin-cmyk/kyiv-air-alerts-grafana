#!/usr/bin/env python3
"""READ-ONLY frozen Git object schema probe; never connects to a database."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path("kyiv-air-alerts-grafana/data")
PIN="92d57bbbfad60e6c09bb92372b1e84f38fa6ced4"
OBJECTS={
 "state": ("explosion_candidate_monitor_state.json","b255f516a8598bbd28faaa1a651249f4064b5620",4100971),
 "queue": ("explosion_review_queue.json","e7777b88bf1912572df10eb252f991ea6456feba",54234970),
 "run": ("explosion_candidate_monitor_last_run.json","19d27d7b72afb52a235e6dfc0914f5aee7082ce2",184821)
}
def shell(*args):
 return subprocess.check_output(["git",*args],stderr=subprocess.PIPE)
def fingerprint(name):
 path,oid,expected=OBJECTS[name]
 object_path=str(ROOT/path)
 actual=shell("rev-parse",f"{PIN}:{object_path}").decode().strip()
 assert actual==oid, (name,"tree",actual,oid)
 size=int(shell("cat-file","-s",oid).strip())
 raw=shell("cat-file","blob",oid)
 got=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
 assert got==oid and size==len(raw)==expected,(name,got,size,len(raw))
 parsed=json.loads(raw)
 return parsed,dict(git_sha1=got,byte_length=len(raw),sha256=hashlib.sha256(raw).hexdigest(),valid_json=True,
   top_type=type(parsed).__name__,top_count=len(parsed))
def summarize(obj,deep=2,limit=24):
 if isinstance(obj,dict):
  r={"type":"dict","size":len(obj),"keys":list(obj)[:limit]}
  if deep:
   r["fields"]={k:summarize(v,deep-1,10) for k,v in list(obj.items())[:min(limit,12)]}
  return r
 if isinstance(obj,list):
  r={"type":"list","size":len(obj)}
  if obj and deep: r["first"]=summarize(obj[0],deep-1,10)
  return r
 if isinstance(obj,str):return {"type":"str","sample":obj[:100],"length":len(obj)}
 return {"type":type(obj).__name__,"value":obj}
def main():
 assert shell("rev-parse",f"{PIN}^{{commit}}").decode().strip()==PIN
 data={};objects={};schema={}
 for name in OBJECTS:
  d,o=fingerprint(name)
  data[name]=d;objects[name]=o
  schema[name]=summarize(d,2)
 state=data["state"]
 if isinstance(state,dict):
  cities=state.get("cities")
  if isinstance(cities,dict):
   schema["state_kyiv"]=summarize(cities.get("kyiv"),4)
   schema["state_kyiv_episode_fields"]={}
   k=cities.get("kyiv")
   if isinstance(k,dict):
    for name,val in k.items():
     if isinstance(val,list) and val and isinstance(val[0],dict):
      schema["state_kyiv_episode_fields"][name]=summarize(val[0],3)
     if isinstance(val,dict) and val:
      first=next(iter(val.values()))
      if isinstance(first,dict):
       schema["state_kyiv_episode_fields"][name]=summarize(first,3)
 queue=data["queue"]
 if isinstance(queue,dict):
  schema["queue_collections"]={}
  for k,v in queue.items():
   if isinstance(v,list):
    schema["queue_collections"][k]={"length":len(v),"first":summarize(v[0],3) if v else None}
   elif isinstance(v,dict) and len(v)>3:
    schema["queue_collections"][k]={"length":len(v),"first":summarize(next(iter(v.values())),3)}
 elif isinstance(queue,list):
  schema["queue_first"]=summarize(queue[0] if queue else None,4)
 report=data["run"]
 report_keep=("finished_at","started_at","due_checks_at_cutoff","checked_due_checks_at_cutoff","unchecked_due_checks_at_cutoff","new_alert_episodes","city_count")
 report_meta={k:report.get(k) for k in report_keep} if isinstance(report,dict) else {}
 result={"scope":"frozen_git_objects_read_only_schema_probe","pinned_commit":PIN,"objects":objects,"schema":schema,"report_meta":report_meta,
         "database_queries":0,"database_writes":0,"classifier_runs":0}
 target=Path("research/kyiv_live_29_queue_schema_probe_2026-10-12.json")
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
 print("SCHEMA_PROBE_COMPLETE",target)
 print("OBJECT_FINGERPRINTS",json.dumps(objects,sort_keys=True))
 print("KYIV_STATE",json.dumps(schema.get("state_kyiv",{}),ensure_ascii=False)[:5000])
 print("QUEUE_COLLECTIONS",json.dumps(schema.get("queue_collections",{}),ensure_ascii=False)[:5000])
if __name__=="__main__":main()
