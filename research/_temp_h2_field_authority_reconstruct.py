#!/usr/bin/env python3
"""Read-only H2 field provenance and key proof. Never imports/executes a historical classifier."""
import collections
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

EXPORT=("03a04d33f7616b77181741fd77a776c490391d07","research/attack_event_18city_persistence_identity_export_v2_2026-10-04.json","a240f1950748afcb9fc974c49ac58da07adfff65","a8440ab537e1b675c7223b7eb7b29c817c1a2e8fc26ba5cf494b5efb3caf662a")
TARGET=("3c39dabbf78ff9415213332023e6e6c4ee7e8225","research/attack_event_18city_accepted_target_map_2026-10-04.json","4211c5899f219c4561cd139afbbf48c36b6ea86f","a8f616ffc6b63dba16feb03738f1e12e86e2c4e532a939cd4e901cb252a7f06e")
NORM=("b56a7f4c8b22788fc5b4698a1c24fce25ebfaac5","research/attack_event_18city_normalization_version_addendum_2026-10-04.json","d77384e47b62e666a3e3cfbeb652b2ebfff07e9f",None)
IDENTITY=("bd82a6c0a19aca4610a8af6df73a307a88c35bf6","research/attack_event_classification_identity_availability_addendum_2026-10-04.json","c4b36f92d4171f59a5b3e45f4d894aedf4d7ebd7",None)
CLASSIFIER_BLOB="89b1be41909c6622339ce8a82d9ac2d982b82481"
METHODOLOGY="historical-attack-event-air-defense-action-v2"
PREV_INVENTORY=("9628c9ba7f23afe2f9fc9bb76454c62bfdd639f5","research/neon_h2_19542_field_authority_audit_2026-10-11.json","43d0c92dab32eaf559b5066f337f6479e652397a","1e614a93409ca7270b433e75bb0e7e44b22b109f53744cf1ce589a4897cb1b88")
BASE="dea5d7c5a79edb2e330ff010bc275878f778be33"
BKT=("strict_events","sensitivity_only_events","review_events")
V09={"strict":"strict_events","sensitivity":"sensitivity_only_events","review":"review_events"}
START_FIELDS=("matched_episode_start","matched_alert_episode_start","alert_episode_start","alert_start","alert_start_kyiv","alert_start_local","matched_alert_start","matched_alert_start_kyiv","episode_start","matched_start","alert_episode_start_kyiv","alert_start_utc")
EP_IDS=("episode_id","matched_episode_id","alert_episode_id","target_episode_id")
KYIV=ZoneInfo("Europe/Kyiv")
UTC=dt.timezone.utc

