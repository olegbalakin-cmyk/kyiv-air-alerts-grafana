#!/usr/bin/env python3
"""Offline, target-only, fail-closed Unit A persistence-payload replay proof."""
from __future__ import annotations
import base64, collections, copy, hashlib, importlib.util, io, json, os, pathlib
import socket, subprocess, sys, tempfile, traceback, urllib.error, urllib.parse
import urllib.request, zipfile

BASE="0a805ced391a15f73e542948ea387e3469c169d6"
BRANCH="attack-event-unit-a-bounded-payload-replay-schema-repair-2026-10-09"
REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
OUT=pathlib.Path("research/attack_event_unit_a_bounded_persistence_payload_replay_schema_repair_2026-10-09.json")
PIN="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASS="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASS_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
RECOVERY="research/attack_event_unit_a_frozen_persistence_payload_recovery_2026-10-09.json"
A3="research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
R3="research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
A1="research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
CONTEXT="research/attack_event_unit_a_frozen_classifier_context_2026-10-08.json"
A3_HARNESS=".github/proof/attack_event_unit_a_bounded_classification_replay.py"
REC_HARNESS=".github/proof/attack_event_unit_a_frozen_persistence_payload_recovery.py"
SIX=("air_defense_context","candidate_evidence","controlled_blast_event_segments",
     "sensitivity_basis","single_episode_day_inference","strict_explosion_evidence")
REQUIRED=("exact_city","strict_explosion","event_types","air_defense_context",
 "air_defense_action","interception_claim","air_military_context","same_attack_context",
 "temporal_binding","single_episode_day_inference","controlled_blast_event_segments",
 "sensitivity_basis","classification_episode_id","candidate_evidence","review_provenance_adapter")
PREVIOUS="research/attack_event_unit_a_bounded_persistence_payload_replay_proof_2026-10-09.json"
PREVIOUS_BLOB="c022e0f0bfccaab695915bda8d5681e71e181a22"
PREVIOUS_SHA="7c73daa1bddffc790ee8c4122e31ea9329ba328bea557250270d18159d37354c"
TARGET_SHA="fec07dca09c6eeb025075dd563723dd0f29b1221e7422c19af7540a3f28facbd"
OCC_SHA="c1393fc2cfc167323a8ff2031201ac3810c1197a86d7ff5ab1063def9fa9f1a2"
RECOVERED_SHA="3dd4706afb5b48b874d9fd47b9d8e88e61b3de6f8574a57629b9c51b57cb5f35"
PINS={
 RECOVERY:("76322fa04a2716865c1a1606a7671c46efeb6735","192aa20276c61d3ac7c78c1bc0a47e3bd80cea29781010a24be4473e70c5fa0a"),
 R3:("a53f665c4f4da26f0b0699939c3b165f376da047","a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"),
 A3:("4dfc8aa7132706e2a3a4febd655ffa0a2bd71640","bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"),
 A1:("52e89792352513664428da3a7fcb9b43f79f1ba1","07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"),
 CONTEXT:("a0dbd84c7d121cf6a7891fafd6e5db77c616c6e1","469bbc319a093d2e4a480e196b704d84002de336c4fc4cc137b911272fd22fb1")}
ART_IDS=(11409720392,11409439130,11427321061,11440696210,11440536485,
         11443597941,11443547933,11471249955,11472455779,11476218067,
         11477885872,11477267777,11569182533,11569177605)
MAX_ZIP=140_000_000
MAX_FILE=140_000_000
class Blocked(Exception):
 def __init__(self,code,detail=""):
  super().__init__(str(code)+":"+str(detail))
  self.code=code
  self.detail=str(detail)[:360]
