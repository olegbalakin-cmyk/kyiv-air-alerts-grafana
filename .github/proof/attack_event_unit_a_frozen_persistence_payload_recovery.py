#!/usr/bin/env python3
"""Immutable Unit A decision-field recovery. Never executes classification/matching/composition."""
from __future__ import annotations
import ast
import base64
import collections
import copy
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
BASE="510b9afcf48d1644cdd9af0c7a135d8f59afd486"
BRANCH="attack-event-unit-a-frozen-persistence-payload-recovery-2026-10-09"
OUT=Path("research/attack_event_unit_a_frozen_persistence_payload_recovery_2026-10-09.json")
A4="research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2_2026-10-09.json"
A3="research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
R3="research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
A1="research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
ID="research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json"
CLASS_COMMIT="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASS_PATH="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
A3_HARNESS_COMMIT="1422e8482303ec9262647ca55fef753a9aa2b3ea"
A3_HARNESS_PATH=".github/proof/attack_event_unit_a_bounded_classification_replay.py"
MISSING=("air_defense_context","candidate_evidence","controlled_blast_event_segments",
         "sensitivity_basis","single_episode_day_inference","strict_explosion_evidence")
PRESERVED=("air_defense_action","air_military_context","event_types",
    "exact_city_classification_evidence","interception_claim","matching",
    "proposed_matched_episode_id","proposed_outcome","reason_codes",
    "review_provenance_adapter","same_attack_context","temporal_binding")
PAYLOAD_REQUIRED=("exact_city_classification_evidence","strict_explosion_evidence",
    "event_types","air_defense_context","air_defense_action","interception_claim",
    "air_military_context","same_attack_context","temporal_binding",
    "single_episode_day_inference","controlled_blast_event_segments",
    "sensitivity_basis","proposed_matched_episode_id","candidate_evidence",
    "review_provenance_adapter")
PINNED={
 A4:("9085ae4fdf2444952fdf251de0e3817d8a38f0c6",
     "d2183293a90cf7a9d3ed91e6cfa0f6b61f724e893ca4bdb70391ad71abb88f24"),
 R3:("a53f665c4f4da26f0b0699939c3b165f376da047",
     "a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"),
 A3:("4dfc8aa7132706e2a3a4febd655ffa0a2bd71640",
     "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"),
 A1:("52e89792352513664428da3a7fcb9b43f79f1ba1",
     "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"),
 ID:("a7e6b992180bfef3dd640fcd9ef8eec8a6436af7",
     "568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891")
}
RUNS=[37580048895,37812185277,37820792820,37894884544,
      37906762208,37916228047,37917554992,37921615802,37936840809]
HEX40=re.compile(r"^[a-f0-9]{40}$")
HEX64=re.compile(r"^[a-f0-9]{64}$")
RUN_URL="https://api.github.com/repos/"+REPO+"/actions/"
CATEGORY=("EXACT_FULL_DECISION_SOURCE","PARTIAL_DECISION_SOURCE",
          "QUEUE_STATE_WITH_EXACT_DECISION_LINEAGE","QUEUE_STATE_WITHOUT_DECISION_LINEAGE",
          "UNRELATED_CLASSIFIER_OUTPUT","CURRENT_RECOMPUTED_STATE","UNUSABLE_LINEAGE")
MAX_BLOB=140_000_000
MAX_ZIP=140_000_000
SAFETY={
 "classifier_executions":0,"matching_executions":0,"composition_executions":0,
 "discovery_executions":0,"public_evidence_requests":0,
 "neon_queries":0,"db_connections":0,"db_queries":0,"db_writes":0,
 "a4_resumed":False,"a5_executed":False,"production_mutation":"NO",
 "unit_b_executions":0,"unit_c_executions":0
}
class Blocked(Exception):
 def __init__(self,gate,msg):
  super().__init__(msg); self.gate=gate

def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(x):
 return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def hobj(x): return sha(canonical(x))
def cmd(*args,may_fail=False):
 p=subprocess.run(["git",*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
     env=dict(os.environ,GIT_NO_LAZY_FETCH="1",GIT_TERMINAL_PROMPT="0"),check=False)
 if p.returncode and not may_fail:
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT",
          "git failure "+str(args[:3])+" "+p.stderr.decode("utf-8","replace")[-280:])
 return p.stdout if p.returncode==0 else None
def verify_pin(commit,path,blob,filesha=None):
 got=cmd("rev-parse",commit+":"+path).decode().strip()
 if got!=blob: raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","Git blob drift at "+path)
 raw=Path(path).read_bytes() if commit=="HEAD" else cmd("show",commit+":"+path)
 if filesha and sha(raw)!=filesha:
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","SHA drift at "+path)
 return raw
def load(raw): return json.loads(raw.decode("utf-8"))
def compact_source(src):
 return {k:v for k,v in src.items() if k in
   ("origin","path","blob","run_id","artifact_id","artifact_name","file_name","classification","matched_decisions","field_names","status","bytes","source_commit")}