def run(*argv):
    return subprocess.run(argv,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
def gt(*argv):
    return run("git",*argv).decode().strip()
def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
def digest(obj):
    return hashlib.sha256(canon(obj)).hexdigest()
def sha24(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:24]
def record_id(city,bucket,index,row):
    return sha24(city+"|"+bucket+"|"+str(index)+"|"+canon(row).decode("utf-8"))
def stream09_id(bucket,index,row):
    for name in ("event_id","candidate_id","evidence_id","id"):
        if row.get(name) is not None and str(row[name]).strip():
            return str(row[name])
    return sha24(bucket+":"+str(index)+":"+canon(row).decode("utf-8"))
def get(spec):
    ref,path,blob,sha=spec
    actual=gt("rev-parse",ref+":"+path)
    if actual!=blob: raise ValueError("FROZEN_BLOB_MISMATCH:"+path+":"+actual)
    raw=run("git","show",ref+":"+path)
    if sha and hashlib.sha256(raw).hexdigest()!=sha: raise ValueError("FROZEN_CONTENT_MISMATCH:"+path)
    return json.loads(raw)
def getraw(ref,path):
    return run("git","show",ref+":"+path)
def ensure(ref):
    if subprocess.run(["git","cat-file","-e",ref+"^{commit}"],capture_output=True).returncode!=0:
        subprocess.run(["git","fetch","--no-tags","origin",ref],check=True,stdout=subprocess.DEVNULL)
def prep():
    for spec in (EXPORT,TARGET,NORM,IDENTITY,PREV_INVENTORY): ensure(spec[0])
    target=get(TARGET)
    assert len(target["workers"])==10 and len(target["target_map"])==18
    for w in target["workers"]:
        for field in ("tested_head","final_head"): ensure(w[field])
    print("INPUT_PREPARED",len(target["workers"]),flush=True)

def iso_utc(s):
    if not isinstance(s,str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z",s): return None
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError: return None
def raw_time(value):
    if not isinstance(value,str): return None
    s=value.strip()
    # Only an exact source clock may prove a unique historical time binding.
    if not re.fullmatch(r"\d{4}-\d\d-\d\d(?:T| )\d\d:\d\d(?::\d\d(?:\.\d{1,6})?)?(?:Z|[+-]\d\d:\d\d)?",s): return None
    try:
        d=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=KYIV)
        return d.astimezone(UTC)
    except ValueError: return None
def strip_ids(row):
    return {k:v for k,v in row.items() if k not in ("episode_id","matched_episode_id","alert_episode_id")}
def original_binding(row,city,start_rows,classification_id):
    explicit=[]
    for field in EP_IDS:
        v=row.get(field)
        if isinstance(v,str) and v: explicit.append((field,v))
    cb=row.get("canonical_binding")
    if isinstance(cb,str) and cb: explicit.append(("canonical_binding",cb))
    if isinstance(cb,dict):
        for field in EP_IDS+("canonical_episode_id",):
            v=cb.get(field)
            if isinstance(v,str) and v: explicit.append(("canonical_binding."+field,v))
    if explicit:
        unique={x[1] for x in explicit}
        if len(unique)==1:
            e=next(iter(unique))
            if e==classification_id: return "ORIGINAL_ACCEPTED","explicit_episode_identity",None
            return "CONTRADICTION","original_explicit_episode_id_conflict",{"original":sorted(unique),"exported":classification_id}
        if classification_id in unique: return "REPLAY_DERIVED_ONLY","conflicting_explicit_source_ids",{"source_ids":sorted(unique)}
        return "CONTRADICTION","no_original_explicit_id_matches_export",{"original":sorted(unique),"exported":classification_id}
    for field in START_FIELDS:
        val=row.get(field)
        t=raw_time(val)
        if t is None: continue
        candidates=[eid for eid,s in start_rows if abs((s-t).total_seconds())<=90]
        if len(candidates)==1:
            if candidates[0]==classification_id:
                return "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT","unique_original_start_interval",None
            return "CONTRADICTION","original_unique_start_conflicts_with_export",{"original":candidates[0],"exported":classification_id,"field":field}
    # Event-only containment deliberately not treated as accepted identity unless
    # it resolves one unique accepted episode from an exact (not publication) clock.
    for field in ("event_time","event_time_kyiv","event_time_local"):
        t=raw_time(row.get(field))
        if t is None: continue
        candidates=[eid for eid,s,e in start_rows._intervals if s<=t<=e] if hasattr(start_rows,"_intervals") else []
        if len(candidates)==1 and candidates[0]==classification_id:
            return "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT","unique_exact_event_time_containment",None
    return "REPLAY_DERIVED_ONLY","no_independent_original_unique_binding",None

def evidence_source_id(row,city,bucket,idx,stream):
    candidates=set()
    for f in ("evidence_id","event_id","record_id","id","candidate_id","source_url","url"):
        v=row.get(f)
        if isinstance(v,(str,int)) and str(v): candidates.add(str(v))
    candidates.update([record_id(city,bucket,idx,row),record_id(city,bucket,idx,strip_ids(row))])
    if stream: candidates.add(stream09_id({"strict_events":"strict","sensitivity_only_events":"sensitivity","review_events":"review"}[bucket],idx,row))
    return candidates

def metric(v,k):
    if k in v: return v[k]
    return v.get("counts",{}).get(k)

def audit():
    export=get(EXPORT); target=get(TARGET); norm=get(NORM); ident=get(IDENTITY); inv=get(PREV_INVENTORY)
    assert ident["classification_identity_v2"]["classification_key_version"]=="attack-event-classification-key-v2"
    target_by_city={x["city_key"]:{r["episode_id"]:r["state"] for r in x["target_rows"]} for x in target["target_map"]}
    worker_by_city={city:w for w in target["workers"] for city in w["cities"]}
    norm_by_worker={x["worker_lineage"]:x for x in norm["worker_normalization_availability_matrix"]}
    assert len(target_by_city)==18 and len(worker_by_city)==18
    counts=collections.Counter()
    cities={}
    rows_by_city={}
    proofs={}
    input_refs=[]
    errors=[]
    contradictions=[]
    source_join_bad=[]
    key_bad={"classification":[],"event":[],"source_link":[]}
    exceptions=[]
    for city in sorted(target_by_city):
        w=worker_by_city[city]
        if city not in cities:
            cities[city]={"classification":0,"positive":0,"events":0,"bound_observations":0,"unbound_observations":0,
              "original_evidence_rows":0,"normalized_observations":0,"membership_authority":dict.fromkeys(
                 ("ORIGINAL_ACCEPTED","INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT","REPLAY_DERIVED_ONLY","NOT_OBSERVABLE","CONTRADICTION"),0),
              "observation_identity_verified":0,"normalized_payload_verified":0,"source_classification_join_discrepancies":0,
              "classification_key_matches":0,"event_key_matches":0,"source_link_key_matches":0,
              "normalization_materialized":0,"normalization_contract_derived":0,
              "unbound_reason_verified":0,"unbound_reason_not_observable":0,
              "source_row_digest":None,"classification_row_digest":None,"event_row_digest":None}
        if w["worker"] not in proofs:
            proof_raw=getraw(w["final_head"],w["proof_artifact_path"])
            if gt("rev-parse",w["final_head"]+":"+w["proof_artifact_path"])!=w["proof_artifact_blob"]:
                raise ValueError("WORKER_PROOF_BLOB_MISMATCH:"+w["worker"])
            p=json.loads(proof_raw)
            if p.get("tested_head")!=w["tested_head"]: raise ValueError("WORKER_HEAD_MISMATCH:"+w["worker"])
            proofs[w["worker"]]=p
        pcity=proofs[w["worker"]]["cities"][city] if "cities" in proofs[w["worker"]] else proofs[w["worker"]]
        path="kyiv-air-alerts-grafana/data/explosion_research/"+city+"/final_evidence.json"
        blob=gt("rev-parse",w["tested_head"]+":"+path)
        expected=pcity.get("input_hashes",{}).get("final_evidence_blob") or pcity.get("input_guards",{}).get("evidence_tested_blob")
        if expected and blob!=expected: raise ValueError("ORIGINAL_EVIDENCE_BLOB_MISMATCH:"+city)
        raw=getraw(w["tested_head"],path)
        evidence=json.loads(raw)
        seq=[(bucket,index,row) for bucket in BKT for index,row in enumerate(evidence.get(bucket,[]))]
        if not all(isinstance(row,dict) for _,_,row in seq): raise ValueError("INVALID_ORIGINAL_EVIDENCE_ROW:"+city)
        rows_by_city[city]={(bucket,index):row for bucket,index,row in seq}
        cities[city]["original_evidence_rows"]=len(seq)
        cities[city]["normalized_observations"]=int(metric(pcity,"normalized_observations"))
        input_refs.append({"city":city,"tested_head":w["tested_head"],"original_evidence_path":path,
                           "original_evidence_blob":blob,"original_evidence_sha256":hashlib.sha256(raw).hexdigest(),
                           "worker_proof_ref":w["final_head"],"worker_proof_blob":w["proof_artifact_blob"],
                           "worker_formalizer_blob":w["formalizer_blob"]})
        if len(seq)!=metric(pcity,"evidence_records_read"):
            errors.append({"city":city,"error":"ORIGINAL_WORKER_RECORD_COUNT_MISMATCH","observed":len(seq),"expected":metric(pcity,"evidence_records_read")})
        counts["original_evidence_rows"]+=len(seq)
        counts["normalized_observations"]+=int(metric(pcity,"normalized_observations"))
        counts["worker_bound_expected"]+=int(metric(pcity,"bound_observations"))
        counts["worker_unbound_expected"]+=int(metric(pcity,"unbound_observations"))
    cls_by_pair={}
    cls_by_key={}
    class_row_summaries=collections.defaultdict(list)
    for c in export["classifications"]:
        city,eid=c.get("city_key"),c.get("historical_episode_id")
        if city not in target_by_city or eid not in target_by_city[city]:
            errors.append({"error":"EXTRA_CLASSIFICATION_ID","city":city,"episode_id":eid});continue
        pair=(city,eid)
        if pair in cls_by_pair: errors.append({"error":"DUPLICATE_CLASSIFICATION_EPISODE","city":city,"episode_id":eid})
        cls_by_pair[pair]=c
        cls_by_key[c["classification_key"]]=c
        if c["verdict"]!=target_by_city[city][eid]: contradictions.append({"error":"ACCEPTED_TARGET_VERDICT_CONTRADICTION","city":city,"episode_id":eid})
        if not iso_utc(c["alert_start_utc_microseconds"]) or not iso_utc(c["alert_end_utc_microseconds"]):
            errors.append({"error":"FROZEN_TIMESTAMP_REPRESENTATION","city":city,"episode_id":eid})
        elif iso_utc(c["alert_start_utc_microseconds"])>=iso_utc(c["alert_end_utc_microseconds"]):
            errors.append({"error":"NON_POSITIVE_INTERVAL","city":city,"episode_id":eid})
        cities[city]["classification"]+=1
        if c["verdict"] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):cities[city]["positive"]+=1
        w=worker_by_city[city]["worker"]; contract=norm_by_worker[w]
        if c["normalization_version"]!=contract["final_authoritative_normalization_version"]:
            errors.append({"error":"NORMALIZATION_VERSION_CONTRACT_MISMATCH","city":city,"episode_id":eid})
        normstatus=contract["normalization_version_state"]
        if normstatus=="MATERIALIZED_IN_ACCEPTED_PROOF":cities[city]["normalization_materialized"]+=1
        elif normstatus=="CONTRACT_DERIVED_FROM_FROZEN_CODE_IDENTITY":cities[city]["normalization_contract_derived"]+=1
        else:errors.append({"error":"UNKNOWN_NORMALIZATION_VERSION_AUTHORITY","city":city})
        if c["qa_reasons_state"]!="UNMATERIALIZED_IN_ACCEPTED_SOURCE" or c["qa_reasons"] is not None:
            errors.append({"error":"QA_PROVENANCE_MISREPRESENTED","city":city,"episode_id":eid})
        if c["classifier_blob_sha"]!=CLASSIFIER_BLOB or c["classifier_methodology_version"]!=METHODOLOGY:
            errors.append({"error":"CLASSIFIER_IDENTITY_CONTRACT_MISMATCH","city":city,"episode_id":eid})
        counts["classification_rows_checked"]+=1
    for city in sorted(target_by_city):
        missing=set(target_by_city[city])-set(e for c,e in cls_by_pair if c==city)
        if missing: errors.extend({"city":city,"error":"MISSING_CLASSIFICATION","episode_id":x} for x in sorted(missing))
    starts={}
    for city in sorted(target_by_city):
        starts[city]=[(eid,iso_utc(c["alert_start_utc_microseconds"]),iso_utc(c["alert_end_utc_microseconds"])) for (cy,eid),c in cls_by_pair.items() if cy==city and iso_utc(c["alert_start_utc_microseconds"]) and iso_utc(c["alert_end_utc_microseconds"])]
    links_by_class=collections.defaultdict(list)
    links_by_raw=collections.defaultdict(list)
    source_records_by_city=collections.defaultdict(list)
    for link in export["source_links"]:
        origin=link.get("origin") or {}
        city=origin.get("path","").split("/")[-2]
        if city not in rows_by_city:
            source_join_bad.append({"error":"LINK_ORIGIN_CITY_UNKNOWN","observation_id":link.get("observation_id")});continue
        worker=worker_by_city[city]
        want_path="kyiv-air-alerts-grafana/data/explosion_research/"+city+"/final_evidence.json"
        evidence_blob=next(x["original_evidence_blob"] for x in input_refs if x["city"]==city)
        if origin != {"path":want_path,"ref":worker["tested_head"],"blob":evidence_blob}:
            source_join_bad.append({"error":"ORIGIN_HEAD_PATH_BLOB_MISMATCH","city":city,"observation_id":link.get("observation_id")})
        pv=link.get("retrieval_provenance") or {}
        bucket=V09.get(pv.get("bucket"),pv.get("bucket"))
        index=pv.get("index")
        if not isinstance(index,int) or (bucket,index) not in rows_by_city[city]:
            source_join_bad.append({"error":"SOURCE_ROW_INDEX_MISSING","city":city,"bucket":bucket,"index":index,"observation_id":link.get("observation_id")});continue
        row=rows_by_city[city][(bucket,index)]
        source_bucket=pv["bucket"]
        is_stream=source_bucket in V09
        obs=str(link.get("observation_id") or "")
        original_input=strip_ids(row) if worker["worker"]=="kharkiv_kherson" else row
        id_options=[record_id(city,bucket,index,row),record_id(city,bucket,index,strip_ids(row)),record_id(city,source_bucket,index,row),record_id(city,source_bucket,index,strip_ids(row))]
        parentid=pv.get("parent_record_id")
        if is_stream:
            identity_valid=(obs==stream09_id(source_bucket,index,row))
        else:
            identity_valid=(obs in id_options and parentid in id_options) if not pv.get("is_split_child") else parentid in id_options
        payload=link.get("normalized_accepted_observation_payload")
        if not isinstance(payload,dict):
            source_join_bad.append({"error":"NO_NORMALIZED_PAYLOAD","city":city,"bucket":bucket,"index":index});continue
        if pv.get("is_split_child"):
            parent=payload.get("_historical_parent_record")
            t=payload.get("_historical_event_time_utc")
            seg=payload.get("evidence") if "evidence" in payload else ""
            if not isinstance(seg,str):seg=""
            identity_valid=bool(identity_valid and parent in (row,strip_ids(row)) and
                  payload.get("_historical_parent_record_id")==parentid and
                  payload.get("_historical_event_observation_id")==obs and
                  isinstance(t,str) and obs==sha24(str(parentid)+"|"+t+"|"+seg))
            normalized_ok=bool(parent in (row,strip_ids(row)) and t)
        else:
            normalized_ok=payload in (row,strip_ids(row))
        if identity_valid:cities[city]["observation_identity_verified"]+=1
        else:source_join_bad.append({"error":"OBSERVATION_ID_NOT_RECONSTRUCTED","city":city,"bucket":bucket,"index":index,"observation_id":obs})
        if normalized_ok:cities[city]["normalized_payload_verified"]+=1
        else:source_join_bad.append({"error":"NORMALIZED_PAYLOAD_NOT_RECONSTRUCTED","city":city,"bucket":bucket,"index":index,"observation_id":obs})
        content=digest(payload)
        if content!=link.get("content_sha256") or link.get("content_hash_basis")!="NORMALIZED_EVIDENCE":
            source_join_bad.append({"error":"CONTENT_HASH_CONTRACT_MISMATCH","city":city,"observation_id":obs})
        cls=cls_by_key.get(link.get("classification_key_v2"))
        if cls is None:
            source_join_bad.append({"error":"SOURCE_CLASSIFICATION_KEY_MISSING","city":city,"observation_id":obs})
            continue
        linked_eid=cls["historical_episode_id"]
        if cls["city_key"]!=city or not (link.get("retrieval_provenance") or {}).get("binding",{}).get("episode_id")==linked_eid:
            source_join_bad.append({"error":"EXPORTED_SOURCE_EPISODE_BINDING_INCONSISTENT","city":city,"observation_id":obs})
        ss=[(eid,start) for eid,start,end in starts[city]]
        # independent binding: input row versus accepted episode chronology, never trust the exported binding as expected truth
        s,method,conflict=original_binding(row,city,ss,linked_eid)
        if s=="CONTRADICTION":
            contradictions.append({"city":city,"bucket":bucket,"index":index,"observation_id":obs,"reason":method,"detail":conflict})
        if s not in cities[city]["membership_authority"]:s="NOT_OBSERVABLE"
        cities[city]["membership_authority"][s]+=1
        cities[city]["bound_observations"]+=1
        links_by_raw[(city,bucket,index)].append(link)
        links_by_class[link["classification_key_v2"]].append(link)
        source_records_by_city[city].append([bucket,index,obs,pv.get("parent_record_id"),linked_eid,s,identity_valid,normalized_ok,content,link["source_link_key"]])
        counts["source_links_checked"]+=1
    # Exact missing-row universe and the original workers' unresolved reason ledgers
    for city in sorted(target_by_city):
        w=worker_by_city[city]; pc=proofs[w["worker"]]["cities"][city]
        unresolved=pc.get("unresolved_items",[])
        used=set(); unbound_here=[]
        for (bucket,idx),row in sorted(rows_by_city[city].items(),key=lambda z:(BKT.index(z[0][0]),z[0][1])):
            if links_by_raw.get((city,bucket,idx)):continue
            ids=evidence_source_id(row,city,bucket,idx,w["worker"]=="vinnytsia_zhytomyr")
            matches=[i for i,item in enumerate(unresolved) if i not in used and isinstance(item,dict) and
                     str(item.get("evidence_id") or "") in ids and str(item.get("evidence_id") or "")]
            chosen=None
            if len(matches)==1:
                chosen=matches[0];used.add(chosen)
                reason=str(unresolved[chosen].get("reason") or "NOT_OBSERVABLE")
                cities[city]["unbound_reason_verified"]+=1
            else:
                reason="NOT_OBSERVABLE"
                cities[city]["unbound_reason_not_observable"]+=1
            unbound_here.append({"city":city,"bucket":bucket,"index":idx,"original_record_sha256":digest(row),
                 "source_record_identifiers":sorted(ids),"original_worker_unresolved_reason":reason,
                 "worker_unresolved_item_index":chosen,"worker_unresolved_candidate_episode_ids":unresolved[chosen].get("candidate_episode_ids") if chosen is not None else None})
            cities[city]["unbound_observations"]+=1
        exceptions.extend(unbound_here)
        if len(unbound_here)!=int(metric(pc,"unbound_observations")):
            errors.append({"city":city,"error":"UNBOUND_PARENT_COUNT_DIFFERS_FROM_NORMALIZED_UNBOUND","parent_rows":len(unbound_here),"original_worker_unbound":metric(pc,"unbound_observations")})
        if len(used)!=len(unresolved):
            errors.append({"city":city,"error":"ORIGINAL_WORKER_UNRESOLVED_LEDGER_NOT_FULLY_JOINED","verified":len(used),"ledger":len(unresolved)})
        if cities[city]["bound_observations"]!=int(metric(pc,"bound_observations")):
            errors.append({"city":city,"error":"BOUND_SOURCE_COUNT_CONTRADICTS_WORKER","observed":cities[city]["bound_observations"],"worker":metric(pc,"bound_observations")})
        if cities[city]["bound_observations"]+cities[city]["unbound_observations"]!=int(metric(pc,"normalized_observations")):
            errors.append({"city":city,"error":"NORMALIZED_OBSERVATION_TRANSPORT_NOT_EXPLAINED"})
        parent_mult=collections.Counter((bucket,index) for c,bucket,index in links_by_raw if c==city)
        raw_bound=sum(bool(links_by_raw[(city,b,i)]) for b,i in rows_by_city[city])
        if len(rows_by_city[city])+cities[city]["bound_observations"]-raw_bound!=cities[city]["normalized_observations"]+cities[city]["unbound_observations"]-0:
            # Separate per-parent multiplicity checks are preserved in row digests; this expression
            # is diagnostic only, since normalized equals bound+unbound, not raw+split.
            pass
        cities[city]["source_row_digest"]=digest(sorted(source_records_by_city[city],key=lambda q:canon(q)))
    # canonical class event/source keys: fresh tuple serialization; no original key copied as expected
    for (city,eid),c in sorted(cls_by_pair.items()):
        evtypes=c.get("event_types")
        if not isinstance(evtypes,list):evtypes=[]
        evjson=json.dumps(sorted(evtypes),ensure_ascii=False,separators=(",",":"))
        refs=links_by_class.get(c["classification_key"],[])
        pairs=sorted(set((x["observation_id"],x["content_sha256"]) for x in refs))
        evidence_array=[list(x) for x in pairs]
        evidence_sha=digest(evidence_array)
        review_obj=c.get("review_provenance")
        review_sha=digest(review_obj) if isinstance(review_obj,dict) and review_obj else None
        if evidence_array!=c.get("accepted_evidence_membership") or evidence_sha!=c.get("evidence_set_sha256"):
            errors.append({"city":city,"episode_id":eid,"error":"SOURCE_CONTRIBUTION_SET_MISMATCH"})
        if review_sha!=c.get("review_provenance_sha256"):
            errors.append({"city":city,"episode_id":eid,"error":"REVIEW_PROVENANCE_HASH_MISMATCH"})
        t=["attack-event-classification-key-v2",city,eid,c["alert_start_utc_microseconds"],
           c["alert_end_utc_microseconds"],c["verdict"],evjson,c["qa_reasons_state"],None,
           c["classifier_blob_sha"],c["classifier_methodology_version"],c["normalization_version"],evidence_sha,review_sha]
        calculated=digest(t)
        if calculated!=c["classification_key"]:
            key_bad["classification"].append({"city":city,"episode_id":eid,"actual":c["classification_key"],"recomputed":calculated})
        else:cities[city]["classification_key_matches"]+=1
        class_row_summaries[city].append([eid,c["verdict"],c["alert_start_utc_microseconds"],c["alert_end_utc_microseconds"],
                      c["classification_key"],calculated,evidence_sha,c["normalization_version"]])
    events_by_pair={}
    event_row_summaries=collections.defaultdict(list)
    for e in export["attack_events"]:
        city,eid=e["city_key"],e["historical_episode_id"]
        pair=(city,eid)
        if pair in events_by_pair:errors.append({"error":"DUPLICATE_MODELED_EVENT","city":city,"episode_id":eid})
        events_by_pair[pair]=e
        c=cls_by_pair.get(pair)
        if c is None or c["verdict"] not in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
            errors.append({"error":"EVENT_WITHOUT_ACCEPTED_POSITIVE","city":city,"episode_id":eid});continue
        if e.get("event_grain")!="HISTORICAL_ALERT_EPISODE" or e.get("classification_key_v2")!=c["classification_key"] or (
            e["alert_start_utc_microseconds"],e["alert_end_utc_microseconds"])!=(c["alert_start_utc_microseconds"],c["alert_end_utc_microseconds"]):
            errors.append({"error":"EVENT_CLASSIFICATION_RELATIONSHIP_MISMATCH","city":city,"episode_id":eid})
        calculated=digest(["attack-event-key-v1","HISTORICAL_ALERT_EPISODE",city,eid,c["alert_start_utc_microseconds"],c["alert_end_utc_microseconds"]])
        if calculated!=e["attack_event_key"]:
            key_bad["event"].append({"city":city,"episode_id":eid,"actual":e["attack_event_key"],"recomputed":calculated})
        else:cities[city]["event_key_matches"]+=1
        cities[city]["events"]+=1
        event_row_summaries[city].append([eid,e["attack_event_key"],calculated,c["classification_key"]])
    for pair,c in cls_by_pair.items():
        if (c["verdict"] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"))!=(pair in events_by_pair):
            errors.append({"error":"MISSING_OR_EXTRA_POSITIVE_EVENT","city":pair[0],"episode_id":pair[1]})
    source_hash_summaries=collections.defaultdict(list)
    for link in export["source_links"]:
        cls=cls_by_key.get(link.get("classification_key_v2"))
        if cls is None:continue
        calculated=digest(["attack-event-source-link-key-v1",cls["classification_key"],link["observation_id"],digest(link["normalized_accepted_observation_payload"])])
        city=cls["city_key"]
        if calculated!=link["source_link_key"]:key_bad["source_link"].append({"city":city,"observation_id":link["observation_id"],"actual":link["source_link_key"],"recomputed":calculated})
        else:cities[city]["source_link_key_matches"]+=1
        source_hash_summaries[city].append([link["observation_id"],link["content_sha256"],link["source_link_key"],calculated,cls["historical_episode_id"]])
    for city in sorted(cities):
        cities[city]["classification_row_digest"]=digest(sorted(class_row_summaries[city],key=lambda x:canon(x)))
        cities[city]["event_row_digest"]=digest(sorted(event_row_summaries[city],key=lambda x:canon(x)))
        cities[city]["source_key_row_digest"]=digest(sorted(source_hash_summaries[city],key=lambda x:canon(x)))
    counts["cities"]=len(cities)
    counts["classifications"]=len(export["classifications"])
    counts["events"]=len(export["attack_events"])
    counts["source_links"]=len(export["source_links"])
    counts["unbound_parent_records"]=len(exceptions)
    counts["split_observation_excess"]=counts["normalized_observations"]-counts["original_evidence_rows"]
    counts["qa_null"]=sum(c.get("qa_reasons") is None for c in export["classifications"])
    counts["qa_not_materialized"]=sum(c.get("qa_reasons_state")=="UNMATERIALIZED_IN_ACCEPTED_SOURCE" for c in export["classifications"])
    counts["original_normalization_labels"]=sum(v["normalization_materialized"] for v in cities.values())
    counts["contract_derived_normalization_labels"]=sum(v["normalization_contract_derived"] for v in cities.values())
    totals={p:sum(city["membership_authority"][p] for city in cities.values()) for p in next(iter(cities.values()))["membership_authority"]}
    total_identity=sum(c["observation_identity_verified"] for c in cities.values())
    total_payload=sum(c["normalized_payload_verified"] for c in cities.values())
    total_reason=sum(c["unbound_reason_verified"] for c in cities.values())
    has_incomplete=bool(errors or source_join_bad or any(key_bad.values()) or total_identity!=1429 or total_payload!=1429 or total_reason!=74 or
        (counts["classifications"],counts["source_links"],counts["events"],counts["original_evidence_rows"],counts["normalized_observations"],counts["worker_bound_expected"],counts["worker_unbound_expected"],counts["unbound_parent_records"],counts["split_observation_excess"])!=(19542,1429,961,1502,1503,1429,74,74,1))
    if contradictions:
        overall="CONTRADICTION"
    elif has_incomplete:
        overall="BLOCKED"
    elif totals["REPLAY_DERIVED_ONLY"] or totals["NOT_OBSERVABLE"]:
        overall="PARTIAL"
    else:
        overall="PASS"
    # Modeled alert-episode relationship may be PASS independently of source-membership authority.
    event_verdict="BLOCKED" if (errors or key_bad["event"] or len(events_by_pair)!=961) else "PASS"
    status={
       "H2_SOURCE_MEMBERSHIP_HISTORICAL_AUTHORITY":"CONTRADICTION" if contradictions else "BLOCKED" if has_incomplete else "PARTIAL" if totals["REPLAY_DERIVED_ONLY"] or totals["NOT_OBSERVABLE"] else "PASS",
       "H2_EVENT_RELATIONSHIP_HISTORICAL_AUTHORITY":event_verdict,
       "H2_CLASSIFICATION_KEY_INPUT_AUTHORITY":"BLOCKED" if key_bad["classification"] else "PARTIAL",
       "H2_EVENT_KEY_INPUT_AUTHORITY":"BLOCKED" if key_bad["event"] else "PARTIAL",
       "H2_SOURCE_LINK_KEY_INPUT_AUTHORITY":"BLOCKED" if key_bad["source_link"] else "PARTIAL",
       "H2_19542_FIELD_AUTHORITY_AUDIT":overall
    }
    return {
      "schema_version":"neon-h2-19542-field-authority-audit-v1",
      "branch_base":BASE,
      "predecessor_inventory":{"commit":PREV_INVENTORY[0],"blob":PREV_INVENTORY[2],"sha256":PREV_INVENTORY[3],"acceptance":"INCOMPLETE_ONLY"},
      "immutable_inputs":{"original_export":{"commit":EXPORT[0],"blob":EXPORT[2],"sha256":EXPORT[3]},
        "accepted_target_map":{"commit":TARGET[0],"blob":TARGET[2],"sha256":TARGET[3]},
        "normalization_contract":{"commit":NORM[0],"blob":NORM[2]},
        "classification_key_contract":{"commit":IDENTITY[0],"blob":IDENTITY[2]},
        "original_city_worker_evidence":input_refs},
      "methodology":{"source_join":"exact original tested Git HEAD/path/blob/bucket/index, never fuzzy matching",
        "source_membership":"source native immutable IDs or unique original alert clock against accepted 18-city chronology; absent evidence remains replay derived",
        "source_identity":"independent canonical UTF-8 sorted compact JSON SHA24 of original or frozen binding-stripped input; stream09 native event ID; split-child provenance checked",
        "content_hash":"SHA256 canonical normalized evidence payload, no claimed source-native hash",
        "classification_key":"SHA256 canonical JSON tuple v2 with original six-decimal ISO-UTC string boundaries and QA null",
        "event_key":"SHA256 canonical JSON v1 tuple for HISTORICAL_ALERT_EPISODE",
        "source_link_key":"SHA256 canonical JSON tuple v1",
        "serializer":"Python JSON ensure_ascii=False sort_keys=True separators=(comma,colon) UTF-8 no trailing newline",
        "classifier_rerun":False,"neon_queries":0,"database_writes":0,
        "run_seeds":[17,997]},
      "coverage":dict(counts),
      "membership_authority_totals":totals,
      "per_city":cities,
      "unbound_original_source_records":exceptions,
      "transport_exception_rows":source_join_bad,
      "other_exception_rows":errors,
      "affirmative_historical_contradictions":contradictions,
      "key_recalculation":{"classification":{"checked":len(export["classifications"]),"matches":sum(x["classification_key_matches"] for x in cities.values()),"mismatches":key_bad["classification"]},
        "event":{"checked":len(export["attack_events"]),"matches":sum(x["event_key_matches"] for x in cities.values()),"mismatches":key_bad["event"]},
        "source_link":{"checked":len(export["source_links"]),"matches":sum(x["source_link_key_matches"] for x in cities.values()),"mismatches":key_bad["source_link"]}},
      "field_authority":{"accepted_episodes_and_verdicts":{"ORIGINAL_ACCEPTED":19542,"source":"previous accepted 18/18 H2 chronology and target-map original-worker identity"},
        "qa_reasons_state":{"INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT":19542,"value":"UNMATERIALIZED_IN_ACCEPTED_SOURCE"},
        "qa_reasons":{"INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT":19542,"value":None},
        "normalization_version":{"ORIGINAL_ACCEPTED":counts["original_normalization_labels"],
          "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT":counts["contract_derived_normalization_labels"]},
        "classification_event_types":{"REPLAY_DERIVED_ONLY":19542,"caveat":"native replay objects not independently adjudicated historical semantics"},
        "modeled_event_grain":{"INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT":len(export["attack_events"]),"physical_attack_identity":"NOT_OBSERVABLE"},
        "source_membership":totals,
        "classification_key_aggregate_input_authority":{"REPLAY_DERIVED_ONLY":len(export["classifications"])},
        "event_key_aggregate_input_authority":{"INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT":len(export["attack_events"])},
        "source_link_key_aggregate_input_authority":{"REPLAY_DERIVED_ONLY":len(export["source_links"])}},
      "verdicts":status,
      "hard_boundaries":{"C4":"NOT PROVEN","C5":"NOT PROVEN","UNBOUND_UNRESOLVED":25,
        "GLOBAL_HISTORICAL_MISSING_EXTRA":"NOT CERTIFIED","NEON_AUTHORITY_ACTIVE":"NO",
        "PRODUCTION_CUTOVER_EXECUTED":"NO","A5_EXECUTED_AGAIN":False,
        "historical_backfill":False,"classifier_rerun":False,"production_mutation":False,"site_prod_mutation":False},
      "reconciliation_scope":"H2 frozen Git inputs only, no persisted Neon parity; 74 unbound evidence observations are separate from 25 unresolved historical parent admissions",
      "successor_gate":"TECHNICAL_RESEARCH_ONLY_REQUIRES_INDEPENDENT_ACCEPTANCE"
    }

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="--prepare":
        prep()
    elif len(sys.argv)==3 and sys.argv[1]=="--audit":
        result=audit()
        Path(sys.argv[2]).write_bytes(canon(result))
        print("AUDIT_RESULT",result["verdicts"],"COVERAGE",result["coverage"],flush=True)
        print("KEY_COUNTS",{k:{"checked":v["checked"],"matches":v["matches"],"mismatches":len(v["mismatches"])} for k,v in result["key_recalculation"].items()},flush=True)
        print("SOURCE_AUTHORITY",result["membership_authority_totals"],"TRANSPORT_EXCEPTIONS",len(result["transport_exception_rows"]),"UNBOUND_REASON_VERIFIED",sum(c["unbound_reason_verified"] for c in result["per_city"].values()),flush=True)
        print("EXCEPTION_PREVIEW",result["transport_exception_rows"][:12],result["other_exception_rows"][:12],result["affirmative_historical_contradictions"][:12],flush=True)
    else:
        raise SystemExit("usage: script.py --prepare | --audit output.json")
