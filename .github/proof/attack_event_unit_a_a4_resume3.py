#!/usr/bin/env python3
"""Bounded Unit A A4 resume3: frozen offline projection then read-only shadow.
No classification, matching, composition, discovery or DB writes.
"""
from __future__ import annotations
import ast
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback
from urllib.parse import urlparse

BASE="c7886eece726ec4b1a0b7f7b2680c43ab7c979c6"
BRANCH="attack-event-unit-a-a4-shadow-gap-audit-resume3-2026-10-09"
OUT=Path("research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume3_2026-10-09.json")
TEMP=Path(".github/proof/.unit_a_a4_resume3_projection.tmp.json")
A3="research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
R3="research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
A1="research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
ADAPTER="research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json"
CROSS="research/attack_event_unit_a_crossbranch_authority_overlap_audit_2026-10-09.json"
REC="research/attack_event_unit_a_bounded_persistence_payload_replay_schema_repair_2026-10-09.json"
PIN_PROD="kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py"
PIN_MON="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
PROD_COMMIT="51adc76b715669e46e8c2c936906022d4d96ed44"
MON_COMMIT="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
MON_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
HELP_COMMIT="a0eb594dd4240d1d923ca5262725fc42f4807338"
HELP=".github/proof/attack_event_unit_a_source_identity_adapter_proof.py"
REC_HELP_COMMIT="41ee8d160c34145b9d9a51b9da095084cf342824"
REC_HELP=".github/proof/attack_event_unit_a_frozen_persistence_payload_recovery.py"
PINS={
 R3:("d8fe91fdbfdcf8d1b851a52358d7eb441308e0ee","a53f665c4f4da26f0b0699939c3b165f376da047","a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"),
 A3:("1422e8482303ec9262647ca55fef753a9aa2b3ea","4dfc8aa7132706e2a3a4febd655ffa0a2bd71640","bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"),
 A1:("2d07c81147932d39cb3a9d9934830f6eb707ee37","52e89792352513664428da3a7fcb9b43f79f1ba1","07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"),
 ADAPTER:(HELP_COMMIT,"a7e6b992180bfef3dd640fcd9ef8eec8a6436af7","568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891"),
 CROSS:("6a891372d4d59f9f2454123afcac2a21ef042d68","4c228f800350ed74363747a9a93bdcae312a5c36","3d63f49a118dcac3a2ef75db45e945cbc6f00a041b4f25ff8529c82cd95d9647"),
 REC:("41bec58604420333dc71910ec38f4a785f6b108e","cb0192e6776cce44b056bb88bf5618541f1c9339","d28d80e15251fed8aad7367748cda7ea3a75b37f45dcb9cd3b656a11db619317"),
 PIN_PROD:(PROD_COMMIT,"0118ca9e5f1308173e657257f1b49fe91cc19fe1",None),
 PIN_MON:(MON_COMMIT,MON_BLOB,None),
 HELP:(HELP_COMMIT,"83dd5279f4aeb17c8e06fe5bfaf143c07059efc2",None),
 REC_HELP:(REC_HELP_COMMIT,"1d0541bef22ced23c0028eda516cc6d13c55b869",None)}