def report_start():
 return {
   "schema_version":1,"kind":"attack_event_unit_a_frozen_persistence_payload_recovery",
   "verdict":"ATTACK-EVENT UNIT A FROZEN PERSISTENCE PAYLOAD RECOVERY = BLOCKED",
   "A4_PAYLOAD_RECOVERY_GATE":"FAIL","base_commit":BASE,"branch":BRANCH,
   "predecessor_identities":{},
   "recovery_target_counts":{"repaired_membership_occurrences":None,"affected_episodes":None,
      "unique_relevant_decision_refs":None},
   "immutable_source_inventory":{"scanned_git_blobs":0,"scanned_git_json_files":0,
      "field_bearing_git_sources":0,"source_roles":{k:0 for k in CATEGORY},
      "sources":[],"skipped_oversized":[],"unreadable_sources":[]},
   "inspected_git_branches":[],"inspected_git_commits":[],"inspected_git_blobs":0,
   "queue_snapshots":{"referenced_commits":0,"scanned":0,"inaccessible":[],"source":"A1 immutable provenance"},
   "actions":{"runs_inspected":[],"artifacts_listed":0,"artifacts_downloaded":0,
       "artifacts_expired_or_inaccessible":[],"scanned_files":0,"discovered_earlier_a3_runs":[]},
   "per_field_recovery_coverage":{},
   "lineage":{"exact_full_decision_sources":0,"partial_decision_sources":0,
      "queue_sources_with_exact_lineage":0,"lineage_failures":0,
      "ambiguous_decisions":0,"conflicting_decisions":0,"bounded_failures":[]},
   "persistence_payload_construction":{"payloads_constructable":0,
      "missing_required_keys":None,"construction_failures":None,
      "occurrence_coverage_sha256":None},
   "recovered_decision_map":None,
   "BOUNDED_PAYLOAD_REPLAY_REQUIRED":"UNPROVEN",
   "determinism":{"run_a_recovery_sha256":None,"run_b_recovery_sha256":None,
      "semantic_mismatches":None},
   "safety":dict(SAFETY),
   "first_failing_gate":None,
   "unrecovered_fields":list(MISSING),"affected_decision_refs":None,
   "affected_occurrences":1559,"affected_episodes":370,
   "smallest_deterministic_blocker_example":None
 }

def preflight(out):
 if os.environ.get("GITHUB_REF_NAME")!=BRANCH: raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","branch")
 if cmd("merge-base","HEAD",BASE).decode().strip()!=BASE:
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","base ancestry")
 for path,(blob,filehash) in PINNED.items():
  verify_pin("HEAD",path,blob,filehash)
  out["predecessor_identities"][path]={"blob":blob,"sha256":filehash}
 verify_pin(CLASS_COMMIT,CLASS_PATH,"778469b74c2aa807d851cf2c2ee35cf4aa785589")
 verify_pin(A3_HARNESS_COMMIT,A3_HARNESS_PATH,"f72f08336f1ebebcc766841f7baf73d196ed092a")
 out["predecessor_identities"][CLASS_PATH]={"commit":CLASS_COMMIT,
   "blob":"778469b74c2aa807d851cf2c2ee35cf4aa785589"}
 a4=load(Path(A4).read_bytes())
 r3=load(Path(R3).read_bytes())
 a3=load(Path(A3).read_bytes())
 ident=load(Path(ID).read_bytes())
 p=a4.get("source_payload_projection_probe") or {}
 safety=a4.get("safety") or {}
 fields=p.get("missing_required_decision_field_counts") or {}
 chk=[
  a4.get("verdict")=="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED",
  a4.get("first_failing_gate")=="UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS",
  a4.get("A5_PERSISTENCE_DELTA_GATE")=="FAIL",
  a4.get("repaired_membership_occurrences")==1559,
  a4.get("source_membership_mismatches")=={"missing":0,"extra":0,"affected_episodes":0},
  p.get("production_related_source_occurrences")==1559,
  p.get("affected_episodes")==370,
  set(fields)==set(MISSING) and all(fields[k]==1559 for k in MISSING),
  a4.get("neon_contacted") is False,
  safety.get("sql_select_count")==0 and safety.get("attempted_db_writes")==0,
  safety.get("actual_db_writes")==0 and safety.get("a5_executions")==0,
  len(r3.get("episode_results") or [])==1713,
  r3.get("counts",{}).get("repaired_membership_occurrences")==1559,
  len(a3.get("episode_results") or [])==1713,
  isinstance(a3.get("candidate_decision_store"),dict),
  a4.get("source_identity_mapping_sha256")=="557bd96a2d5d0f8f337852965cb9ca9ead7c2d947f556c476d04aeffb13d7703",
  isinstance(ident.get("contributor_source_identity_mapping"),list)
 ]
 if not all(chk):
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT",
                "A4/repaired-A3/source-identity accepted facts mismatch, failing="+str([i for i,v in enumerate(chk) if not v]))
 # Independently check pinned projection AST, not execute any classifier function.
 source=cmd("show",A3_HARNESS_COMMIT+":"+A3_HARNESS_PATH).decode("utf-8")
 tree=ast.parse(source)
 fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="decision_projection"),None)
 rr=next((n.value for n in ast.walk(fn) if isinstance(n,ast.Return)),None) if fn else None
 names=([k.value for k in rr.keys] if (isinstance(rr,ast.Dict) and
       all(isinstance(k,ast.Constant) and isinstance(k.value,str) for k in rr.keys)) else [])
 if set(names)!=set(PRESERVED):
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A3 decision_projection AST changed")
 return a4,r3,a3

