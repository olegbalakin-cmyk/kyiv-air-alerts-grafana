#!/usr/bin/env python3
"""Independent Unit A object-state freeze. No A4 acceptance or mutation planning."""
import hashlib, json, os, re, sys, traceback
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from urllib.parse import urlparse
import psycopg

ROOT=Path("research/attack_event_unit_a_independent_shadow_gap_state_evidence_2026-10-10.json")
PROJ=Path(".github/proof/.unit_a_independent_projection.tmp.json")
OFF=Path(".github/proof/.unit_a_shadow_offline_gate.tmp.json")
BRANCH="br-bold-mode-b5rub8pq"
PROJECT="green-cake-44216048"
POS={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
TABLES={
 "parents":("alert_episodes","episode_uid legacy_episode_id city_key alert_type episode_state canonicalization_version start_at end_at"),
 "classifications":("attack_event_classifications","classification_uid classification_key_version classification_key historical_episode_id city_key alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256 supersedes_classification_uid alert_episode_uid"),
 "sources":("attack_event_sources","source_link_key_version source_link_key classification_uid observation_id source_family source_type source_type_state source_url telegram_channel telegram_message_id source_timestamp source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt content_sha256 content_hash_basis observation_classification_outcome classification_episode_id evidence_payload retrieval_provenance"),
 "events":("attack_events","attack_event_uid attack_event_key_version attack_event_key event_grain historical_episode_id city_key alert_start_at alert_end_at event_status current_classification_uid alert_episode_uid")
}
def norm(v):
 if isinstance(v,datetime):
  if v.tzinfo is None: raise RuntimeError("NAIVE_DATETIME")
  return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
 if isinstance(v,dict):return {k:norm(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [norm(x) for x in v]
 return v
def canonical(v):return json.dumps(norm(v),ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def hashed(v):return hashlib.sha256(canonical(v)).hexdigest()
def require(condition,code,example=None):
 if not condition:raise Gate(code,example)
class Gate(Exception):
 def __init__(self,code,example=None):super().__init__(code);self.code=code;self.example=example
def safe_report():
 return {"schema_version":"unit-a-independent-object-state-v1","verdict":"UNIT A INDEPENDENT SHADOW GAP STATE EVIDENCE = BLOCKED","OBJECT_STATE_EVIDENCE_GATE":"FAIL","A4_ACCEPTANCE_GATE":"NOT_RUN","A5_MANIFEST_ACCEPTED":"NO","A5_AUTHORIZED":"NO","base_main":"bc29c2ad343b13a3823d37489277a81b689e31d1","github_proof_branch":os.environ.get("GITHUB_REF_NAME"),"neon":{"project":PROJECT,"branch":BRANCH,"branch_verified":False,"repeatable_read":False,"read_only":False,"select_count":0,"attempted_writes":0,"committed_writes":0},"safety":{"classifier_executions":0,"matching_executions":0,"composition_executions":0,"discovery_executions":0,"public_evidence_requests":0,"a5_executions":0,"unit_b_executions":0,"unit_c_executions":0,"insert":0,"update":0,"delete":0,"merge":0,"ddl":0,"production_mutation":"NO"},"first_failing_gate":None,"smallest_deterministic_blocker_example":None}
def fetch(cur,report,sql,args=()):
 require(re.match(r"^\s*SELECT\b",sql,re.I),"SQL_NON_SELECT")
 report["neon"]["select_count"]+=1
 cur.execute(sql,args)
 return cur.fetchall()
def main():
 report=safe_report()
 try:
  require(PROJ.exists() and OFF.exists(),"OFFLINE_PROJECTION_ABSENT")
  gate=json.loads(OFF.read_text())
  require(gate["A4_OFFLINE_PROJECTION_GATE"]=="PASS" and gate["A4_CANONICAL_PROJECTION_GATE"]=="PASS","OFFLINE_UNIVERSE_GATE")
  raw=PROJ.read_bytes()
  require(hashlib.sha256(raw).hexdigest()==gate["offline_projection"]["temp_projection_sha256"],"OFFLINE_UNIVERSE_HASH")
  projection=json.loads(raw)
  cl=projection["classifications"];so=projection["sources"];pos=projection["events"]
  cls={x["classification_key"]:x for x in cl}
  src={x["source_link_key"]:x for x in so}
  ep={x["historical_episode_id"]:x for x in cl}
  require(len(cl)==len(cls)==len(ep)==1713 and len(so)==len(src)==1559 and len(pos)==10,"UNIVERSE_IDENTITY",{"class":len(cls),"source":len(src),"episode":len(ep)})
  require(len({x["historical_episode_id"] for x in pos})==10 and Counter(x["verdict"] for x in cl)=={"STRICT_EVENT_POSITIVE":9,"SENSITIVITY_EVENT_POSITIVE":1,"NEEDS_REVIEW":356,"NO_CONFIRMED_EVENT":1347},"UNIVERSE_DISTRIBUTION")
  report["universe"]={"classifications":1713,"source_memberships":1559,"target_episodes":1713,"positive":10,"non_positive":1703,"recovered_decision_refs":1418,"membership_episodes":370,"duplicate_canonical_identities":0}
  require(os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID")==BRANCH,"NEON_BRANCH_VARIABLE")
  url=os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL")
  require(bool(url),"NEON_SHADOW_SECRET_ABSENT")
  require(urlparse(url).hostname=="ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech","NEON_HOST_MISMATCH")
  ids=sorted(ep)
  fields={k:v[1].split() for k,v in TABLES.items()}
  conn=psycopg.connect(url,autocommit=True,connect_timeout=20)
  try:
   with conn.cursor() as cur:
    cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    try:
     trans=fetch(cur,report,"SELECT current_setting('transaction_isolation'),current_setting('transaction_read_only'),current_database()")[0]
     report["neon"]["repeatable_read"]=trans[0]=="repeatable read"
     report["neon"]["read_only"]=trans[1]=="on"
     report["neon"]["database_name"]=trans[2]
     require(report["neon"]["repeatable_read"] and report["neon"]["read_only"],"SERVER_TRANSACTION_NOT_READ_ONLY_REPEATABLE")
     report["neon"]["branch_verified"]=True
     catalog=fetch(cur,report,"SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s)",([v[0] for v in TABLES.values()],))
     available=defaultdict(set)
     for t,c in catalog:available[t].add(c)
     for key,(table,_) in TABLES.items():
      missing=set(fields[key])-available[table]
      require(not missing,"SCHEMA_MISSING_COLUMNS",{"table":table,"first":sorted(missing)[:3]})
     parent_rows=fetch(cur,report,"SELECT "+",".join(fields["parents"])+" FROM public.alert_episodes WHERE legacy_episode_id=ANY(%s)",(ids,))
     class_rows=fetch(cur,report,"SELECT "+",".join(fields["classifications"])+" FROM public.attack_event_classifications WHERE historical_episode_id=ANY(%s)",(ids,))
     source_rows=fetch(cur,report,"SELECT "+",".join("s."+f for f in fields["sources"])+",c.classification_key AS parent_classification_key FROM public.attack_event_sources s JOIN public.attack_event_classifications c ON c.classification_uid=s.classification_uid WHERE s.source_link_key=ANY(%s)",(sorted(src),))
     event_rows=fetch(cur,report,"SELECT "+",".join(fields["events"])+" FROM public.attack_events WHERE historical_episode_id=ANY(%s)",(ids,))
     def objects(rows,names):return [dict(zip(names,norm(x))) for x in rows]
     parents=objects(parent_rows,fields["parents"])
     classes=objects(class_rows,fields["classifications"])
     sources=objects(source_rows,fields["sources"]+["parent_classification_key"])
     events=objects(event_rows,fields["events"])
     pidx=defaultdict(list);cidx=defaultdict(list);sidx=defaultdict(list);eidx=defaultdict(list)
     for p in parents:pidx[p["legacy_episode_id"]].append(p)
     for c in classes:cidx[c["historical_episode_id"]].append(c)
     for s in sources:sidx[s["source_link_key"]].append(s)
     for e in events:eidx[e["historical_episode_id"]].append(e)
     out={"parents":[],"classifications":[],"sources":[],"events":[]}
     for c in cl:
      eid=c["historical_episode_id"];city=c["city_key"];start=c["alert_start_at"];end=c["alert_end_at"]
      matches=[p for p in pidx[eid] if all(p.get(k)==v for k,v in c["parent_identity"].items())]
      out["parents"].append({"classification_key":c["classification_key"],"episode_id":eid,"city":city,"expected_start":start,"expected_end":end,"matching_rows":sorted(matches,key=lambda x:canonical(x)),"all_legacy_id_rows":sorted(pidx[eid],key=lambda x:canonical(x))})
      episode_rows=[x for x in cidx[eid] if x["city_key"]==city and x["alert_start_at"]==start and x["alert_end_at"]==end]
      out["classifications"].append({"classification_key":c["classification_key"],"episode_id":eid,"city":city,"expected_start":start,"expected_end":end,"exact_key_rows":sorted([x for x in episode_rows if x["classification_key"]==c["classification_key"]],key=lambda x:canonical(x)),"all_episode_rows":sorted(episode_rows,key=lambda x:canonical(x))})
      out["events"].append({"episode_id":eid,"city":city,"expected_start":start,"expected_end":end,"authoritative_verdict":c["verdict"],"expected_positive":c["verdict"] in POS,"expected_event_key":c["attack_event_key"] if c["verdict"] in POS else None,"desired_classification_key":c["classification_key"],"observed_rows":sorted([x for x in eidx[eid] if x["city_key"]==city],key=lambda x:canonical(x))})
     for s in so:
      key=s["source_link_key"]
      out["sources"].append({"source_link_key":key,"classification_key":s["classification_key"],"observation_id":s["observation_id"],"content_sha256":s["content_sha256"],"expected_semantic_source_row_sha256":hashed(s),"observed_rows":sorted(sidx[key],key=lambda x:canonical(x))})
     for k in out:out[k].sort(key=lambda x:canonical(x))
     n={k:len(v) for k,v in out.items()}
     require(n=={"parents":1713,"classifications":1713,"sources":1559,"events":1713},"COVERAGE_CARDINALITY",n)
     require(all(len({canonical(x) for x in v})==len(v) for v in out.values()),"DUPLICATE_EVIDENCE_RECORD")
     summary={"parent_0":sum(not x["matching_rows"] for x in out["parents"]),"parent_1":sum(len(x["matching_rows"])==1 for x in out["parents"]),"parent_gt1":sum(len(x["matching_rows"])>1 for x in out["parents"]),"exact_key_classification_rows":sum(len(x["exact_key_rows"]) for x in out["classifications"]),"episode_classification_rows":sum(len(x["all_episode_rows"]) for x in out["classifications"]),"source_link_rows":sum(len(x["observed_rows"]) for x in out["sources"]),"attack_event_rows":sum(len(x["observed_rows"]) for x in out["events"])}
     core={"schema_version":"unit-a-independent-object-state-v1","universe":report["universe"],"evidence":out}
     ha={k:hashed(v) for k,v in out.items()}
     ha["combined"]=hashed(core)
     hb=hashlib.sha256(canonical(json.loads(canonical(core)))).hexdigest()
     require(ha["combined"]==hb,"NONDETERMINISTIC_EVIDENCE_SHA")
     report["coverage"]={**n,"total":sum(n.values()),"omitted_targets":0,"duplicate_evidence_identities":0}
     report["observed_state_summary"]=summary
     report["hashes"]={**ha,"combined_run_a":ha["combined"],"combined_run_b":hb,"equality":"PASS"}
     report["semantic_evidence"]=core
     report["verdict"]="UNIT A INDEPENDENT SHADOW GAP STATE EVIDENCE = FROZEN"
     report["OBJECT_STATE_EVIDENCE_GATE"]="PASS"
    finally:cur.execute("ROLLBACK")
  finally:conn.close()
 except Gate as exc:
  report["first_failing_gate"]=exc.code;report["smallest_deterministic_blocker_example"]=exc.example
 except Exception as exc:
  report["first_failing_gate"]="INDEPENDENT_SNAPSHOT_RUNTIME_FAILURE"
  report["smallest_deterministic_blocker_example"]={"type":type(exc).__name__,"message":str(exc)[:160]}
 ROOT.parent.mkdir(exist_ok=True,parents=True)
 ROOT.write_bytes(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()+b"\n")
 print("VERDICT="+report["verdict"])
 print("GATE="+report["OBJECT_STATE_EVIDENCE_GATE"])
 print("FIRST_FAILING_GATE="+str(report["first_failing_gate"]))
 print("SELECT_COUNT="+str(report["neon"]["select_count"]))
 print("ARTIFACT_SHA256="+hashlib.sha256(ROOT.read_bytes()).hexdigest())
 print("COVERAGE="+str(report.get("coverage")))
if __name__=="__main__":main()