def fail(code,detail=""): raise Blocked(code,detail)
def sh(*args):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode:fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","git command failed "+repr(args)+" "+p.stderr.decode(errors="replace")[-220:])
 return p.stdout
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canon(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def hobj(o):return sha(canon(o))
def load(path):return json.loads(pathlib.Path(path).read_bytes())
def getjson(data):return json.loads(data.decode("utf-8"))
def pin(commit,path,blob,file_sha=None):
 got=sh("git","rev-parse",commit+":"+path).decode().strip()
 if got!=blob:fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","blob mismatch "+path)
 if file_sha and sha(pathlib.Path(path).read_bytes())!=file_sha:
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","file SHA mismatch "+path)
def module_from_git(commit,path,name,tmp):
 data=sh("git","show",commit+":"+path)
 p=pathlib.Path(tmp)/(name+".py")
 p.write_bytes(data)
 spec=importlib.util.spec_from_file_location(name,p)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod
def initialize():
 return {
  "schema_version":1,
  "kind":"attack_event_unit_a_bounded_persistence_payload_replay_proof",
  "verdict":"ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = BLOCKED",
  "A4_PAYLOAD_REPLAY_GATE":"FAIL",
  "BOUNDED_PAYLOAD_REPLAY_REQUIRED":"UNPROVEN",
  "BOUNDED_PAYLOAD_REPLAY_PROVEN_SAFE":"NO",
  "branch":BRANCH,"base_commit":BASE,
  "first_failing_gate":None,
  "FROZEN_SOURCE_EXHAUSTION_GATE":"UNPROVEN",
  "frozen_refs":{"recovery":PINS[RECOVERY],"original_a3":PINS[A3],
    "repaired_a3":PINS[R3],"a1":PINS[A1],"context":PINS[CONTEXT],
    "classifier_commit":PIN,"classifier_blob":CLASS_BLOB,
    "a3_harness_commit":"1422e8482303ec9262647ca55fef753a9aa2b3ea",
    "a3_harness_blob":"f72f08336f1ebebcc766841f7baf73d196ed092a"},
  "frozen_source_exhaustion":{"expected_artifacts":14,"successfully_downloaded":0,
    "artifacts_with_any_six_fields":0,"artifacts_with_usable_exact_decision_state":0,
    "results":[],"unparseable_field_bearing_files":[]},
  "targets":{"repaired_membership_occurrences":0,"affected_episodes":0,
    "unique_decision_refs":0,"target_set_sha256":None,
    "occurrence_to_decision_coverage_sha256":None},
  "input_reconstruction":{"exact_target_inputs":0,"missing_inputs":0,
    "ambiguous_inputs":0,"frozen_matching_objects":0},
  "parity":{"replayed_decisions_compared":0,"existing_a3_field_comparisons":0,
    "existing_a3_semantic_mismatches":0,"proposed_outcome_mismatches":0,
    "reason_code_mismatches":0,"event_type_mismatches":0,
    "temporal_binding_mismatches":0,"review_provenance_mismatches":0},
  "per_field_recovery_coverage":{k:{"unique_decision_coverage":0,
    "occurrence_coverage":0,"run_a_b_mismatches":0} for k in SIX},
  "persistence_evidence":{"payloads_constructable":0,
    "missing_required_keys":0,"construction_failures":0,"occurrence_coverage_sha256":None},
  "determinism":{"run_a_recovered_payload_sha256":None,
    "run_b_recovered_payload_sha256":None,"semantic_mismatches":0},
  "safety":{"classifier_executions_run_a":0,"classifier_executions_run_b":0,
    "classifier_executions_total":0,"matching_executions":0,
    "composition_executions":0,"discovery_executions":0,
    "public_evidence_requests":0,"github_artifact_downloads":0,
    "neon_queries":0,"db_connections":0,"db_queries":0,"db_writes":0,
    "a4_resumed":False,"a5_executed":False,"production_mutation":"NO",
    "unit_b_executions":0,"unit_c_executions":0},
  "predecessor":{"artifact_identity_verified":"NO","frozen_source_exhaustion_accepted":"NO"},
  "recovered_decision_map":{},
  "smallest_deterministic_blocker_example":None,
  "original_a3_usable_unchanged":True}
def accept_predecessor(out):
 pin(BASE,PREVIOUS,PREVIOUS_BLOB,PREVIOUS_SHA)
 x=load(PREVIOUS)
 t=x.get("targets",{});f=x.get("frozen_source_exhaustion",{});d=x.get("determinism",{})
 if (x.get("verdict")!="ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = BLOCKED"
  or x.get("first_failing_gate")!="UNIT_A_REPLAYED_PERSISTENCE_PAYLOAD_NOT_REPRESENTABLE"
  or x.get("FROZEN_SOURCE_EXHAUSTION_GATE")!="PASS"
  or x.get("BOUNDED_PAYLOAD_REPLAY_REQUIRED")!="YES"
  or (t.get("unique_decision_refs"),t.get("repaired_membership_occurrences"),t.get("affected_episodes"))!=(1418,1559,370)
  or t.get("target_set_sha256")!=TARGET_SHA or t.get("occurrence_to_decision_coverage_sha256")!=OCC_SHA
  or x.get("input_reconstruction")!={"ambiguous_inputs":0,"exact_target_inputs":1418,"frozen_matching_objects":1418,"missing_inputs":0}
  or x.get("parity")!={"event_type_mismatches":0,"existing_a3_field_comparisons":17016,"existing_a3_semantic_mismatches":0,"proposed_outcome_mismatches":0,"reason_code_mismatches":0,"replayed_decisions_compared":1418,"review_provenance_mismatches":0,"temporal_binding_mismatches":0}
  or d.get("run_a_recovered_payload_sha256")!=RECOVERED_SHA or d.get("run_b_recovered_payload_sha256")!=RECOVERED_SHA or d.get("semantic_mismatches")!=0
  or f.get("successfully_downloaded")!=14 or f.get("artifacts_with_any_six_fields")!=0 or f.get("artifacts_with_usable_exact_decision_state")!=0
  or x.get("persistence_evidence",{}).get("missing_required_keys")!=4677 or x.get("persistence_evidence",{}).get("construction_failures")!=1559):
  fail("UNIT_A_SCHEMA_REPAIR_PREDECESSOR_DRIFT","frozen predecessor disagrees")
 for k in SIX:
  if x.get("per_field_recovery_coverage",{}).get(k)!={"unique_decision_coverage":1418,"occurrence_coverage":1559,"run_a_b_mismatches":0}:
   fail("UNIT_A_SCHEMA_REPAIR_PREDECESSOR_DRIFT",k)
 out["predecessor"]={"artifact_identity_verified":"YES","frozen_source_exhaustion_accepted":"YES","final_head":BASE,"artifact_blob":PREVIOUS_BLOB,"artifact_sha256":PREVIOUS_SHA}
 out["frozen_source_exhaustion"]=f;out["FROZEN_SOURCE_EXHAUSTION_GATE"]="PASS"
 out["BOUNDED_PAYLOAD_REPLAY_REQUIRED"]="YES"
def prepare_targets(out,recmod,a3mod,a3,r3,a1,ctx):
 corpus,meta=a3mod.decode_materialization(a1)
 if meta["uncompressed_sha256"]!="9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073":
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","decoded A1 corpus SHA")
 rows,store,metrics=a3mod.reconstruct_materialization(corpus)
 if len(rows)!=1713 or len(store)!=3347 or not metrics["decoded_schema_pass"] or any(
   metrics[k] for k in ("candidate_store_duplicate_keys","candidate_store_hash_mismatches",
    "candidate_ref_failures","materialized_input_hash_mismatches",
    "unaccepted_empty_candidate_sets")):
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","A1 original reconstruction integrity")
 byref={k:v.get("candidate_id") for k,v in store.items()}
 buildout={"recovery_target_counts":{},
  "persistence_payload_construction":{},
  "smallest_deterministic_blocker_example":None}
 try:occ,bydr,ds=recmod.targets_build(buildout,r3,a3,byref)
 except Exception as exc:fail("UNIT_A_BOUNDED_REPLAY_TARGET_SET_DRIFT",str(exc))
 if len(occ)!=1559 or len(bydr)!=1418 or len({x["alert_episode_uid"] for x in occ})!=370:
  fail("UNIT_A_BOUNDED_REPLAY_TARGET_SET_DRIFT","1,559/1,418/370 mismatch")
 out["targets"]={"repaired_membership_occurrences":len(occ),
  "affected_episodes":len({x["alert_episode_uid"] for x in occ}),
  "unique_decision_refs":len(bydr),"target_set_sha256":hobj(sorted(bydr)),
  "occurrence_to_decision_coverage_sha256":hobj(occ)}
 out["smallest_deterministic_blocker_example"]=buildout["smallest_deterministic_blocker_example"]
 raw,ctxrows,bycity=a3mod.prepare_context(ctx)
 if len(ctxrows)!=28480:fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","context not 28,480")
 rowbyuid={str(row.get("alert_episode_uid")):row for row in rows}
 missing=0;ambiguous=0;matching=0
 for dr,t in sorted(bydr.items()):
  cref=t["candidate_input_ref"]
  candidate=store.get(cref)
  if not isinstance(candidate,dict) or candidate.get("candidate_id")!=t["candidate_id"]:
   missing+=1;continue
  if sha(a3mod.canonical_bytes(candidate))!=cref:
   missing+=1;continue
  frozen=ds.get(dr)
  if not isinstance(frozen,dict) or "matching" not in frozen or not isinstance(frozen["matching"],dict):
   fail("UNIT_A_BOUNDED_REPLAY_MATCHING_INPUT_MISSING",dr)
  matching+=1
  origin=rowbyuid.get(t["alert_episode_uid"])
  ci=(origin or {}).get("classifier_episode_input") or {}
  if (ci.get("city_key")!=t["city_key"] or ci.get("episode_id")!=t["episode_id"] or
      cref not in ((origin or {}).get("candidate_input_refs") or [])):
   ambiguous+=1;continue
  contextrows=bycity.get(t["city_key"]) or []
  matching_target=[r for r in contextrows if str(r.get("episode_id") or "")==t["episode_id"]]
  if len(matching_target)!=1:ambiguous+=1
  if hobj({"candidate_ref":cref,"decision":frozen})!=dr:
   fail("UNIT_A_BOUNDED_REPLAY_TARGET_SET_DRIFT","frozen A3 decision ref hash "+dr)
 out["input_reconstruction"]={"exact_target_inputs":len(bydr)-missing-ambiguous,
    "missing_inputs":missing,"ambiguous_inputs":ambiguous,
    "frozen_matching_objects":matching}
 if missing:fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN",str(missing)+" candidate inputs missing")
 if ambiguous:fail("UNIT_A_BOUNDED_REPLAY_INPUT_AMBIGUOUS",str(ambiguous)+" input/context mappings")
 if matching!=1418:fail("UNIT_A_BOUNDED_REPLAY_MATCHING_INPUT_MISSING",str(matching))
 return occ,bydr,ds,store,ctx,a3mod,recmod
def one_run(out,label,bydr,store,ctxdoc,a3mod,ds,worktree):
 script=pathlib.Path(worktree)/CLASS
 mon=a3mod.import_file(script,"unit_a_pinned_monitor_"+label.lower())
 _,_,bycity=a3mod.prepare_context(copy.deepcopy(ctxdoc))
 recovered={}
 p=out["parity"];s=out["safety"]
 counter="classifier_executions_run_"+label.lower()
 forbids={"match_candidate_to_episodes":"matching_executions",
 "compose_episode_candidates":"composition_executions",
 "apply_episode_composition":"composition_executions"}
 def count_calls(frame,event,arg):
  if event=="call" and frame.f_code.co_name in forbids:
   s[forbids[frame.f_code.co_name]]+=1
 try:
  sys.setprofile(count_calls)
  for dr in sorted(bydr):
   t=bydr[dr]
   frozen=ds[dr]
   candidate=copy.deepcopy(store[t["candidate_input_ref"]])
   matching=copy.deepcopy(frozen["matching"])
   episodes=bycity[t["city_key"]]
   s[counter]+=1
   s["classifier_executions_total"]+=1
   decision=mon.classify_candidate(candidate,t["city_key"],episodes,matching)
   if not isinstance(decision,dict):
    fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_INCOMPLETE",dr+" classifier returned non-object")
   if label=="A":
    projected=a3mod.decision_projection(decision)
    p["replayed_decisions_compared"]+=1
    for k,old in frozen.items():
     p["existing_a3_field_comparisons"]+=1
     if k not in projected or old!=projected[k]:
      p["existing_a3_semantic_mismatches"]+=1
      special={"proposed_outcome":"proposed_outcome_mismatches",
       "reason_codes":"reason_code_mismatches","event_types":"event_type_mismatches",
       "temporal_binding":"temporal_binding_mismatches",
       "review_provenance_adapter":"review_provenance_mismatches"}
      if k in special:p[special[k]]+=1
    if p["existing_a3_semantic_mismatches"]:
     fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_SEMANTIC_DRIFT",
          "first mismatching decision_ref="+dr)
   missing=[key for key in SIX if key not in decision]
   if missing:fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_INCOMPLETE",
                    "decision_ref="+dr+" missing "+",".join(missing))
   recovered[dr]={key:copy.deepcopy(decision[key]) for key in SIX}
 finally:sys.setprofile(None)
 return recovered