def decode_a1(out):
 doc=load(Path(A1).read_bytes())
 co=doc.get("corpus") or {}
 if co.get("encoding")!="gzip+base64":
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A1 corpus encoding")
 compressed=base64.b64decode(co["payload_base64"],validate=True)
 if sha(compressed)!=co.get("compressed_sha256"):
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A1 compressed SHA")
 raw=gzip.decompress(compressed)
 if sha(raw)!="9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073":
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A1 corpus SHA")
 corpus=load(raw)
 rows=corpus.get("candidate_input_store") or []
 store={}
 id_by_ref={}
 for row in rows:
  ref=row.get("sha256"); cand=row.get("candidate_input") or {}
  if not ref or ref in store or sha(canonical(cand)+b"\n")!=ref:
   # canonical_bytes in A3 includes a newline; calculate exactly.
   if not ref or ref in store or sha(canonical(cand)+b"\n")!=ref:
    raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A1 store identity invalid")
  store[ref]=cand
  id_by_ref[ref]=cand.get("candidate_id")
 if len(rows)!=3347: raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A1 candidate store count")
 out["predecessor_identities"][A1]["decoded_corpus_sha256"]=sha(raw)
 return doc,corpus,store,id_by_ref

def targets_build(out,r3,a3,id_by_ref):
 dstore=a3["candidate_decision_store"]
 targets=[]
 for e in r3["episode_results"]:
  positions=e.get("target_related_candidate_positions") or []
  drs=e.get("candidate_decision_refs") or []
  crs=e.get("candidate_input_refs") or []
  for i in positions:
   if not isinstance(i,int) or i>=len(drs) or i>=len(crs) or i<0:
    raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","membership index")
   ref=crs[i]; dr=drs[i]
   if dr not in dstore or ref not in id_by_ref:
    raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A3 ref resolution")
   expected=hobj({"candidate_ref":ref,"decision":dstore[dr]})
   if expected!=dr:
    raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","A3 decision-ref hash mismatch")
   targets.append({
    "alert_episode_uid":e["alert_episode_uid"],"episode_id":e["episode_id"],
    "city_key":e["city_key"],"candidate_input_ref":ref,
    "decision_ref":dr,"candidate_id":id_by_ref[ref],
    "observation_id":id_by_ref[ref]
   })
 targets.sort(key=lambda x:(x["alert_episode_uid"],x["decision_ref"],x["candidate_input_ref"]))
 bydr={}
 for t in targets:
  dr=t["decision_ref"]
  if dr in bydr and (bydr[dr]["candidate_input_ref"]!=t["candidate_input_ref"] or
                     bydr[dr]["candidate_id"]!=t["candidate_id"]):
   raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","decision maps to multiple source identities")
  bydr.setdefault(dr,t)
 if len(targets)!=1559 or len({t["alert_episode_uid"] for t in targets})!=370:
  raise Blocked("UNIT_A_PAYLOAD_RECOVERY_INPUT_DRIFT","target occurrence count")
 out["recovery_target_counts"]={"repaired_membership_occurrences":1559,
       "affected_episodes":370,"unique_relevant_decision_refs":len(bydr)}
 out["persistence_payload_construction"]["occurrence_coverage_sha256"]=hobj(targets)
 out["smallest_deterministic_blocker_example"]=next(
      (x for x in targets if x["alert_episode_uid"]=="00073d75-8217-4cbe-a7d8-f75f975c3c3b"),targets[0])
 return targets,bydr,dstore

def snapshot_refs(corpus):
 found=set()
 def walk(x,kcontext="",depth=0):
  if depth>24: return
  if isinstance(x,dict):
   for k,v in x.items():
    key=str(k).lower()
    if (isinstance(v,str) and HEX40.fullmatch(v) and
       ("queue" in key or "snapshot" in key or ("commit" in key and ("queue" in kcontext or "snapshot" in kcontext)))):
     found.add(v)
    elif isinstance(v,list) and ("queue" in key or "snapshot" in key):
     for z in v:
      if isinstance(z,str) and HEX40.fullmatch(z): found.add(z)
    if isinstance(v,(dict,list)): walk(v,key,depth+1)
  elif isinstance(x,list):
   for v in x: walk(v,kcontext,depth+1)
 walk(corpus)
 return sorted(found)

