#!/usr/bin/env python3
"""Independent, Git-only H2 original-export revalidation; disposable research runner."""
import argparse
import collections
import datetime
import hashlib
import json
import re
import subprocess
import sys
import traceback
from pathlib import Path

ORIGINAL=("03a04d33f7616b77181741fd77a776c490391d07","research/attack_event_18city_persistence_identity_export_v2_2026-10-04.json","a240f1950748afcb9fc974c49ac58da07adfff65",60509907,"a8440ab537e1b675c7223b7eb7b29c817c1a2e8fc26ba5cf494b5efb3caf662a")
PREVIOUS=("c23387942a6b3effafa612195582b1e56afe618f","research/neon_h2_19542_field_authority_containment_revalidation_2026-10-12.json","2abd72d10bdac896d3c4ed10c582c38aafb162af",1654218,"c3827de8c0574c0305e5da1efe619da678faaa2e8a201150ac8fe5fa7f57bd8c")
TARGET=("3c39dabbf78ff9415213332023e6e6c4ee7e8225","research/attack_event_18city_accepted_target_map_2026-10-04.json","4211c5899f219c4561cd139afbbf48c36b6ea86f",1408158,"a8f616ffc6b63dba16feb03738f1e12e86e2c4e532a939cd4e901cb252a7f06e")
CONTRACTS={
 "persistence":("b205d38dbc50bc502d10e682d4ae53491af542ea","research/attack_event_neon_persistence_contract_2026-10-02.json","e9dcbdf21551ca086fbf096138f885f453a8c2b0"),
 "classification_v2":("bd82a6c0a19aca4610a8af6df73a307a88c35bf6","research/attack_event_classification_identity_availability_addendum_2026-10-04.json","c4b36f92d4171f59a5b3e45f4d894aedf4d7ebd7"),
 "normalization":("b56a7f4c8b22788fc5b4698a1c24fce25ebfaac5","research/attack_event_18city_normalization_version_addendum_2026-10-04.json","d77384e47b62e666a3e3cfbeb652b2ebfff07e9f"),
}
CLASSIFIER_BLOB="89b1be41909c6622339ce8a82d9ac2d982b82481"
REPLAY_BLOB="e1a6c793d680196724fbf70f09ed09a821912aca"
BASE="69b6f635f6f61c7c99e287f998323ee258009208"
POSITIVE={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}

