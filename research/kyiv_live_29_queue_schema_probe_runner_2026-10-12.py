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

def crosswalk():
 from collections import defaultdict
 import csv,io
 from datetime import datetime,timezone
 def iso(s):return datetime.fromisoformat(s.replace("Z","+00:00"))
 inputs={k:fingerprint(k)[0] for k in OBJECTS}
 cutoff=iso("2026-10-07T19:05:00Z")
 frozen=iso("2026-10-11T05:56:28.255150Z")
 eps=sorted([e for e in inputs["state"]["cities"]["kyiv"]["episodes"] if iso(e["alert_start"])>=cutoff],key=lambda x:(x["alert_start"],x["episode_id"]))
 assert len(eps)==29,("frozen_count",len(eps))
 ids={e["episode_id"] for e in eps}
 assert len(ids)==29
 assert all(e["city_key"]=="kyiv" and e["alert_source"]=="kyiv_combined_exact_city" for e in eps)
 links=defaultdict(list);relationships=[];unresolved=[]
 for c in inputs["queue"]:
  triggers=c.get("trigger_episode_ids") or []
  if not isinstance(triggers,list):triggers=[triggers] if isinstance(triggers,str) else []
  matched=c.get("matched_episode_id")
  refs=sorted({x for x in triggers+([matched] if isinstance(matched,str) else []) if x in ids})
  if not refs:continue
  disposition="EXACT_MATCHED" if matched in refs and len(refs)==1 else ("AMBIGUOUS" if len(refs)>1 else "TRIGGER_ONLY")
  rec={"candidate_id":c.get("candidate_id","NOT_OBSERVABLE"),"observation_id":c.get("observation_id","NOT_OBSERVABLE"),"frozen_episode_refs":refs,"binding_disposition":disposition,"matched_episode_id":matched or "NOT_OBSERVABLE","trigger_episode_ids":triggers,"original_candidate":c}
  relationships.append(rec)
  for ep in refs:links[ep].append(rec["candidate_id"])
  if disposition!="EXACT_MATCHED":unresolved.append(rec)
 relationships.sort(key=lambda x:(x["candidate_id"],x["frozen_episode_refs"]))
 summaries=[];checks=[]
 for e in eps:
  due=checked=0
  for c in e["checks"]:
   d=iso(c["due_at"])<=frozen
   due+=d;checked+=bool(c.get("checked_at"))
   checks.append({"episode_id":e["episode_id"],"check_label":c.get("label","NOT_OBSERVABLE"),"due_at":c["due_at"],"checked_at":c.get("checked_at") or "NOT_OBSERVABLE","new_candidates":c.get("new_candidates","NOT_OBSERVABLE"),"is_due_at_frozen":d,"independent_successful_source_execution":"NOT_OBSERVABLE","coverage_evidence":"UNVERIFIED" if d else "NOT_DUE"})
  summaries.append({"city_key":e["city_key"],"episode_id":e["episode_id"],"alert_start":e["alert_start"],"alert_end":e["alert_end"],"alert_source":e["alert_source"],"candidate_ids":sorted(links[e["episode_id"]]),"candidate_count":len(links[e["episode_id"]]),"checks_scheduled":len(e["checks"]),"checks_due":due,"checks_checked":checked,"checks_independently_executed":"NOT_OBSERVABLE","checks_missing_coverage":due,"coverage_disposition":"UNVERIFIED"})
 assert sum(x["checks_scheduled"] for x in summaries)==116
 assert sum(x["checks_checked"] for x in summaries)==55
 assert sum(x["checks_scheduled"] for x in summaries[1:])==112
 assert sum(x["checks_checked"] for x in summaries[1:])==52
 out=Path("research/kyiv_live_29_frozen_git_outputs");out.mkdir(parents=True,exist_ok=True)
 def save(path,obj): (out/path).write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 save("01_integrity.json",{"pinned_commit":PIN,"objects":{k:fingerprint(k)[1] for k in OBJECTS}})
 save("02_episodes.json",summaries)
 with (out/"03_episodes.csv").open("w",newline="",encoding="utf-8") as f:
  keys=["city_key","episode_id","alert_start","alert_end","alert_source","candidate_count","checks_scheduled","checks_due","checks_checked","checks_independently_executed","checks_missing_coverage","coverage_disposition"]
  w=csv.DictWriter(f,fieldnames=keys,lineterminator="\n");w.writeheader();w.writerows({k:e[k] for k in keys} for e in summaries)
 save("04_candidate_relationships.json",relationships)
 save("05_followup_checks.json",checks)
 save("06_unresolved.json",{"candidate_relationships":unresolved,"due_checks_with_unverified_coverage":[x for x in checks if x["coverage_evidence"]=="UNVERIFIED"]})
 totals={"episodes":29,"full_queue_records":len(inputs["queue"]),"related_candidate_records":len(relationships),"candidate_episode_links":sum(len(x["frozen_episode_refs"]) for x in relationships),"unresolved_candidates":len(unresolved),"scheduled":sum(x["checks_scheduled"] for x in summaries),"due":sum(x["checks_due"] for x in summaries),"checked":sum(x["checks_checked"] for x in summaries),"independent_source_execution":"NOT_OBSERVABLE","missing_coverage":sum(x["checks_missing_coverage"] for x in summaries)}
 save("07_totals.json",totals)
 print("CROSSWALK_TOTALS",json.dumps(totals,sort_keys=True))
 print("OUTPUT_SHA256",json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())},sort_keys=True))

if __name__=="__main__":
 main()
 crosswalk()