def git_inventory(out,queue_ids):
 branches=cmd("branch","-r","--format=%(refname:short)").decode("utf-8","replace").splitlines()
 out["inspected_git_branches"]=sorted(x for x in branches if x)
 found=[]
 for q in queue_ids:
  if cmd("cat-file","-e",q+"^{commit}",may_fail=True) is None:
   p=subprocess.run(["git","fetch","--no-tags","origin",q],
       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
  if cmd("cat-file","-e",q+"^{commit}",may_fail=True) is None:
   out["queue_snapshots"]["inaccessible"].append(q)
  else: found.append(q)
 out["queue_snapshots"]["scanned"]=len(found)
 out["queue_snapshots"]["referenced_commits"]=len(queue_ids)
 # Enumerate immutable blobs reachable from all fetched refs, including specific queue snapshot commits.
 objects=cmd("rev-list","--objects","--all",*found).decode("utf-8","replace").splitlines()
 allsha={}
 for ln in objects:
  if " " not in ln: continue
  oid,p=ln.split(" ",1)
  if not p: continue
  if p.lower().endswith((".json",".jsonl",".ndjson",".json.gz",".zip",".yaml",".yml")):
   allsha.setdefault(oid,p)
 out["inspected_git_blobs"]=len(allsha)
 out["inspected_git_commits"]=[BASE,CLASS_COMMIT,A3_HARNESS_COMMIT]+found
 return allsha

def raw_git_blob(ref):
 return cmd("cat-file","blob",ref)

class Collector:
 def __init__(self,targets,bydr,dstore):
  self.targets=targets; self.bydr=bydr; self.dstore=dstore
  self.values=collections.defaultdict(lambda:collections.defaultdict(list))
  self.roles=collections.Counter()
  self.sources=[]
  self.lineage_errors=[]
  self.field_bearing=0
  self.matched_sources=collections.Counter()
 def source(self,source,raw):
  if not any(k.encode() in raw for k in MISSING): return
  self.field_bearing+=1
  try:
   docs=[]
   p=source.get("path") or source.get("file_name") or ""
   if p.endswith(".gz"):
    raw=gzip.decompress(raw)
   if p.endswith((".jsonl",".ndjson")):
    for line in raw.splitlines():
     if any(k.encode() in line for k in MISSING):
      try: docs.append(json.loads(line))
      except (json.JSONDecodeError,UnicodeDecodeError): pass
   else:
    docs=[json.loads(raw.decode("utf-8"))]
  except (ValueError,UnicodeDecodeError,OSError,EOFError,MemoryError):
   self.record_source(source,"UNUSABLE_LINEAGE",list(MISSING),0)
   return
  sroles=collections.Counter()
  found_fields=set()
  matches=set()
  for doc in docs:
   for obj,anc in self.walk(doc):
    present=set(MISSING).intersection(obj)
    if not present: continue
    found_fields.update(present)
    matched,role=self.match(obj,anc,source,present)
    sroles[role]+=1
    matches.update(matched)
  if sroles:
   if sroles["EXACT_FULL_DECISION_SOURCE"]:
    role="EXACT_FULL_DECISION_SOURCE"
   elif sroles["PARTIAL_DECISION_SOURCE"]:
    role="PARTIAL_DECISION_SOURCE"
   elif sroles["QUEUE_STATE_WITH_EXACT_DECISION_LINEAGE"]:
    role="QUEUE_STATE_WITH_EXACT_DECISION_LINEAGE"
   elif sroles["QUEUE_STATE_WITHOUT_DECISION_LINEAGE"]:
    role="QUEUE_STATE_WITHOUT_DECISION_LINEAGE"
   else: role=max(sorted(sroles),key=lambda x:sroles[x])
  else: role="UNRELATED_CLASSIFIER_OUTPUT"
  self.record_source(source,role,sorted(found_fields),len(matches))
 def record_source(self,s,role,fields,matched):
  entry={**s,"classification":role,"field_names":fields,"matched_decisions":matched}
  self.roles[role]+=1
  self.sources.append(entry)
 def walk(self,node,anc=(),depth=0):
  if depth>30:return
  if isinstance(node,dict):
   yield node,anc
   for k,v in node.items():
    if isinstance(v,(dict,list)):
     yield from self.walk(v,(node,)+anc,depth+1)
  elif isinstance(node,list):
   for v in node: yield from self.walk(v,anc,depth+1)
 def match(self,node,anc,source,present):
  ancestors=(node,)+anc[:5]
  def pick(*keys):
   for d in ancestors:
    for key in keys:
     v=d.get(key)
     if isinstance(v,str) and v: return v
   return None
  ref=pick("candidate_input_ref","candidate_ref","candidate_input_sha256")
  explicit_dr=pick("decision_ref")
  cid=pick("candidate_id","observation_id")
  city=pick("city_key")
  cls=pick("classifier_blob","classifier_sha","classifier_git_blob")
  method=pick("methodology_version")
  norm=pick("normalization_version")
  # Exact A3 projection identity must be established, not inferred from text or reason codes.
  decision=next((d for d in ancestors if all(k in d for k in PRESERVED)),None)
  if (not decision and isinstance(node.get("decision"),dict) and
     all(k in node["decision"] for k in PRESERVED)):
   decision=node["decision"]
  verified=[]
  if decision is not None and ref:
   projected={k:decision[k] for k in PRESERVED}
   # Reproduce the pure, 12-field frozen A3 decision projection semantics.
   projected["matching"]=decision.get("matching") or {}
   projected["event_types"]=list(decision.get("event_types") or [])
   projected["reason_codes"]=list(decision.get("reason_codes") or [])
   for k in ("temporal_binding","exact_city_classification_evidence",
      "air_military_context","same_attack_context","review_provenance_adapter"):
    projected[k]=decision.get(k) or {}
   for k in ("air_defense_action","interception_claim"):
    projected[k]=bool(decision.get(k))
   inferred=hobj({"candidate_ref":ref,"decision":projected})
   if inferred in self.bydr and self.dstore[inferred]==projected:
    if not explicit_dr or explicit_dr==inferred:
     t=self.bydr[inferred]
     if (not cid or cid==t["candidate_id"]) and (not city or city==t["city_key"]):
      if ((not cls or cls=="778469b74c2aa807d851cf2c2ee35cf4aa785589") and
          (not method or method=="historical-attack-event-air-defense-action-v2") and
          (not norm or norm=="historical-attack-event-observation-v2")):
       verified=[inferred]
  # Explicit matching decision-ref alone is NOT enough: full preserved semantic
  # projection is still required. This is deliberate fail-closed lineage policy.
  if verified:
   for dr in verified:
    for field in present:
     val=node[field]
     self.values[dr][field].append({"value":copy.deepcopy(val),
       "hash":hobj(val),"source":compact_source(source)})
   kind=("QUEUE_STATE_WITH_EXACT_DECISION_LINEAGE" if "queue" in
      str(source.get("path") or source.get("file_name") or "").lower() else (
      "EXACT_FULL_DECISION_SOURCE" if len(present)==len(MISSING) else "PARTIAL_DECISION_SOURCE"))
   self.matched_sources[kind]+=1
   return verified,kind
  if ((cid and any(t["candidate_id"]==cid for t in self.bydr.values())) or
     (ref and any(t["candidate_input_ref"]==ref for t in self.bydr.values())) or
     (explicit_dr and explicit_dr in self.bydr)):
   if len(self.lineage_errors)<12:
    self.lineage_errors.append({"source":compact_source(source),
       "candidate_id":cid,"candidate_input_ref":ref,"decision_ref":explicit_dr,
       "present_fields":sorted(present),"cause":"NO_EXACT_FROZEN_A3_DECISION_PROJECTION"})
   role=("QUEUE_STATE_WITHOUT_DECISION_LINEAGE" if "queue" in
      str(source.get("path") or source.get("file_name") or "").lower() else "UNUSABLE_LINEAGE")
   return [],role
  return [],"UNRELATED_CLASSIFIER_OUTPUT"

def scan_git(out,collector,inventory):
 seen=set()
 for blob,path in sorted(((b,p) for b,p in inventory.items()),key=lambda x:(x[1],x[0])):
  lower=path.lower()
  if not any(z in lower for z in ("attack","event","classif","evidence","persist","backfill",
       "queue","candidate","unit_a","recovery","source","historical","23city","18city","5city")):
   continue
  if blob in seen:continue
  seen.add(blob)
  # Fetch only immutable JSON data, not scripts or public evidence.
  try:
   size=int(cmd("cat-file","-s",blob).decode().strip())
   if size>MAX_BLOB:
    out["immutable_source_inventory"]["skipped_oversized"].append(
       {"path":path,"blob":blob,"bytes":size})
    continue
   if not (lower.endswith((".json",".jsonl",".ndjson",".json.gz"))):
    continue
   raw=raw_git_blob(blob)
   out["immutable_source_inventory"]["scanned_git_json_files"]+=1
   collector.source({"origin":"git","path":path,"blob":blob,"bytes":size},raw)
  except Exception as exc:
   out["immutable_source_inventory"]["unreadable_sources"].append(
      {"path":path,"blob":blob,"error":str(exc)[:160]})
 out["immutable_source_inventory"]["scanned_git_blobs"]=len(seen)
 out["immutable_source_inventory"]["field_bearing_git_sources"]=collector.field_bearing

def github_json(url,token):
 req=urllib.request.Request(url,headers={
    "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
    "X-GitHub-Api-Version":"2022-11-28","User-Agent":"unit-a-frozen-audit"})
 with urllib.request.urlopen(req,timeout=30) as res:
  return json.load(res)
def github_bytes(url,token,limit):
 req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,
   "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
   "User-Agent":"unit-a-frozen-audit"})
 with urllib.request.urlopen(req,timeout=100) as res:
  data=res.read(limit+1)
 if len(data)>limit:raise ValueError("artifact size exceeds bounded limit")
 return data