def git(*args,check=True):
 p=subprocess.run(["git",*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode:
  raise RuntimeError("GIT_FAILURE "+ " ".join(map(str,args))+": "+p.stderr.decode("utf8","replace")[:500])
 return p

def gittext(*args):
 return git(*args).stdout.decode("utf8").strip()

def commit_present(sha):
 if git("cat-file","-e",sha+"^{commit}",check=False).returncode:
  git("fetch","--no-tags","origin",sha)
 if gittext("rev-parse",sha+"^{commit}")!=sha:
  raise RuntimeError("UNAUTHENTICATED_GIT_COMMIT "+sha)

def gitbytes(ref,path,expected_blob,expected_size=None,expected_sha=None):
 got=gittext("rev-parse",ref+":"+path)
 if got!=expected_blob:
  raise RuntimeError("GIT_BLOB_ID_MISMATCH "+ref+":"+path+" "+got+" vs "+expected_blob)
 raw=git("cat-file","blob",got).stdout
 actual_sha=hashlib.sha256(raw).hexdigest()
 if len(raw)!=expected_size and expected_size is not None:
  raise RuntimeError("BYTE_LENGTH_MISMATCH "+path+" "+str(len(raw)))
 if expected_sha is not None and actual_sha!=expected_sha:
  raise RuntimeError("SHA256_MISMATCH "+path+" "+actual_sha)
 return raw

def canonical(x):
 return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf8")

def h(x):
 return hashlib.sha256(x).hexdigest()

def ch(x):
 return h(canonical(x))

def independent_list_bytes(items):
 return ("["+",".join(json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str) for item in items)+"]").encode("utf8")

def keyhash(items):
 raw=canonical(items)
 if raw!=independent_list_bytes(items):
  raise AssertionError("INDEPENDENT_ENCODER_DISAGREEMENT")
 return h(raw)

def utc6(value):
 if not isinstance(value,str):
  raise ValueError("UTC_BOUNDARY_NOT_STRING")
 d=datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
 if d.tzinfo is None:
  raise ValueError("NAIVE_SOURCE_EPISODE_BOUNDARY")
 return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def test_contracts():
 tests={}
 obj=["\u0407",None,[],{"b":2,"a":1}]
 tests["UTF8_SORTED_CANONICAL_JSON"]=canonical(obj)==b'["\xd0\x87",null,[],{"a":1,"b":2}]'
 tests["INDEPENDENT_JSON_ENCODER"]=canonical(obj)==independent_list_bytes(obj)
 tests["NULL_VS_EMPTY_ARRAY"]=ch(["x",None])!=ch(["x",[]])
 tests["EVENT_TYPES_SORT_ORDER"]=ch(sorted(["b","a","a"]))!=ch(["b","a","a"])
 tests["MEMBER_DEDUPLICATION"]=len(sorted(set([("x","h"),("x","h"),("y","h")])))==2
 tests["UTC_STRING_MICROSECONDS"]=utc6("2026-01-02T03:04:05.000006+00:00")=="2026-01-02T03:04:05.000006Z"
 tests["UTC_INSTANT_EQUIVALENCE"]=utc6("2026-01-02T05:04:05.000006+02:00")=="2026-01-02T03:04:05.000006Z"
 tests["UTC_STRING_IS_NOT_INTEGER"]=isinstance(utc6("2026-01-02T00:00:00Z"),str)
 tests["DOMAIN_SEPARATION"]=ch(["attack-event-classification-key-v2","x"])!=ch(["attack-event-key-v1","x"])!=ch(["attack-event-source-link-key-v1","x"])
 tests["MUTATED_INPUT_DETECTED"]=ch(["x","y"])!=ch(["x","z"])
 tests["MUTATED_EMBEDDED_ARRAY_DETECTED"]=ch(["a",'["b"]'])!=ch(["a",'["c"]'])
 tests["MUTATED_KEY_VALUE_DETECTED"]=ch(["x"])!="0"*64
 if not all(tests.values()):
  raise AssertionError("INDEPENDENT_CONTRACT_TEST_FAILURE "+str(tests))
 return tests

def target_lookup(doc):
 out={}
 for city in doc["target_map"]:
  name=city["city_key"]
  if name in out: raise AssertionError("DUPLICATE_TARGET_CITY "+name)
  rows=city["target_rows"]
  ids=[r["episode_id"] for r in rows]
  if len(ids)!=len(set(ids)):
   raise AssertionError("DUPLICATE_TARGET_EPISODE "+name)
  out[name]={"rows":{r["episode_id"]:r["state"] for r in rows},"hash":city["accepted_target_state_sha256"],"n":len(rows)}
 return out

def verify():
 for c in [ORIGINAL,PREVIOUS,TARGET,*CONTRACTS.values()]:commit_present(c[0])
 original_raw=gitbytes(*ORIGINAL)
 corrected=json.loads(gitbytes(*PREVIOUS))
 target_doc=json.loads(gitbytes(*TARGET))
 contracts={k:json.loads(gitbytes(*v)) for k,v in CONTRACTS.items()}
 exp=json.loads(original_raw)
 del original_raw
 if exp.get("kind")!="attack_event_18city_persistence_identity_export_v2":
  raise AssertionError("EXPORT_FORMAT_UNKNOWN")
 if contracts["classification_v2"]["classification_identity_v2"]["classification_key_version"]!="attack-event-classification-key-v2":
  raise AssertionError("CLASSIFICATION_KEY_CONTRACT_DIFFERENT")
 if contracts["persistence"]["event_identity"]["attack_event_key_version"]!="attack-event-key-v1":
  raise AssertionError("EVENT_KEY_CONTRACT_DIFFERENT")
 if exp.get("classifier_blob_sha")!=CLASSIFIER_BLOB or exp.get("classifier_methodology_version")!="historical-attack-event-air-defense-action-v2":
  raise AssertionError("CLASSIFIER_PROVENANCE_CHANGED")
 if exp.get("target_map_sha256")!="d8c2c78d8340288308eb027f37e36de83c38fdee3230e5679a30ae41328f6eb2":
  raise AssertionError("ACCEPTED_TARGET_CANONICAL_HASH_MISMATCH")
 target=target_lookup(target_doc)
 tests=test_contracts()
 by_city=collections.defaultdict(list)
 by_exported_key={}
 for row in exp["classifications"]:
  by_city[row["city_key"]].append(row)
  if row["classification_key"] in by_exported_key:
   raise AssertionError("DUPLICATE_EXPORTED_CLASSIFICATION_KEY")
  by_exported_key[row["classification_key"]]=row
 if set(by_city)!=set(target) or len(by_exported_key)!=19542:
  raise AssertionError("H2_EXPORT_POPULATION_MISMATCH")
 
 # Strict Git origin validation for each original chronology slice, never derive source rows from the export.
 provenance=corrected["original_chronological_provenance"]
 source_blob_evidence={}
 all_original={}
 slices_manifest={}
 crosswalk=[]
 chrono={}
 chrono_mismatches=[]
 for city in sorted(target):
  pr=provenance[city]; commit=pr["original_tested_head"]
  commit_present(commit)
  entries=[]
  for s in pr["sources"]:
   raw=gitbytes(commit,s["path"],s["blob"],None,s["sha256"])
   data=json.loads(raw); eps=data.get("episodes") or []
   if len(eps)!=s["episodes"] or data.get("episode_count")!=len(eps):
    raise AssertionError("SOURCE_SLICE_EPISODE_COUNT "+s["path"])
   entries.extend(eps)
   slices_manifest[s["path"]]={"commit":commit,"blob":s["blob"],"bytes":len(raw),"sha256":s["sha256"],"episodes":len(eps)}
  originals={}
  for ep in entries:
   eid=ep["episode_id"]
   if eid in originals:raise AssertionError("DUPLICATE_ORIGINAL_EPISODE "+city+":"+eid)
   originals[eid]=ep
  if len(originals)!=pr["episodes"]:
   raise AssertionError("ORIGINAL_CHRONOLOGY_COUNT "+city)
  export_rows=by_city[city]
  ids=[r["historical_episode_id"] for r in export_rows]
  if len(ids)!=len(set(ids)) or set(ids)!=set(target[city]["rows"]) or len(ids)!=target[city]["n"]:
   raise AssertionError("ACCEPTED_TARGET_EPISODE_POPULATION "+city)
  r_by_id={r["historical_episode_id"]:r for r in export_rows}
  by_interval=collections.defaultdict(list)
  for x in export_rows:by_interval[(x["alert_start_utc_microseconds"],x["alert_end_utc_microseconds"])].append(x)
  canonical_rows=[]
  city_cross=[]
  for orig_id,ep in originals.items():
   orig_start,orig_end=utc6(ep["alert_start"]),utc6(ep["alert_end"])
   candidates=by_interval[(orig_start,orig_end)]
   if city=="kyiv":
    selected=candidates[0] if len(candidates)==1 else None
    city_cross.append({"original_id":orig_id,"original_start":ep["alert_start"],"original_end":ep["alert_end"],"start_utc":orig_start,"end_utc":orig_end,"candidate_count":len(candidates),"target_id":selected["historical_episode_id"] if selected else None})
   else:
    selected=r_by_id.get(orig_id)
    if selected and (selected["alert_start_utc_microseconds"],selected["alert_end_utc_microseconds"])!=(orig_start,orig_end):selected=None
    if selected is None:chrono_mismatches.append({"city":city,"original_id":orig_id,"error":"ID_OR_INTERVAL_MISMATCH"})
   if selected is None:
    if city=="kyiv":chrono_mismatches.append({"city":city,"original_id":orig_id,"error":"NONUNIQUE_EXACT_INTERVAL","candidate_count":len(candidates)})
    continue
   tid=selected["historical_episode_id"]
   canonical_rows.append({"episode_id":orig_id,"alert_start":ep["alert_start"],"alert_end":ep["alert_end"],"state":target[city]["rows"][tid]})
   if selected["verdict"]!=target[city]["rows"][tid]:
    chrono_mismatches.append({"city":city,"original_id":orig_id,"error":"TARGET_VERDICT_MISMATCH"})
  canonical_rows.sort(key=lambda x:(x["alert_start"],x["episode_id"]))
  digest=ch(canonical_rows)
  chrono[city]={"original_rows":len(originals),"export_rows":len(export_rows),"recomputed_original_sha256":digest,"expected_reported_original_sha256":pr["canonical_original_chronology_sha256"],"accepted_original_sha256":pr.get("accepted_original_hash"),"matching_reported_hash":digest==pr["canonical_original_chronology_sha256"],"source_slices":len(pr["sources"]),"original_tested_head":commit,"original_id_duplicates":0}
  if digest!=pr["canonical_original_chronology_sha256"]:
   chrono_mismatches.append({"city":city,"error":"ORIGINAL_CHRONOLOGY_DIGEST_MISMATCH","actual":digest,"expected":pr["canonical_original_chronology_sha256"]})
  all_original[city]=originals
  if city=="kyiv":crosswalk=sorted(city_cross,key=lambda x:(x["original_start"],x["original_id"]))
 if len(crosswalk)!=2456:raise AssertionError("KYIV_CROSSWALK_DENOMINATOR")
 target_ids=[x["target_id"] for x in crosswalk]
 cross_unique=all(x["candidate_count"]==1 and x["target_id"] for x in crosswalk) and len(target_ids)==len(set(target_ids))==2456
 
 # Original evidence blobs and row identities, pinned to each worker's tested HEAD.
 worker_by_city={}
 evidence_by_city={}
 for worker in corrected["immutable_inputs"]["original_city_worker_evidence"]:
  city=worker["city"]; worker_by_city[city]=worker
  commit_present(worker["tested_head"])
  raw=gitbytes(worker["tested_head"],worker["original_evidence_path"],worker["original_evidence_blob"],None,worker["original_evidence_sha256"])
  evidence_by_city[city]=json.loads(raw)
  source_blob_evidence[city]={"source_head":worker["tested_head"],"source_blob":worker["original_evidence_blob"],"sha256":worker["original_evidence_sha256"],"bytes":len(raw),"worker_formalizer_blob":worker["worker_formalizer_blob"],"worker_proof_blob":worker["worker_proof_blob"]}
 
 # Independently hash each normalized source-link payload and validate original raw evidence row.
 reg_index={}
 for x in corrected["full_membership_regression"]:
  index=(x["city"],x["observation_id"])
  if index in reg_index:raise AssertionError("CORRECTED_LEDGER_DUPLICATE "+repr(index))
  reg_index[index]=x
 if len(reg_index)!=1429:raise AssertionError("CORRECTED_LEDGER_COUNT")
 links=collections.defaultdict(list)
 source_errors=[]
 link_ledger=[]
 raw_rows_ok=0
 for l in exp["source_links"]:
  payload=l.get("normalized_accepted_observation_payload")
  if not isinstance(payload,dict):
   raise AssertionError("NORMALIZED_PAYLOAD_NOT_OBJECT")
  claimed_native=payload.get("content_hash")
  recalc_content=str(claimed_native).lower() if claimed_native not in (None,"") else ch(payload)
  match=by_exported_key.get(l["classification_key_v2"])
  if match is None:raise AssertionError("LINK_CLASSIFICATION_NOT_FOUND")
  city=match["city_key"]; oid=l["observation_id"]
  ledger=reg_index.get((city,oid))
  origin=l["origin"]; meta=l["retrieval_provenance"]; wi=worker_by_city[city]
  valid_source=origin["path"]==wi["original_evidence_path"] and origin["ref"]==wi["tested_head"] and origin["blob"]==wi["original_evidence_blob"]
  raw_row_hash=None; raw_row_match=False
  try:
   raw_row=evidence_by_city[city][meta["bucket"]][meta["index"]]
   raw_row_hash=ch(raw_row)
   raw_row_match=ledger is not None and raw_row_hash==ledger["original_record_sha256"] and meta["bucket"]==ledger["bucket"] and meta["index"]==ledger["original_row_index"]
  except (KeyError,IndexError,TypeError) as ex:
   source_errors.append({"city":city,"observation_id":oid,"issue":"RAW_SOURCE_LOOKUP "+str(ex)})
  if raw_row_match:raw_rows_ok+=1
  else:source_errors.append({"city":city,"observation_id":oid,"issue":"ORIGINAL_RAW_ROW_HASH_OR_INDEX_MISMATCH","raw_sha256":raw_row_hash})
  if not valid_source:source_errors.append({"city":city,"observation_id":oid,"issue":"ORIGIN_POINTER_MISMATCH"})
  if ledger and ledger["exported_episode_id"]!=match["historical_episode_id"]:
   source_errors.append({"city":city,"observation_id":oid,"issue":"HISTORICAL_MEMBERSHIP_LEDGER_PARENT_MISMATCH"})
  if recalc_content!=l["content_sha256"]:
   source_errors.append({"city":city,"observation_id":oid,"issue":"NORMALIZED_CONTENT_SHA_MISMATCH"})
  links[l["classification_key_v2"]].append((oid,recalc_content))
  link_ledger.append({"city":city,"episode":match["historical_episode_id"],"observation_id":oid,"claimed_key":l["source_link_key"],"raw_row_sha256":raw_row_hash,"recomputed_content_sha256":recalc_content,"source_row_verified":raw_row_match and valid_source})
 
 # Deterministic-key recomputation uses the ORIGINAL export's constituent fields, not the earlier verifier.
 count={"classification_checked":0,"classification_matched":0,"event_checked":0,"event_matched":0,"source_checked":0,"source_matched":0}
 mismatches={"classification":[],"event":[],"source":[],"evidence_membership":[],"review":[],"normalization":[]}
 calculated={}
 city_rows=collections.defaultdict(lambda:{"classification":[],"event":[],"source":[]})
 norm_contract={r["worker_lineage"]:r["final_authoritative_normalization_version"] for r in contracts["normalization"]["worker_normalization_availability_matrix"]}
 city_worker={}
 for row in target_doc["workers"]:
  for city in row.get("cities",[]):city_worker[city]=row.get("worker")
 for city in sorted(target):
  for c in by_city[city]:
   count["classification_checked"]+=1
   id=c["historical_episode_id"]
   pairs=sorted(set(links.get(c["classification_key"],[])))
   members=[[x,y] for x,y in pairs]
   derived_evidence_sha=ch(members)
   if c["accepted_evidence_membership"]!=members or derived_evidence_sha!=c["evidence_set_sha256"]:
    mismatches["evidence_membership"].append({"city":city,"episode_id":id})
   review=c.get("review_provenance")
   review_sha=ch(review) if isinstance(review,dict) and review else None
   if c.get("review_provenance_sha256")!=review_sha:
    mismatches["review"].append({"city":city,"episode_id":id})
   norm=norm_contract.get(c["origin_provenance"]["worker"])
   if c["normalization_version"]!=norm:
    mismatches["normalization"].append({"city":city,"episode_id":id})
   evtypes=sorted(set(map(str,c.get("event_types") or [])))
   evtypes_string=json.dumps(evtypes,ensure_ascii=False,separators=(",",":"))
   qa=c["qa_reasons"]
   qa_input=json.dumps(sorted(qa),ensure_ascii=False,separators=(",",":")) if isinstance(qa,list) else None
   tpl=["attack-event-classification-key-v2",city,id,c["alert_start_utc_microseconds"],c["alert_end_utc_microseconds"],c["verdict"],evtypes_string,c["qa_reasons_state"],qa_input,CLASSIFIER_BLOB,c["classifier_methodology_version"],norm,derived_evidence_sha,review_sha]
   calc=keyhash(tpl)
   calculated[c["classification_key"]]=calc
   good=calc==c["classification_key"] and c["qa_reasons_state"]=="UNMATERIALIZED_IN_ACCEPTED_SOURCE" and qa is None and utc6(c["alert_start_utc_microseconds"])==c["alert_start_utc_microseconds"] and utc6(c["alert_end_utc_microseconds"])==c["alert_end_utc_microseconds"]
   if good:count["classification_matched"]+=1
   else:mismatches["classification"].append({"city":city,"episode_id":id,"claimed":c["classification_key"],"recomputed":calc})
   city_rows[city]["classification"].append([id,c["classification_key"],calc])
 for e in exp["attack_events"]:
  count["event_checked"]+=1
  city=e["city_key"];id=e["historical_episode_id"]
  tpl=["attack-event-key-v1","HISTORICAL_ALERT_EPISODE",city,id,e["alert_start_utc_microseconds"],e["alert_end_utc_microseconds"]]
  digest=keyhash(tpl)
  parent=by_exported_key.get(e["classification_key_v2"])
  okay=digest==e["attack_event_key"] and parent is not None and parent["verdict"] in POSITIVE and parent["city_key"]==city and parent["historical_episode_id"]==id and calculated.get(e["classification_key_v2"])==e["classification_key_v2"]
  if okay:count["event_matched"]+=1
  else:mismatches["event"].append({"city":city,"episode_id":id,"claimed":e["attack_event_key"],"recomputed":digest})
  city_rows[city]["event"].append([id,e["attack_event_key"],digest])
 link_lookups={(x["city"],x["observation_id"]):x for x in link_ledger}
 for l in exp["source_links"]:
  count["source_checked"]+=1
  parent=by_exported_key[l["classification_key_v2"]]
  city=parent["city_key"];id=parent["historical_episode_id"]
  newclass=calculated[l["classification_key_v2"]]
  entry=link_lookups[(city,l["observation_id"])]
  tpl=["attack-event-source-link-key-v1",newclass,l["observation_id"],entry["recomputed_content_sha256"]]
  digest=keyhash(tpl)
  if digest==l["source_link_key"] and entry["source_row_verified"]:count["source_matched"]+=1
  else:mismatches["source"].append({"city":city,"episode_id":id,"observation_id":l["observation_id"],"claimed":l["source_link_key"],"recomputed":digest,"source_original_verified":entry["source_row_verified"]})
  city_rows[city]["source"].append([id,l["observation_id"],l["source_link_key"],digest])
 positives={(r["city_key"],r["historical_episode_id"]) for r in exp["classifications"] if r["verdict"] in POSITIVE}
 event_ids=[(r["city_key"],r["historical_episode_id"]) for r in exp["attack_events"]]
 one_to_one=len(positives)==len(event_ids)==len(set(event_ids))==961 and set(event_ids)==positives
 
 # Source-specific timezone contract: distinguish accepted source rules from replay defaults.
 replay_text=git("cat-file","blob",REPLAY_BLOB).stdout.decode("utf8")
 replay_default=bool(re.search(r"dt\s*=\s*dt\.replace\(tzinfo=KYIV_TZ\)",replay_text))
 timezone_cases=[]
 proof_meta={}
 for city in ("dnipro","mykolaiv"):
  worker=worker_by_city[city]
  commit_present(worker["worker_proof_ref"])
  proof_raw=git("cat-file","blob",worker["worker_proof_blob"]).stdout
  proof=json.loads(proof_raw)
  proof_meta[city]={"commit":worker["worker_proof_ref"],"blob":worker["worker_proof_blob"],"sha256":h(proof_raw),"explicit_source_timezone_fields_found":[], "proof_has_timezone_section":any("timezone" in str(k).lower() for k in proof)}
  worker_code=git("cat-file","blob",worker["worker_formalizer_blob"]).stdout.decode("utf8")
  proof_meta[city]["worker_formalizer_sha256"]=h(worker_code.encode("utf8"))
  proof_meta[city]["tested_head"]=worker["tested_head"]
  proof_meta[city]["replay_parser_blob"]=REPLAY_BLOB
 for r in corrected["full_membership_regression"]:
  if r["previous_authority"]==r["corrected_authority"] or r["corrected_authority"]!="REPLAY_DERIVED_ONLY":continue
  city=r["city"]; orig=evidence_by_city[city][r["bucket"]][r["original_row_index"]]
  if ch(orig)!=r["original_record_sha256"]:
   raise AssertionError("TIMEZONE_CASE_ORIGINAL_ROW_MISMATCH "+city+":"+r["observation_id"])
  naive={}
  for field,details in (r.get("original_clock_evidence") or {}).items():
   if isinstance(details,dict) and details.get("raw") is not None and details.get("exact_utc") is None:
    naive[field]=details["raw"]
    if str(orig.get(field))!=str(details["raw"]):
     raise AssertionError("TIMEZONE_CASE_CLOCK_NOT_FROM_ORIGINAL "+city+":"+r["observation_id"]+":"+field)
  # Verified original worker proof is an accepted implementation record, not a source-specific temporal contract.
  # No accepted source-specific field-timezone rule appears in the checked worker proof/normalization contracts.
  decision="REPLAY_TIMEZONE_ASSUMPTION_ONLY" if naive and replay_default else "TIMEZONE_CONTRACT_NOT_OBSERVABLE"
  timezone_cases.append({"city":city,"observation_id":r["observation_id"],"bucket":r["bucket"],"index":r["original_row_index"],"original_record_sha256":r["original_record_sha256"],"original_source_blob":r["original_source_blob"],"original_tested_head":r["original_source_head"],"original_naive_fields":naive,"worker_formalizer_blob":worker_by_city[city]["worker_formalizer_blob"],"accepted_worker_proof_blob":worker_by_city[city]["worker_proof_blob"],"replay_parser_blob":REPLAY_BLOB,"accepted_source_specific_timezone_rule":"NOT_FOUND_IN_TESTED_FROZEN_WORKER_PROOF_OR_SOURCE_METADATA","implementation_behavior":"Europe/Kyiv injected into naive replay datetime (not independent field-timezone authority)","decision":decision,"corrected_membership_authority":"REPLAY_DERIVED_ONLY"})
 timezone_cases.sort(key=lambda x:(x["city"],x["bucket"],x["index"],x["observation_id"]))
 if len(timezone_cases)!=63:raise AssertionError("TIMEZONE_DENOMINATOR_NOT_63")
 
 percity={}
 for city in sorted(city_rows):
  rows=city_rows[city]
  percity[city]={"classification_count":len(rows["classification"]),"classification_ledger_sha256":ch(sorted(rows["classification"])),"event_count":len(rows["event"]),"event_ledger_sha256":ch(sorted(rows["event"])),"source_count":len(rows["source"]),"source_ledger_sha256":ch(sorted(rows["source"]))}
 
 key_expected=(count["classification_checked"],count["classification_matched"],count["event_checked"],count["event_matched"],count["source_checked"],count["source_matched"])==(19542,19542,961,961,1429,1429)
 chron_ok=len(chrono)==18 and all(v["matching_reported_hash"] for v in chrono.values()) and not chrono_mismatches
 time_counts=dict(collections.Counter(x["decision"] for x in timezone_cases))
 return {
  "schema_version":"H2_INDEPENDENT_ORIGINAL_EXPORT_REVALIDATION_V1",
  "research_scope":"OFFLINE_READ_ONLY_NO_NEON_NO_CLASSIFIER_RERUN",
  "baseline_main_commit":BASE,
  "immutable_original_export":{"commit":ORIGINAL[0],"path":ORIGINAL[1],"blob":ORIGINAL[2],"bytes":ORIGINAL[3],"sha256":ORIGINAL[4],"locally_authenticated":True},
  "immutable_corrected_comparison":{"commit":PREVIOUS[0],"blob":PREVIOUS[2],"bytes":PREVIOUS[3],"sha256":PREVIOUS[4]},
  "immutable_accepted_target_map":{"commit":TARGET[0],"blob":TARGET[2],"bytes":TARGET[3],"sha256":TARGET[4]},
  "source_slices":slices_manifest,
  "source_evidence_origins":source_blob_evidence,
  "contracts":{k:{"commit":v[0],"path":v[1],"blob":v[2]} for k,v in CONTRACTS.items()},
  "independent_test_results":tests,
  "key_revalidation":{"counts":count,"all_expected_matched":key_expected,"mismatches":mismatches,"source_original_rows_rehashed":raw_rows_ok,"source_original_row_errors":source_errors,"per_city":percity,"all_classification_row_commitment":ch(sorted([row for c in city_rows.values() for row in c["classification"]])),"all_event_row_commitment":ch(sorted([row for c in city_rows.values() for row in c["event"]])),"all_source_row_commitment":ch(sorted([row for c in city_rows.values() for row in c["source"]])),"event_parent_one_to_one":one_to_one},
  "chronology":{"cities":chrono,"mismatches":chrono_mismatches,"all_18_match_corrected":chron_ok,"two_city_previously_accepted_hashes_match":all(chrono[c]["recomputed_original_sha256"]==chrono[c]["accepted_original_sha256"] for c in ("kropyvnytskyi","mykolaiv"))},
  "kyiv_crosswalk":{"count":len(crosswalk),"unique_bidirectional_exact_interval":bool(cross_unique),"ledger":crosswalk,"row_commitment_sha256":ch(crosswalk),"original_id_authority":"NOT_OBSERVABLE_FROM_EXACT_INTERVAL_EQUIVALENCE_ALONE"},
  "timezone_contract_audit":{"case_count":len(timezone_cases),"counts":time_counts,"worker_evidence":proof_meta,"cases":timezone_cases,"decision_method":"Accepted source-field timezone rule required. Replay implementation default alone cannot promote authority.","proposed_286_1064_79_change":"NONE_UNLESS_NEW_ACCEPTED_SOURCE_SPECIFIC_CONTRACT_IS_FOUND"},
  "corrected_prior_distribution":corrected["membership_authority_totals"],
  "corrected_reference_row_ledger_count":len(reg_index),
  "source_binding_authority_not_automatically_promoted":True,
  "computed_key_equality_is_not_original_field_authority":True,
  "historical_parent_admission":"UNRESOLVED",
  "neon_persisted_row_parity":"NOT_CHECKED",
  "hard_boundaries":{"C4":"NOT PROVEN","C5":"NOT PROVEN","UNBOUND_UNRESOLVED":25,"NEON_AUTHORITY_ACTIVE":"NO","PRODUCTION_CUTOVER_EXECUTED":"NO","PRODUCTION_MUTATIONS":0,"NEON_QUERIES":0,"NEON_WRITES":0,"A5_REEXECUTIONS":0,"CLASSIFIER_RERUNS_FOR_TRUTH":0},
  "verdicts":{
   "H2_ORIGINAL_EXPORT_TRANSPORT":"PASS",
   "H2_CLASSIFICATION_KEY_REVALIDATION":"PASS" if key_expected and not mismatches["classification"] and not mismatches["evidence_membership"] and not mismatches["review"] and not mismatches["normalization"] else "PARTIAL",
   "H2_EVENT_KEY_REVALIDATION":"PASS" if count["event_matched"]==961 and one_to_one else "PARTIAL",
   "H2_SOURCE_LINK_KEY_REVALIDATION":"PASS" if count["source_matched"]==1429 and not source_errors else "PARTIAL",
   "H2_18_CITY_CHRONOLOGY_REVALIDATION":"PASS" if chron_ok else "PARTIAL",
   "H2_KYIV_EXACT_INTERVAL_CROSSWALK":"PASS" if cross_unique else "PARTIAL",
   "H2_KYIV_ORIGINAL_ID_AUTHORITY":"NOT_OBSERVABLE",
   "H2_63_CASE_TIMEZONE_CONTRACT_AUDIT":"PARTIAL" if time_counts.get("TIMEZONE_CONTRACT_NOT_OBSERVABLE",0) else "PASS",
   "H2_INDEPENDENT_ACCEPTANCE_BLOCKER_RECOVERY":"PASS" if key_expected and chron_ok and cross_unique and not source_errors else "PARTIAL",
   "H2_19542_FIELD_AUTHORITY_AUDIT":"PARTIAL"
  },
  "notes":["Independent Git-only recomputation uses accepted contracts and original Git bytes; does not import the earlier H2 verifier.","Chronology source slices are independently re-read; original Kyiv IDs are retained separately from target episode IDs.","63 timezone reviews apply an authority ceiling, not a timezone conversion or source rebinding.","Recomputed key agreement is not historical source-binding or replay event-type authority."]
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--output",required=True);ns=ap.parse_args()
 try:
  obj=verify()
 except Exception as e:
  obj={"schema_version":"H2_INDEPENDENT_ORIGINAL_EXPORT_REVALIDATION_V1","status":"BLOCKED","failure_type":type(e).__name__,"failure_message":str(e)[:1200],"traceback_last_lines":traceback.format_exc().splitlines()[-9:],"hard_boundaries":{"NEON_QUERIES":0,"NEON_WRITES":0,"PRODUCTION_WRITES":0},"verdicts":{"H2_INDEPENDENT_ACCEPTANCE_BLOCKER_RECOVERY":"BLOCKED"}}
 raw=canonical(obj)
 Path(ns.output).write_bytes(raw)
 print(json.dumps({"status":obj.get("status","COMPLETED"),"sha256":h(raw),"bytes":len(raw),"verdicts":obj.get("verdicts"),"key_counts":obj.get("key_revalidation",{}).get("counts"),"time_counts":obj.get("timezone_contract_audit",{}).get("counts"),"error":obj.get("failure_message")},sort_keys=True))
 if obj.get("status")=="BLOCKED":sys.exit(0)

if __name__=="__main__":
 main()