def prove(out):
 if os.environ.get("GITHUB_REF_NAME")!=BRANCH:
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","wrong Actions branch")
 if sh("git","merge-base","HEAD",BASE).decode().strip()!=BASE:
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","base ancestry mismatch")
 if sys.version_info[:2]!=(3,12):
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","Python is not 3.12")
 if os.environ.get("DATABASE_URL") or os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL"):
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","database environment exposed")
 accept_predecessor(out)
 for path,(blob,filesha) in PINS.items():pin("HEAD",path,blob,filesha)
 pin(PIN,CLASS,CLASS_BLOB)
 pin("1422e8482303ec9262647ca55fef753a9aa2b3ea",
      A3_HARNESS,"f72f08336f1ebebcc766841f7baf73d196ed092a")
 pin("41ee8d160c34145b9d9a51b9da095084cf342824",
      REC_HARNESS,"1d0541bef22ced23c0028eda516cc6d13c55b869")
 rec=load(RECOVERY)
 if (rec.get("verdict")!="ATTACK-EVENT UNIT A FROZEN PERSISTENCE PAYLOAD RECOVERY = BLOCKED"
    or rec.get("A4_PAYLOAD_RECOVERY_GATE")!="FAIL"
    or rec.get("recovery_target_counts",{}).get("unique_relevant_decision_refs")!=1418
    or rec.get("BOUNDED_PAYLOAD_REPLAY_REQUIRED")!="UNPROVEN"):
  fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","predecessor recovery verdict drift")
 a3=load(A3);r3=load(R3);a1=load(A1);ctx=load(CONTEXT)
 with tempfile.TemporaryDirectory(prefix="unit_a_payload_sources_") as tmp:
  recmod=module_from_git("41ee8d160c34145b9d9a51b9da095084cf342824",
    REC_HARNESS,"accepted_recovery",tmp)
  a3mod=module_from_git("1422e8482303ec9262647ca55fef753a9aa2b3ea",
    A3_HARNESS,"accepted_a3_input",tmp)
  occ,bydr,ds,store,ctxdoc,a3mod,recmod=prepare_targets(out,recmod,a3mod,a3,r3,a1,ctx)
  # No artifact downloads: predecessor already proves frozen-source exhaustion.
  import requests,bs4
  versions=a3.get("execution_environment") or {}
  import importlib.metadata
  if (importlib.metadata.version("requests")!=str(versions.get("resolved_requests_version"))
       or importlib.metadata.version("beautifulsoup4")!=str(versions.get("resolved_beautifulsoup4_version"))):
   fail("UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN","A3 dependency runtime version drift")
  pin(PIN,"kyiv-air-alerts-grafana/requirements.txt",
      "d7a2ff05af67cda88e4930d238f0282ca557a963")
  worktree=pathlib.Path(tmp)/"pinned"
  sh("git","worktree","add","--detach",str(worktree),PIN)
  try:
   sys.path.insert(0,str(worktree/"kyiv-air-alerts-grafana"/"scripts"))
   sys.path.insert(0,str(worktree/"kyiv-air-alerts-grafana"))
   # Original accepted A3 guard: network denied before pinned module import/replay.
   a3mod.block_network()
   runa=one_run(out,"A",bydr,store,ctxdoc,a3mod,ds,worktree)
   runb=one_run(out,"B",bydr,store,ctxdoc,a3mod,ds,worktree)
  finally:
   sh("git","worktree","remove","--force",str(worktree))
  if out["parity"]!={"event_type_mismatches":0,"existing_a3_field_comparisons":17016,"existing_a3_semantic_mismatches":0,"proposed_outcome_mismatches":0,"reason_code_mismatches":0,"replayed_decisions_compared":1418,"review_provenance_mismatches":0,"temporal_binding_mismatches":0}:
   fail("UNIT_A_SCHEMA_REPAIR_REPLAY_PARITY_DRIFT","A3 replay parity")
  runasha=hobj(runa);runbsha=hobj(runb)
  out["determinism"]["run_a_recovered_payload_sha256"]=runasha
  out["determinism"]["run_b_recovered_payload_sha256"]=runbsha
  mismatch=0
  for dr in sorted(bydr):
   for field in SIX:
    if runa[dr][field]!=runb[dr][field]:
     mismatch+=1
     out["per_field_recovery_coverage"][field]["run_a_b_mismatches"]+=1
  out["determinism"]["semantic_mismatches"]=mismatch
  if mismatch or runasha!=runbsha:
   fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_NONDETERMINISTIC","RUN A/B six-field mismatch")
  if runasha!=RECOVERED_SHA or runbsha!=RECOVERED_SHA:
   fail("UNIT_A_SCHEMA_REPAIR_RECOVERED_VALUE_DRIFT","recovered hash")
  for field in SIX:
   n=sum(field in runa[d] and field in runb[d] for d in bydr)
   c=sum(field in runa[t["decision_ref"]] for t in occ)
   out["per_field_recovery_coverage"][field]["unique_decision_coverage"]=n
   out["per_field_recovery_coverage"][field]["occurrence_coverage"]=c
   if n!=1418 or c!=1559:
    fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_INCOMPLETE",field)
  fmt=recmod.payload_formatter()
  hashes=[];missingkeys=0;extra_keys=0;failures=0;mapping=0
  for occurrence in occ:
   dr=occurrence["decision_ref"]
   combined={**copy.deepcopy(ds[dr]),**copy.deepcopy(runa[dr])}
   try:
    pl=fmt(combined)
    if not isinstance(pl,dict):
     failures+=1;continue
    missing=set(REQUIRED)-set(pl);extra=set(pl)-set(REQUIRED)
    missingkeys+=len(missing);extra_keys+=len(extra)
    if missing or extra:
     failures+=1;continue
    expected={"exact_city":combined["exact_city_classification_evidence"],
     "strict_explosion":combined["strict_explosion_evidence"],
     "event_types":list(combined.get("event_types") or []),
     "air_defense_context":bool(combined.get("air_defense_context")),
     "air_defense_action":bool(combined.get("air_defense_action")),
     "interception_claim":bool(combined.get("interception_claim")),
     "air_military_context":combined["air_military_context"],
     "same_attack_context":combined["same_attack_context"],
     "temporal_binding":combined["temporal_binding"],
     "single_episode_day_inference":combined["single_episode_day_inference"],
     "controlled_blast_event_segments":combined["controlled_blast_event_segments"],
     "sensitivity_basis":combined["sensitivity_basis"],
     "classification_episode_id":combined["proposed_matched_episode_id"],
     "candidate_evidence":combined.get("candidate_evidence") or {},
     "review_provenance_adapter":combined.get("review_provenance_adapter") or {}}
    if pl!=expected:
     mapping+=1;failures+=1;continue
    hashes.append({"occurrence":occurrence,"evidence_sha256":hobj(pl)})
   except Exception:
    failures+=1
  out["persistence_evidence"]={"canonical_output_schema":list(REQUIRED),
   "canonical_output_key_count":15,"payloads_constructable":len(hashes),
   "missing_required_keys":missingkeys,"unexpected_output_schema_keys":extra_keys,
   "formatter_semantic_mapping_mismatches":mapping,"construction_failures":failures,
   "occurrence_coverage_sha256":hobj(hashes),"payloads_sha256":hobj(hashes)}
  if missingkeys or extra_keys:fail("UNIT_A_PERSISTENCE_PAYLOAD_OUTPUT_SCHEMA_DRIFT",str(missingkeys)+" / "+str(extra_keys))
  if mapping:fail("UNIT_A_PERSISTENCE_PAYLOAD_FORMATTER_MAPPING_DRIFT",str(mapping))
  if failures or len(hashes)!=1559:fail("UNIT_A_REPLAYED_PERSISTENCE_PAYLOAD_NOT_REPRESENTABLE",str(failures))
  distribution=collections.Counter(row.get("verdict") for row in r3.get("episode_results",[]))
  wanted={"STRICT_EVENT_POSITIVE":9,"SENSITIVITY_EVENT_POSITIVE":1,
    "NEEDS_REVIEW":356,"NO_CONFIRMED_EVENT":1347}
  if dict(distribution)!=wanted:
   fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_SEMANTIC_DRIFT",
        "frozen repaired A3 distribution differs")
  s=out["safety"]
  if (s["classifier_executions_run_a"]!=1418 or s["classifier_executions_run_b"]!=1418
     or s["classifier_executions_total"]!=2836 or s["matching_executions"]
     or s["composition_executions"] or s["discovery_executions"]):
   fail("UNIT_A_BOUNDED_PAYLOAD_REPLAY_INCOMPLETE","safety counters")
  if out["targets"]["target_set_sha256"]!=TARGET_SHA or out["targets"]["occurrence_to_decision_coverage_sha256"]!=OCC_SHA:
   fail("UNIT_A_SCHEMA_REPAIR_TARGET_SET_DRIFT","target hashes")
  out["occurrence_coverage"]={"mapped_occurrences":len(occ),"unmapped_occurrences":0,
   "affected_episodes":370,"occurrence_to_decision_coverage_sha256":OCC_SHA,
   "occurrences":[{"alert_episode_uid":x["alert_episode_uid"],"decision_ref":x["decision_ref"],"candidate_id":x["candidate_id"]} for x in occ]}
  out["recovered_decision_map"]={
   dr:{"decision_ref":dr,"candidate_input_ref":bydr[dr]["candidate_input_ref"],
       "candidate_id":bydr[dr]["candidate_id"],"city_key":bydr[dr]["city_key"],
       "recovered_fields":runa[dr],
       "recovered_fields_canonical_sha256":hobj(runa[dr]),
       "frozen_a3_parity_status":"EXACT_MATCH",
       "run_a_b_equality_status":"EQUAL"} for dr in sorted(bydr)}
  out["recovered_map_summary"]={"decision_entries_frozen":len(out["recovered_decision_map"]),"unmapped_decisions":1418-len(out["recovered_decision_map"])}
  out["verdict"]="ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = PROVEN"
  out["A4_PAYLOAD_REPLAY_GATE"]="PASS"
  out["BOUNDED_PAYLOAD_REPLAY_PROVEN_SAFE"]="YES"
  out["first_failing_gate"]=None