def scan_actions(out,collector):
 token=os.environ.get("GH_TOKEN","")
 if not token:
  out["actions"]["artifacts_expired_or_inaccessible"].append(
     {"reason":"GITHUB_TOKEN_UNAVAILABLE","potential_full_decision_state":"UNPROVEN"})
  return
 actions=out["actions"]
 runs=set(RUNS)
 # Enumerate completed prior Unit A A3 runs, without triggering any workflow.
 try:
  for pg in range(1,13):
   data=github_json(RUN_URL+"runs?per_page=100&page="+str(pg),token)
   rr=data.get("workflow_runs") or []
   if not rr:break
   for r in rr:
    name=str(r.get("name") or "").lower()
    branch=str(r.get("head_branch") or "").lower()
    if r.get("status")!="completed":continue
    if (("unit a" in name or "unit-a" in branch or "attack-event" in branch) and
       ("classif" in name or "replay" in name or "context" in name)):
     runs.add(int(r["id"]))
     if int(r["id"]) not in RUNS:
      actions["discovered_earlier_a3_runs"].append(int(r["id"]))
   if str(rr[-1].get("created_at") or "")<"2026-10-07":
    break
 except Exception as exc:
  actions["artifacts_expired_or_inaccessible"].append(
   {"reason":"ACTIONS_RUN_ENUMERATION_FAILED","error":str(exc)[:140],
    "potential_full_decision_state":"UNPROVEN"})
 for run in sorted(runs):
  inspected={"run_id":run,"artifacts_found":0,"artifacts_downloaded":0,"status":"READ"}
  try:
   data=github_json(RUN_URL+"runs/"+str(run)+"/artifacts?per_page=100",token)
   artifacts=data.get("artifacts") or []
   inspected["artifacts_found"]=len(artifacts)
   actions["artifacts_listed"]+=len(artifacts)
   if data.get("total_count",len(artifacts))>len(artifacts):
    actions["artifacts_expired_or_inaccessible"].append(
       {"run_id":run,"reason":"ARTIFACT_PAGINATION_INCOMPLETE",
        "potential_full_decision_state":"UNPROVEN"})
   for a in artifacts:
    info={"run_id":run,"artifact_id":a.get("id"),"artifact_name":a.get("name"),
          "bytes":a.get("size_in_bytes")}
    if a.get("expired"):
     actions["artifacts_expired_or_inaccessible"].append(
       {**info,"status":"EXPIRED","potential_full_decision_state":"UNPROVEN"})
     continue
    if (a.get("size_in_bytes") or 0)>MAX_ZIP:
     actions["artifacts_expired_or_inaccessible"].append(
       {**info,"status":"SKIPPED_OVERSIZED","potential_full_decision_state":"UNPROVEN"})
     continue
    try:
     z=github_bytes(RUN_URL+"artifacts/"+str(a["id"])+"/zip",token,MAX_ZIP)
     inspected["artifacts_downloaded"]+=1
     actions["artifacts_downloaded"]+=1
     with zipfile.ZipFile(io.BytesIO(z)) as zz:
      for f in sorted(zz.namelist()):
       if not f.lower().endswith((".json",".jsonl",".ndjson",".json.gz")):continue
       try:
        data=zz.read(f)
        actions["scanned_files"]+=1
        collector.source({"origin":"actions","run_id":run,
           "artifact_id":a["id"],"artifact_name":a.get("name"),
           "file_name":f,"bytes":len(data)},data)
       except Exception as exc:
        actions["artifacts_expired_or_inaccessible"].append(
         {**info,"file_name":f,"status":"FILE_UNREADABLE","error":str(exc)[:120],
          "potential_full_decision_state":"UNPROVEN"})
    except Exception as exc:
     actions["artifacts_expired_or_inaccessible"].append(
       {**info,"status":"INACCESSIBLE","error":str(exc)[:160],
        "potential_full_decision_state":"UNPROVEN"})
  except Exception as exc:
   inspected["status"]="INACCESSIBLE"
   actions["artifacts_expired_or_inaccessible"].append(
     {"run_id":run,"status":"RUN_ARTIFACT_LIST_INACCESSIBLE",
      "error":str(exc)[:160],"potential_full_decision_state":"UNPROVEN"})
  actions["runs_inspected"].append(inspected)
 actions["discovered_earlier_a3_runs"]=sorted(set(actions["discovered_earlier_a3_runs"]))