SIX=("air_defense_context","candidate_evidence","controlled_blast_event_segments","sensitivity_basis","single_episode_day_inference","strict_explosion_evidence")
REQUIRED=("exact_city","strict_explosion","event_types","air_defense_context","air_defense_action","interception_claim","air_military_context","same_attack_context","temporal_binding","single_episode_day_inference","controlled_blast_event_segments","sensitivity_basis","classification_episode_id","candidate_evidence","review_provenance_adapter")
DIST={"STRICT_EVENT_POSITIVE":9,"SENSITIVITY_EVENT_POSITIVE":1,"NEEDS_REVIEW":356,"NO_CONFIRMED_EVENT":1347}
POSITIVE={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
KEY_SHA="ddf73127fa96c10b4882293cf8970a561d403d2b48a488c5a139ee5e8ae91a74"
REC_MAP_SHA="3dd4706afb5b48b874d9fd47b9d8e88e61b3de6f8574a57629b9c51b57cb5f35"
SOURCE_MAPPING_SHA="557bd96a2d5d0f8f337852965cb9ca9ead7c2d947f556c476d04aeffb13d7703"
NEON_PROJECT="green-cake-44216048"
NEON_BRANCH="br-bold-mode-b5rub8pq"

class Blocked(Exception):
 def __init__(self,code,example=None):
  super().__init__(code);self.code=code;self.example=example

def need(ok,code,example=None):
 if not ok:raise Blocked(code,example)

def cmd(*args):
 p=subprocess.run(["git",*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    env=dict(os.environ,GIT_NO_LAZY_FETCH="1",GIT_TERMINAL_PROMPT="0"))
 need(p.returncode==0,"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"git":args[:2],"stderr":p.stderr.decode(errors="replace")[-250:]})
 return p.stdout

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def hobj(x):return sha(canon(x))
def norm(v):
 if isinstance(v,datetime):
  need(v.tzinfo is not None,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","naive datetime")
  return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
 if isinstance(v,dict):return {k:norm(vv) for k,vv in v.items()}
 if isinstance(v,(list,tuple)):return [norm(x) for x in v]
 return v
def raw(ref,path):return cmd("show",ref+":"+path)
def pin(path):
 ref,blob,fsha=PINS[path]
 for target in (ref,):
  got=cmd("rev-parse",target+":"+path).decode().strip()
  need(got==blob,"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"path":path,"commit":target,"found_blob":got})
 b=raw(ref,path)
 if fsha:need(sha(b)==fsha,"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"path":path,"found_sha256":sha(b)})
 return b
def only_functions(source,names,globals_):
 tree=ast.parse(source.decode())
 found={x.name:x for x in tree.body if isinstance(x,ast.FunctionDef)}
 need(all(n in found for n in names),"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"missing_pure_methods":[n for n in names if n not in found]})
 import copy as _copy
 unit=ast.fix_missing_locations(ast.Module(body=[_copy.deepcopy(found[n]) for n in names],type_ignores=[]))
 exec(compile(unit,"pinned_pure_methods","exec"),globals_)
 return globals_
def helper_from_git(commit,path,alias):
 with tempfile.TemporaryDirectory(prefix="unit_a_pinned_") as t:
  p=Path(t)/(alias+".py");p.write_bytes(raw(commit,path))
  spec=importlib.util.spec_from_file_location(alias,p)
  mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  return mod
def init():
 return {
 "schema_version":1,"kind":"attack_event_execution_unit_a_shadow_persistence_gap_audit_resume3",
 "branch":BRANCH,"base_commit":BASE,"main_coordination_baseline":BASE,
 "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
 "verdict":"ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED",
 "A4_OFFLINE_PROJECTION_GATE":"FAIL","A4_CANONICAL_PROJECTION_GATE":"FAIL",
 "A5_PERSISTENCE_DELTA_GATE":"FAIL","A5_REQUIRED":"UNKNOWN","A5_AUTHORIZED":"NO",
 "first_failing_gate":None,"smallest_deterministic_blocker_example":None,
 "phase_reached":"PRECHECK","frozen_input_identities":{},
 "neon":{"project":NEON_PROJECT,"branch":NEON_BRANCH,"contacted":False,
   "branch_identity_verified":False,"repeatable_read":False,
   "read_only_transaction":False,"schema_compatible":None,"select_count":0,
   "attempted_writes":0,"committed_writes":0},
 "offline_projection":{},
 "parents":{"exact_bound":None,"missing":None,"ambiguous":None,"identity_sha256":None},
 "classification_gap":{"exact_present":None,"missing_no_prior_revision":None,
   "missing_with_prior_revision":None,"semantic_conflicts":None,"multiple_current_tips":None},
 "source_gap":{"exact_present":None,"missing":None,"semantic_conflicts":None},
 "event_gap":{"exact_present":None,"missing":None,"pointer_updates_required":None,
   "withdrawals_required":None,"semantic_conflicts":None},
 "A5_frozen_delta_manifest":None,"A5_DELTA_SHA256":None,
 "safety":{"classifier_executions":0,"matching_executions":0,"composition_executions":0,
   "discovery_executions":0,"public_evidence_requests":0,"unit_b_executions":0,
   "unit_c_executions":0,"ddl_statements":0,"db_insert":0,"db_update":0,
   "db_delete":0,"db_merge":0,"db_writes_attempted":0,"db_writes_committed":0,
   "alert_episodes_mutations":0,"a5_executions":0,"production_mutation":"NO"}}
def save(report):
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_bytes((json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode())
def fail_report(rep,exc):
 rep["first_failing_gate"]=exc.code
 rep["smallest_deterministic_blocker_example"]=norm(exc.example)
 rep["A5_PERSISTENCE_DELTA_GATE"]="FAIL"
 rep["A5_AUTHORIZED"]="NO"
 rep["verdict"]="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED"
 save(rep)
 print("A4_VERDICT=BLOCKED")
 print("FIRST_FAILING_GATE="+exc.code)
 if exc.example is not None:print("SMALLEST_BLOCKER="+json.dumps(norm(exc.example),ensure_ascii=False)[:900])
 print("NEON_CONTACTED="+str(rep["neon"]["contacted"]))
 print("ARTIFACT_SHA256="+sha(OUT.read_bytes()))
def preflight(report):
 need(os.environ.get("GITHUB_REF_NAME")==BRANCH,"UNIT_A_A4_INPUT_IDENTITY_DRIFT","unexpected branch")
 need(cmd("merge-base","HEAD",BASE).decode().strip()==BASE,
      "UNIT_A_A4_INPUT_IDENTITY_DRIFT","base ancestry")
 for p in PINS:
  b=pin(p)
  report["frozen_input_identities"][p]={"commit":PINS[p][0],"blob":PINS[p][1],"sha256":sha(b)}
 cross=json.loads(raw(PINS[CROSS][0],CROSS))
 need(cross.get("A5_CROSSBRANCH_GATE")=="PASS","UNIT_A_A4_INPUT_IDENTITY_DRIFT","crossbranch A5 gate")
 rec=json.loads(raw(PINS[REC][0],REC))
 need(rec.get("verdict")=="ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = PROVEN" and
      rec.get("A4_PAYLOAD_REPLAY_GATE")=="PASS","UNIT_A_A4_INPUT_IDENTITY_DRIFT","recovered replay acceptance")
 need(rec.get("determinism",{}).get("run_a_recovered_payload_sha256")==REC_MAP_SHA and
      rec.get("determinism",{}).get("run_b_recovered_payload_sha256")==REC_MAP_SHA,
      "UNIT_A_A4_INPUT_IDENTITY_DRIFT","recovered A/B SHA")
 need(rec.get("persistence_evidence",{}).get("payloads_sha256")==KEY_SHA,
      "UNIT_A_A4_INPUT_IDENTITY_DRIFT","recovered accepted payload SHA")
 need(len(rec.get("recovered_decision_map") or {})==1418,
      "UNIT_A_A4_INPUT_IDENTITY_DRIFT","recovered map 1418")
 adapter=json.loads(raw(PINS[ADAPTER][0],ADAPTER))
 need(adapter.get("run_a_mapping_sha256")==SOURCE_MAPPING_SHA and
      adapter.get("run_b_mapping_sha256")==SOURCE_MAPPING_SHA,
      "UNIT_A_A4_INPUT_IDENTITY_DRIFT","source content mapping hash")
 report["source_identity_mapping_sha256"]=SOURCE_MAPPING_SHA
 report["canonical_payload_sha256_expected"]=KEY_SHA
 report["recovered_decision_map_sha256"]=REC_MAP_SHA
 report["phase_reached"]="INPUT_IDENTITIES_VERIFIED"
 return rec,adapter
def build_once(report,label,rec,adapter):
 # Deliberately reload and decode frozen materialization independently for each run.
 helper=helper_from_git(HELP_COMMIT,HELP,"adapter_offline_"+label)
 recmod=helper_from_git(REC_HELP_COMMIT,REC_HELP,"recovery_offline_"+label)
 _,docs=helper.verify_inputs()
 a1=json.loads(docs["A1"]); a3=json.loads(docs["A3"])
 repaired=json.loads(raw(PINS[R3][0],R3))
 _,a1episodes,store,refs_total=helper.decode_a1(a1)
 original,ds,byuid=helper.verify_a3(a3,a1episodes)
 episodes=repaired["episode_results"]
 need(len(episodes)==1713 and refs_total==99663,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","A1 cardinality")
 need(repaired.get("distribution")==DIST,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","A3 verdict distribution")
 by_old={x["alert_episode_uid"]:x for x in original}
 membership=0
 for ep in episodes:
  old=by_old.get(ep["alert_episode_uid"])
  need(old is not None,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","unknown episode")
  for f in ("episode_id","city_key","alert_start","alert_end",
            "candidate_input_refs","candidate_decision_refs","composition_provenance"):
   need(ep.get(f)==old.get(f),"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":ep["alert_episode_uid"],"field":f})
  positions=ep.get("target_related_candidate_positions") or []
  need([ep["candidate_decision_refs"][i] for i in positions]==ep["target_related_candidate_decision_refs"],
       "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":ep["alert_episode_uid"],"field":"positions"})
  membership+=len(positions)
 need(membership==1559,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","membership cardinality")
 byref={ref:v.get("candidate_id") for ref,v in store.items()}
 temp={"recovery_target_counts":{},"persistence_payload_construction":{},
       "smallest_deterministic_blocker_example":None}
 occ,bydr,ds2=recmod.targets_build(temp,repaired,a3,byref)
 need(len(occ)==1559 and len(bydr)==1418 and
      len({x["alert_episode_uid"] for x in occ})==370,
      "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","occurrence 1559/1418/370")
 need(ds2=={dr:ds[dr] for dr in ds2},"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","decision source")
 recovered=rec["recovered_decision_map"]
 need(set(recovered)==set(bydr),"UNIT_A_A4_INPUT_IDENTITY_DRIFT","recovery map target keys")
 mon=only_functions(pin(PIN_MON),["apply_matching_result","classification_evidence_payload",
    "apply_classification_decision"],{})
 prod=only_functions(pin(PIN_PROD),["canonical_json_bytes","canonical_sha256",
    "_tuple_sha256","_parse_dt","utc_microseconds","_normalized_source_content",
    "_source_timestamp","_telegram_identity","_event_time_from_evidence",
    "_source_row","_review_provenance"],{
    "hashlib":hashlib,"json":json,"datetime":datetime,"timezone":timezone,
    "urlparse":urlparse,"SOURCE_LINK_KEY_VERSION":"attack-event-source-link-key-v1",
    "MONITOR_RELATIVE_PATH":PIN_MON,"PersistenceContractError":ValueError,
    "Any":object})
 payload_by_dr={}
 hashrows=[]
 for occurrence in occ:
  dr=occurrence["decision_ref"]
  recovered_item=recovered[dr]
  need(recovered_item.get("candidate_input_ref")==bydr[dr]["candidate_input_ref"] and
       recovered_item.get("candidate_id")==bydr[dr]["candidate_id"] and
       recovered_item.get("frozen_a3_parity_status")=="EXACT_MATCH",
       "UNIT_A_A4_RECOVERED_PAYLOAD_DRIFT",{"decision_ref":dr})
  fields=recovered_item.get("recovered_fields") or {}
  need(set(fields)==set(SIX),"UNIT_A_A4_RECOVERED_PAYLOAD_DRIFT",{"decision_ref":dr,"field_set":sorted(fields)})
  decision={**copy.deepcopy(ds2[dr]),**copy.deepcopy(fields)}
  payload=mon["classification_evidence_payload"](decision)
  need(set(payload)==set(REQUIRED),"UNIT_A_A4_RECOVERED_PAYLOAD_DRIFT",{"decision_ref":dr,"payload_keys":sorted(payload)})
  payload_by_dr[dr]=payload
  hashrows.append({"occurrence":occurrence,"evidence_sha256":hobj(payload)})
 need(len(hashrows)==1559 and hobj(hashrows)==KEY_SHA,
      "UNIT_A_A4_RECOVERED_PAYLOAD_DRIFT",{"actual_payload_sha256":hobj(hashrows),"count":len(hashrows)})
 # A1 has exact observation identities; read original immutable queue for the
 # complete source-row representation (incl. retrieval provenance).
 expect={(q["commit"],q["path"]):q for q in adapter["frozen_queue_inputs"]}
 need(len(expect)==89,"UNIT_A_A4_INPUT_IDENTITY_DRIFT","frozen queue authority 89")
 queue_cache={}
 input_by_uid=byuid
 outcome={"classifications":[],"events":[],"sources":[]}
 semantic_errors=[]
 comps=0
 observed_membership=0
 all_positions={(x["alert_episode_uid"],x["decision_ref"]) for x in occ}
 for ep in episodes:
  uid=ep["alert_episode_uid"];eid=ep["episode_id"];city=ep["city_key"]
  refs=ep["candidate_input_refs"];drefs=ep["candidate_decision_refs"]
  targets=set(ep.get("target_related_candidate_positions") or [])
  related=[]
  if targets:
   srcmeta=input_by_uid[uid]["evidence_provenance"]
   qi=(srcmeta.get("collection_queue_identity") or {})
   pair=(str(qi.get("commit") or ""),str(qi.get("path") or ""))
   expected=expect.get(pair)
   need(expected is not None,"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"uid":uid,"missing_queue":pair})
   if pair not in queue_cache:
    qbytes=raw(pair[0],pair[1])
    need(cmd("rev-parse",pair[0]+":"+pair[1]).decode().strip()==expected["blob"] and
         sha(qbytes)==expected["sha256"],"UNIT_A_A4_INPUT_IDENTITY_DRIFT",{"queue":pair})
    queue_cache[pair]=json.loads(qbytes)
   selected=helper.selected_queue_rows(queue_cache[pair],eid,srcmeta.get("followup_72h_checked_at"))
   need(len(selected)==len(refs),"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"queue_refs":len(refs),"actual":len(selected)})
   for i in sorted(targets):
    dr=drefs[i];cref=refs[i];candidate=store[cref];source=selected[i]
    need((uid,dr) in all_positions and dr in payload_by_dr,
         "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"decision_ref":dr})
    need(candidate["candidate_id"]==source.get("candidate_id")==bydr[dr]["candidate_id"] and
         prod["_normalized_source_content"](candidate)==prod["_normalized_source_content"](source),
         "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"candidate_input_ref":cref})
    decision={**copy.deepcopy(ds[dr]),**copy.deepcopy(recovered[dr]["recovered_fields"])}
    row=copy.deepcopy(source)
    mon["apply_classification_decision"](row,decision,copy.deepcopy(ds[dr]["matching"]))
    need(row["classification_evidence"]==payload_by_dr[dr],
         "UNIT_A_A4_RECOVERED_PAYLOAD_DRIFT",{"uid":uid,"decision_ref":dr})
    related.append((row,dr,cref))
    observed_membership+=1
  composition=ep.get("composition_provenance")
  if composition is not None:
   comps+=1
   anchor=str(composition.get("anchor_candidate_id") or "")
   anchors=[row for row,dr,cref in related if row.get("candidate_id")==anchor]
   need(len(anchors)==1 and ep["verdict"]=="STRICT_EVENT_POSITIVE" and
        composition.get("final_composed_verdict")=="approved_strict" and
        not ep.get("direct_strict_contributor_refs"),
        "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"composition_anchor":anchor})
   anchors[0]["status"]="approved_strict"
   anchors[0]["matched_episode_id"]=eid
   anchors[0]["composition_provenance"]=copy.deepcopy(composition)
   codes=list(anchors[0].get("classification_reason_codes") or [])
   for code in composition.get("reason_codes") or []:
    if code not in codes:codes.append(code)
   anchors[0]["classification_reason_codes"]=codes
   anchors[0]["review_note"]="episode-level composed strict classification"
   # The frozen, exactly-15-key decision payload MUST remain untouched.
  rows=[x[0] for x in related]
  start=prod["utc_microseconds"](ep["alert_start"])
  end=prod["utc_microseconds"](ep["alert_end"])
  need(start<end,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"interval":"invalid"})
  evidence=[]
  for row in sorted(rows,key=lambda r:(str(r.get("candidate_id") or ""),
                                      str(r.get("url") or ""),str(r.get("title") or ""))):
   id=str(row.get("candidate_id") or "").strip()
   need(bool(id),"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"uid":uid,"missing_observation":True})
   evidence.append([id,prod["canonical_sha256"](prod["_normalized_source_content"](row))])
  evidence.sort(key=lambda x:(x[0],x[1]))
  evidence_sha=prod["_tuple_sha256"](evidence)
  review=prod["_review_provenance"](rows)
  review_sha=prod["canonical_sha256"](review) if review else None
  reason_codes=sorted({str(code) for row in rows
                   for code in row.get("classification_reason_codes") or [] if str(code).strip()})
  types=sorted({str(x) for x in ep["event_types"] if str(x).strip()})
  qa=sorted({str(x) for x in ep["qa_reasons"] if str(x).strip()})
  verdict=ep["verdict"]
  tup=["attack-event-classification-key-v2",city,eid,start,end,verdict,
      json.dumps(types,ensure_ascii=False,separators=(",",":")),"MATERIALIZED",
      json.dumps(qa,ensure_ascii=False,separators=(",",":")),MON_BLOB,
      "historical-attack-event-air-defense-action-v2",
      "historical-attack-event-observation-v2",evidence_sha,review_sha]
  key=prod["_tuple_sha256"](tup)
  attack_key=prod["_tuple_sha256"](["attack-event-key-v1","HISTORICAL_ALERT_EPISODE",city,eid,start,end])
  event=verdict in POSITIVE
  tier="STRICT" if verdict=="STRICT_EVENT_POSITIVE" else "SENSITIVITY" if verdict=="SENSITIVITY_EVENT_POSITIVE" else None
  row_sem={"classification_key_version":"attack-event-classification-key-v2","classification_key":key,
     "historical_episode_id":eid,"city_key":city,"alert_type":"AIR",
     "alert_start_at":start,"alert_end_at":end,"verdict":verdict,"is_event":event,
     "positive_tier":tier,"event_types":types,"qa_reasons_state":"MATERIALIZED",
     "qa_reasons":qa,"classifier_reason_codes":reason_codes,"classifier_blob_sha":MON_BLOB,
     "classifier_methodology_version":"historical-attack-event-air-defense-action-v2",
     "normalization_version":"historical-attack-event-observation-v2",
     "evidence_set_sha256":evidence_sha,"review_provenance_sha256":review_sha,
     "human_review_state":"NEEDS_REVIEW" if verdict=="NEEDS_REVIEW" else "REVIEWED_EVIDENCE" if review else "NONE",
     "review_provenance":review,"composition_provenance":composition,
     "attack_event_key":attack_key,
     "parent_identity":{"legacy_episode_id":eid,"city_key":city,"alert_type":"AIR",
        "episode_state":"closed","canonicalization_version":"alert-canonicalization-v1",
        "start_at":start,"end_at":end}}
  outcome["classifications"].append(row_sem)
  if event:outcome["events"].append({"attack_event_key":attack_key,
     "attack_event_key_version":"attack-event-key-v1","event_grain":"HISTORICAL_ALERT_EPISODE",
     "historical_episode_id":eid,"city_key":city,"alert_start_at":start,"alert_end_at":end,
     "desired_status":"ACTIVE","desired_classification_key":key})
  origin={"ref":"OFFLINE_AUDIT_NON_SEMANTIC_PLACEHOLDER","commit":MON_COMMIT,
   "run_id":None,"monitor_blob":MON_BLOB,
   "origin_provenance":{"kind":"offline_unit_a_projection_non_persisted",
       "repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana",
       "ref":"OFFLINE_AUDIT_NON_SEMANTIC_PLACEHOLDER","commit":MON_COMMIT,
       "monitor_path":PIN_MON,"monitor_blob":MON_BLOB,
       "classifier_blob":MON_BLOB,
       "classifier_methodology_version":"historical-attack-event-air-defense-action-v2",
       "normalization_version":"historical-attack-event-observation-v2"}}
  for row,dr,cref in related:
   made=prod["_source_row"](row,classification_key=key,origin=origin)
   src={k:norm(v) for k,v in made.items() if k not in
     {"origin_git_ref","origin_git_blob_sha","origin_provenance",
      "origin_provenance_sha256","origin_artifact_path","raw_object_path"}}
   src["classification_key"]=key
   src["decision_ref"]=dr
   src["candidate_input_ref"]=cref
   outcome["sources"].append(src)
 need(observed_membership==1559 and comps==3,
      "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"membership":observed_membership,"composed":comps})
 outcome["classifications"].sort(key=lambda x:x["classification_key"])
 outcome["events"].sort(key=lambda x:x["attack_event_key"])
 outcome["sources"].sort(key=lambda x:x["source_link_key"])
 ck=[x["classification_key"] for x in outcome["classifications"]]
 ek=[x["attack_event_key"] for x in outcome["events"]]
 sk=[x["source_link_key"] for x in outcome["sources"]]
 need(len(ck)==len(set(ck))==1713 and len(ek)==len(set(ek))==10 and
      len(sk)==len(set(sk))==1559,
      "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",
      {"classifications":len(ck),"distinct_classification_keys":len(set(ck)),
       "events":len(ek),"distinct_event_keys":len(set(ek)),
       "sources":len(sk),"distinct_source_keys":len(set(sk))})
 actual=Counter(x["verdict"] for x in outcome["classifications"])
 need(dict(actual)==DIST,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",{"distribution":dict(actual)})
 need(all(x["classification_key"] in set(ck) for x in outcome["sources"]),
      "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","orphan source")
 need(Counter(x["classification_key"] for x in outcome["sources"])==
      Counter({x["classification_key"]:sum(1 for y in outcome["sources"] if y["classification_key"]==x["classification_key"])
               for x in outcome["classifications"] if any(y["classification_key"]==x["classification_key"] for y in outcome["sources"])}),
      "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","source membership count")
 report["offline_projection"]={"targets":1713,"repaired_membership_occurrences":1559,
    "affected_source_episodes":370,"recovered_decision_refs_used":1418,
    "projected_classifications":len(ck),"projected_positive_events":len(ek),
    "projected_source_links":len(sk),"verdict_distribution":dict(actual),
    "distinct_classification_keys":len(set(ck)),"distinct_attack_event_keys":len(set(ek)),
    "distinct_source_link_keys":len(set(sk)),"semantic_mismatches":0,
    "canonical_payload_sha256":hobj(hashrows),"composed_strict_episodes":comps}
 return outcome
def offline(report):
 rec,adapter=preflight(report)
 resulta=build_once(report,"A",rec,adapter)
 hashes_a={k:hobj(resulta[k]) for k in ("classifications","events","sources")}
 hashes_a["complete"]=hobj(resulta)
 # Do not share mutable decoded objects across the two independent builds.
 del resulta
 resultb=build_once(report,"B",rec,adapter)
 hashes_b={k:hobj(resultb[k]) for k in ("classifications","events","sources")}
 hashes_b["complete"]=hobj(resultb)
 report["offline_projection"]["run_a_hashes"]=hashes_a
 report["offline_projection"]["run_b_hashes"]=hashes_b
 need(hashes_a==hashes_b,"UNIT_A_A4_PROJECTION_NONDETERMINISTIC",
      {"a":hashes_a,"b":hashes_b})
 report["phase_reached"]="OFFLINE_GATE_PASS"
 report["A4_OFFLINE_PROJECTION_GATE"]="PASS"
 report["A4_CANONICAL_PROJECTION_GATE"]="PASS"
 TEMP.write_bytes(canon(resultb))
 report["offline_projection"]["temp_projection_sha256"]=sha(TEMP.read_bytes())
 save(report)
 print("A4_OFFLINE_PROJECTION_GATE=PASS")
 print("RUN_A_COMPLETE_PROJECTION_SHA256="+hashes_a["complete"])
 print("RUN_B_COMPLETE_PROJECTION_SHA256="+hashes_b["complete"])

if __name__=="__main__":
 report=init()
 try:
  mode=sys.argv[1]
  if mode=="--offline":offline(report)
  else:raise Blocked("UNIT_A_A4_UNSUPPORTED_MODE",mode)
 except Blocked as exc:fail_report(report,exc)
 except Exception as exc:
  fail_report(report,Blocked("UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT",
       {"unexpected_error":type(exc).__name__,"message":str(exc)[:300],
        "traceback":traceback.format_exc(limit=3)[-500:]}))