def main():
 out=initialize()
 try:prove(out)
 except Blocked as exc:
  out["first_failing_gate"]=exc.code
  out["bounded_blocker_detail"]=exc.detail
  if out["verdict"].endswith("NOT REQUIRED"):
   out["A4_PAYLOAD_REPLAY_GATE"]="FROZEN_SOURCE_FOUND"
  else:
   out["verdict"]="ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = BLOCKED"
   out["A4_PAYLOAD_REPLAY_GATE"]="FAIL"
   if out["FROZEN_SOURCE_EXHAUSTION_GATE"]=="UNPROVEN":
    out["FROZEN_SOURCE_EXHAUSTION_GATE"]="BLOCKED"
 except Exception as exc:
  # An unanticipated harness/runtime exception must be frozen as BLOCKED, never PASS.
  out["verdict"]="ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = BLOCKED"
  out["first_failing_gate"]="UNIT_A_BOUNDED_REPLAY_INPUT_LINEAGE_UNPROVEN"
  out["bounded_blocker_detail"]=type(exc).__name__+":"+str(exc)[:300]
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_bytes(canon(out)+b"\n")
 for key in ("verdict","A4_PAYLOAD_REPLAY_GATE","BOUNDED_PAYLOAD_REPLAY_REQUIRED",
  "BOUNDED_PAYLOAD_REPLAY_PROVEN_SAFE","FROZEN_SOURCE_EXHAUSTION_GATE",
  "first_failing_gate"):
  print(str(key)+"="+str(out.get(key)))
 print("ACTIONS_ARTIFACTS_DOWNLOADED_THIS_RUN="+str(out["safety"]["github_artifact_downloads"]))
 print("TARGETS="+json.dumps(out["targets"],sort_keys=True))
 print("INPUTS="+json.dumps(out["input_reconstruction"],sort_keys=True))
 print("PARITY="+json.dumps(out["parity"],sort_keys=True))
 print("FIELD_COVERAGE="+json.dumps(out["per_field_recovery_coverage"],sort_keys=True))
 print("DETERMINISM="+json.dumps(out["determinism"],sort_keys=True))
 print("PERSISTENCE="+json.dumps(out["persistence_evidence"],sort_keys=True))
 print("SAFETY="+json.dumps(out["safety"],sort_keys=True))
 print("PROOF_SHA256="+sha(OUT.read_bytes()))
 return 0
if __name__=="__main__":raise SystemExit(main())