def independently_reduce(values,bydr,targets):
 recovered={}
 conflicts=[]
 for dr in sorted(bydr):
  recovered[dr]={}
  for k in MISSING:
   copies=values.get(dr,{}).get(k,[])
   groups=collections.defaultdict(list)
   for one in copies: groups[one["hash"]].append(one)
   if len(groups)>1:
    h=sorted(groups)
    conflicts.append({"decision_ref":dr,"field":k,"hashes":h,
      "sources":[groups[h[0]][0]["source"],groups[h[1]][0]["source"]]})
   elif len(groups)==1:
    one=groups[next(iter(groups))][0]
    recovered[dr][k]={"value":copy.deepcopy(one["value"]),
                      "hash":one["hash"],"sources":[x["source"] for x in copies[:6]]}
 return recovered,conflicts

def payload_formatter():
 raw=cmd("show",CLASS_COMMIT+":"+CLASS_PATH).decode("utf-8")
 tree=ast.parse(raw)
 fns=[x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=="classification_evidence_payload"]
 if len(fns)!=1:
  raise Blocked("UNIT_A_FROZEN_PAYLOAD_LINEAGE_UNPROVEN","pinned evidence payload formatter not uniquely found")
 fn=copy.deepcopy(fns[0]);fn.decorator_list=[]
 module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
 scope={"__builtins__":{"bool":bool,"str":str,"int":int,"list":list,"dict":dict,
   "set":set,"tuple":tuple,"sorted":sorted,"len":len,"isinstance":isinstance,
   "any":any,"all":all},"json":json,"copy":copy}
 exec(compile(module,"pinned_pure_payload_formatter","exec"),scope)
 return scope["classification_evidence_payload"]

def finalize(out,collector,targets,bydr,dstore):
 inv=out["immutable_source_inventory"]
 inv["source_roles"]=dict(sorted(collector.roles.items()))
 inv["sources"]=sorted((compact_source(x) for x in collector.sources),
            key=lambda x:(x.get("origin",""),x.get("path",""),str(x.get("run_id","")),str(x.get("blob",""))))
 out["lineage"]["exact_full_decision_sources"]=collector.matched_sources["EXACT_FULL_DECISION_SOURCE"]
 out["lineage"]["partial_decision_sources"]=collector.matched_sources["PARTIAL_DECISION_SOURCE"]
 out["lineage"]["queue_sources_with_exact_lineage"]=collector.matched_sources["QUEUE_STATE_WITH_EXACT_DECISION_LINEAGE"]
 out["lineage"]["lineage_failures"]=len(collector.lineage_errors)
 out["lineage"]["bounded_failures"]=collector.lineage_errors
 # Reconstruct twice from fresh, isolated value and target objects.
 a,ca=independently_reduce(copy.deepcopy(dict(collector.values)),copy.deepcopy(bydr),copy.deepcopy(targets))
 b,cb=independently_reduce(copy.deepcopy(dict(collector.values)),copy.deepcopy(bydr),copy.deepcopy(targets))
 sem=0 if a==b and ca==cb else 1
 runa=hobj({"recovered":a,"conflicts":ca})
 runb=hobj({"recovered":b,"conflicts":cb})
 out["determinism"]={"run_a_recovery_sha256":runa,"run_b_recovery_sha256":runb,
                     "semantic_mismatches":sem}
 conflicts=ca
 out["lineage"]["conflicting_decisions"]=len(set(x["decision_ref"] for x in conflicts))
 out["lineage"]["conflicts"]=conflicts[:20]
 counts={}
 anymiss=collections.Counter()
 for field in MISSING:
  present={d for d in bydr if field in a[d] and
           not any(c["decision_ref"]==d and c["field"]==field for c in conflicts)}
  occ=sum(1 for t in targets if t["decision_ref"] in present)
  counts[field]={"target_occurrences":len(targets),"recovered_occurrences":occ,
    "missing_occurrences":len(targets)-occ,
    "relevant_decision_refs":len(bydr),"recovered_decision_refs":len(present),
    "missing_decision_refs":len(bydr)-len(present),
    "conflicts":sum(c["field"]==field for c in conflicts)}
  anymiss[field]=len(bydr)-len(present)
 out["per_field_recovery_coverage"]=counts
 out["unrecovered_fields"]=[k for k in MISSING if anymiss[k]]
 missingdr=sorted(d for d in bydr if any(k not in a[d] for k in MISSING))
 out["affected_decision_refs"]=len(missingdr)
 out["affected_occurrences"]=sum(t["decision_ref"] in set(missingdr) for t in targets)
 out["affected_episodes"]=len(set(t["alert_episode_uid"] for t in targets if t["decision_ref"] in set(missingdr)))
 ok=not any(anymiss.values()) and not conflicts and sem==0 and runa==runb and not collector.lineage_errors
 if ok:
  format_payload=payload_formatter()
  failures=0; misskeys=0; payload_hashes=[]
  for t in targets:
   d=t["decision_ref"]
   row={**dstore[d],**{k:a[d][k]["value"] for k in MISSING}}
   try:
    result=format_payload(row)
    if not isinstance(result,dict):raise ValueError("formatter did not return dict")
    absent=set(PAYLOAD_REQUIRED)-set(result)
    if absent: misskeys+=len(absent);failures+=1
    else:payload_hashes.append(hobj(result))
   except Exception as exc:
    failures+=1
    if len(out["lineage"]["bounded_failures"])<12:
     out["lineage"]["bounded_failures"].append({"reason":"PURE_FORMAT_ERROR","error":str(exc)[:120]})
  out["persistence_payload_construction"].update(
   {"payloads_constructable":len(payload_hashes),"missing_required_keys":misskeys,
    "construction_failures":failures,
    "canonical_payload_set_sha256":hobj(payload_hashes)})
  ok=failures==0 and len(payload_hashes)==1559
 else:
  out["persistence_payload_construction"].update(
      {"payloads_constructable":0,"missing_required_keys":sum(anymiss.values()),
       "construction_failures":len(targets)})
 if ok:
  out["verdict"]="ATTACK-EVENT UNIT A FROZEN PERSISTENCE PAYLOAD RECOVERY = RECOVERED"
  out["A4_PAYLOAD_RECOVERY_GATE"]="PASS"
  out["recovered_decision_map"]={
   d:{"decision_ref":d,"candidate_identity":{"candidate_id":bydr[d]["candidate_id"],
       "candidate_input_ref":bydr[d]["candidate_input_ref"],
       "city_key":bydr[d]["city_key"]},
       "recovered_fields":{k:a[d][k]["value"] for k in MISSING},
       "sources":{k:a[d][k]["sources"] for k in MISSING},
       "recovered_fields_canonical_sha256":hobj({k:a[d][k]["value"] for k in MISSING}),
       "lineage_verification_status":"EXACT_FROZEN_A3_PROJECTION_MATCH"} for d in sorted(bydr)}
  out["BOUNDED_PAYLOAD_REPLAY_REQUIRED"]="NO"
 else:
  if conflicts: gate="UNIT_A_FROZEN_PAYLOAD_CONFLICT"
  elif sem: gate="UNIT_A_FROZEN_PAYLOAD_RECOVERY_NONDETERMINISTIC"
  elif collector.lineage_errors and not all(anymiss.values()):gate="UNIT_A_FROZEN_PAYLOAD_LINEAGE_UNPROVEN"
  elif all(anymiss.values()):gate="UNIT_A_FROZEN_PAYLOAD_SOURCE_NOT_FOUND"
  else:gate="UNIT_A_FROZEN_PAYLOAD_INCOMPLETE"
  out["first_failing_gate"]=gate
  out["smallest_deterministic_blocker_example"].update(
     {"unrecovered_fields":out["unrecovered_fields"],"reason":gate})
  no_skip=(not inv["skipped_oversized"] and not inv["unreadable_sources"] and
       out["queue_snapshots"]["scanned"]==89 and
       not out["queue_snapshots"]["inaccessible"] and
       not out["actions"]["artifacts_expired_or_inaccessible"])
  # YES requires demonstrated exhaustive preservation search; otherwise UNPROVEN.
  out["BOUNDED_PAYLOAD_REPLAY_REQUIRED"]="YES" if no_skip else "UNPROVEN"
 return out

def main():
 out=report_start()
 try:
  a4,r3,a3=preflight(out)
  _,corpus,store,id_by_ref=decode_a1(out)
  targets,bydr,dstore=targets_build(out,r3,a3,id_by_ref)
  queue_ids=snapshot_refs(corpus)
  inv=git_inventory(out,queue_ids)
  collector=Collector(targets,bydr,dstore)
  scan_git(out,collector,inv)
  scan_actions(out,collector)
  finalize(out,collector,targets,bydr,dstore)
 except Blocked as ex:
  out["first_failing_gate"]=ex.gate
  out["audit_exception"]={"type":"BLOCKED","message":str(ex)[:320]}
 except Exception as ex:
  out["first_failing_gate"]="UNIT_A_FROZEN_PAYLOAD_LINEAGE_UNPROVEN"
  out["audit_exception"]={"type":type(ex).__name__,"message":str(ex)[:320]}
 if not out["first_failing_gate"] and out["A4_PAYLOAD_RECOVERY_GATE"]!="PASS":
  out["first_failing_gate"]="UNIT_A_FROZEN_PAYLOAD_INCOMPLETE"
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_bytes(canonical(out)+b"\n")
 print("VERDICT="+out["verdict"])
 print("A4_PAYLOAD_RECOVERY_GATE="+out["A4_PAYLOAD_RECOVERY_GATE"])
 print("FIRST_FAILING_GATE="+str(out["first_failing_gate"]))
 print("TARGETS="+str(out["recovery_target_counts"]))
 print("GIT_SOURCES_SCANNED="+str(out["immutable_source_inventory"]["scanned_git_json_files"]))
 print("QUEUE_SNAPSHOTS="+str(out["queue_snapshots"]["scanned"])+"/"+str(out["queue_snapshots"]["referenced_commits"]))
 print("ACTIONS_RUNS="+str(len(out["actions"]["runs_inspected"])))
 print("ACTIONS_ARTIFACTS_DOWNLOADED="+str(out["actions"]["artifacts_downloaded"]))
 print("FIELD_COVERAGE="+json.dumps({k:[v["recovered_occurrences"],v["target_occurrences"]] for k,v in out["per_field_recovery_coverage"].items()},sort_keys=True))
 print("REPLAY_REQUIRED="+out["BOUNDED_PAYLOAD_REPLAY_REQUIRED"])
 print("RECOVERY_SHA256="+sha(OUT.read_bytes()))
 return 0

if __name__=="__main__":
 sys.exit(main())
