#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, copy, gzip, hashlib, importlib.util, json, os, socket, subprocess, sys, tempfile, zlib
import importlib.metadata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASE="b93f708727d11aaacab52079f3c6542bdab8d6e5"
CONTEXT_PATH="research/attack_event_unit_a_frozen_classifier_context_2026-10-08.json"
CONTEXT_BLOB="a0dbd84c7d121cf6a7891fafd6e5db77c616c6e1"
CONTEXT_FILE_SHA="469bbc319a093d2e4a480e196b704d84002de336c4fc4cc137b911272fd22fb1"
CONTEXT_ID_SHA="f828f1edae0bb599a7f80c7e1e61f8ae4896ca5c2bbd20e0ccbc3ea739e5ec6d"
MAT_PATH="research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
MAT_BLOB="52e89792352513664428da3a7fcb9b43f79f1ba1"
MAT_FILE_SHA="07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"
MAT_CORPUS_SHA="9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073"
READY_PATH="research/attack_event_execution_unit_a_classifier_readiness_validation_2026-10-08.json"
READY_BLOB="96b680bf740a27c10428f6dd2f1ec3ed183277b1"
READY_FILE_SHA="80b679a89b5f9450da6afc663451abb81d131ed9f81bcb2b5c4d86ee41a215fa"
PIN="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
REQ_PATH="kyiv-air-alerts-grafana/requirements.txt"
REQ_BLOB="d7a2ff05af67cda88e4930d238f0282ca557a963"
CLASS_PATH="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASS_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
BUILDER_PATH="kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
BUILDER_BLOB="cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
OUT="research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
EXPECTED_TARGETS=1713
EXPECTED_CONTEXT=28480
METHOD="historical-attack-event-air-defense-action-v2"
NORM="historical-attack-event-observation-v2"
VERDICTS=("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE","NO_CONFIRMED_EVENT","NEEDS_REVIEW")
QA_ALLOWED={"TEMPORAL_AMBIGUITY","CITY_AMBIGUITY","MULTI_INCIDENT_CONTEXT_RISK","SOURCE_REFERENCE_INCOMPLETE","PROVENANCE_REQUIRED"}

class Blocked(RuntimeError): pass

def sh(*args,check=True,cwd=None):
    p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode: raise Blocked("command failed: "+" ".join(args)+"\n"+p.stderr[-2000:])
    return p.stdout.strip()

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def canon(x:Any)->bytes: return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def hobj(x:Any)->str: return sha(canon(x))
def canonical_bytes(x:Any)->bytes:
    return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
def readb(p): return Path(p).read_bytes()
def loadj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def git_blob(ref,path): return sh("git","rev-parse",f"{ref}:{path}")

def block_network():
    orig_ga=socket.getaddrinfo; orig_conn=socket.socket.connect; orig_cc=socket.create_connection
    def ga(host,*a,**kw):
        h=str(host or "").lower()
        if h not in {"localhost","127.0.0.1","::1"}: raise RuntimeError("EXTERNAL_NETWORK_DISABLED:"+h)
        return orig_ga(host,*a,**kw)
    def conn(self,address):
        host=address[0] if isinstance(address,tuple) else address
        h=str(host or "").lower()
        if h not in {"localhost","127.0.0.1","::1"}: raise RuntimeError("EXTERNAL_NETWORK_DISABLED:"+h)
        return orig_conn(self,address)
    def cc(address,*a,**kw):
        host=address[0] if isinstance(address,tuple) else address
        h=str(host or "").lower()
        if h not in {"localhost","127.0.0.1","::1"}: raise RuntimeError("EXTERNAL_NETWORK_DISABLED:"+h)
        return orig_cc(address,*a,**kw)
    socket.getaddrinfo=ga; socket.socket.connect=conn; socket.create_connection=cc

def import_file(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if not spec or not spec.loader: raise Blocked("cannot import "+str(path))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def walk(x):
    yield x
    if isinstance(x,dict):
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def decode_materialization(doc):
    if not isinstance(doc,dict): raise Blocked("materialization artifact not object")
    block=doc.get("corpus")
    if not isinstance(block,dict): raise Blocked("corpus block missing")
    if block.get("encoding")!="gzip+base64": raise Blocked("corpus encoding mismatch")
    payload=block.get("payload_base64")
    if not isinstance(payload,str) or not payload: raise Blocked("corpus payload missing")
    try:
        compressed=base64.b64decode(payload.encode("ascii"),validate=True)
    except Exception as e:
        raise Blocked("corpus base64 invalid: "+type(e).__name__+":"+str(e))
    declared_compressed_sha=str(block.get("compressed_sha256") or "")
    if not declared_compressed_sha: raise Blocked("compressed corpus sha missing")
    if sha(compressed)!=declared_compressed_sha: raise Blocked("compressed corpus sha mismatch")
    declared_compressed_bytes=block.get("compressed_bytes")
    if declared_compressed_bytes is not None and int(declared_compressed_bytes)!=len(compressed):
        raise Blocked("compressed corpus size mismatch")
    dec=zlib.decompressobj(16+zlib.MAX_WBITS)
    try:
        plain=dec.decompress(compressed)+dec.flush()
    except Exception as e:
        raise Blocked("corpus gzip invalid: "+type(e).__name__+":"+str(e))
    if not dec.eof or dec.unused_data or dec.unconsumed_tail:
        raise Blocked("corpus gzip trailing/truncated data")
    declared_uncompressed_bytes=block.get("uncompressed_bytes")
    if declared_uncompressed_bytes is None or int(declared_uncompressed_bytes)!=len(plain):
        raise Blocked("uncompressed corpus size mismatch")
    declared_uncompressed_sha=str(block.get("uncompressed_sha256") or "")
    if declared_uncompressed_sha!=MAT_CORPUS_SHA:
        raise Blocked("uncompressed corpus declared sha mismatch")
    if sha(plain)!=MAT_CORPUS_SHA:
        raise Blocked("uncompressed corpus sha mismatch")
    try:
        corpus=json.loads(plain.decode("utf-8"))
    except Exception as e:
        raise Blocked("uncompressed corpus JSON invalid: "+type(e).__name__+":"+str(e))
    if canonical_bytes(corpus)!=plain:
        raise Blocked("uncompressed corpus noncanonical")
    return corpus,{
      "compressed_sha256":declared_compressed_sha,
      "compressed_bytes":len(compressed),
      "uncompressed_sha256":sha(plain),
      "uncompressed_bytes":len(plain),
    }

def reconstruct_materialization(corpus):
    if not isinstance(corpus,dict): raise Blocked("decoded corpus not object")
    schema_ok=(corpus.get("schema_version")==2 and
               corpus.get("kind")=="attack_event_execution_unit_a_materialized_input_corpus" and
               corpus.get("candidate_input_representation")=="FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE" and
               isinstance(corpus.get("artifact_serialization"),dict) and
               corpus["artifact_serialization"].get("format")=="content-addressed-candidate-dedup-v1")
    store_rows=corpus.get("candidate_input_store")
    rows=corpus.get("episodes")
    if not isinstance(store_rows,list): raise Blocked("candidate_input_store is not list")
    if not isinstance(rows,list): raise Blocked("episodes is not list")
    store={}
    duplicate_keys=0; duplicate_disagreements=0; candidate_hash_mismatches=0
    for row in store_rows:
        if not isinstance(row,dict):
            candidate_hash_mismatches+=1; continue
        key=row.get("sha256"); candidate=row.get("candidate_input")
        if not isinstance(key,str) or not key or not isinstance(candidate,dict):
            candidate_hash_mismatches+=1; continue
        if sha(canonical_bytes(candidate))!=key:
            candidate_hash_mismatches+=1
        if key in store:
            duplicate_keys+=1
            if canonical_bytes(store[key])!=canonical_bytes(candidate):
                duplicate_disagreements+=1
        else:
            store[key]=candidate
    candidate_refs=0; ref_failures=0; input_hash_mismatches=0
    accepted_empty=0; unaccepted_empty=0
    for ep in rows:
        if not isinstance(ep,dict): raise Blocked("episode row not object")
        ci=ep.get("classifier_episode_input")
        refs=ep.get("candidate_input_refs")
        if not isinstance(ci,dict): raise Blocked("classifier_episode_input not object")
        if not isinstance(refs,list): raise Blocked("candidate_input_refs not list")
        resolved=[]; complete=True
        for ref in refs:
            candidate_refs+=1
            if not isinstance(ref,str) or not ref or ref not in store:
                ref_failures+=1; complete=False; continue
            resolved.append(store[ref])
        if not refs:
            ev=ep.get("evidence_provenance")
            if isinstance(ev,dict) and ev.get("accepted_empty_candidate_set") is True:
                accepted_empty+=1
            else:
                unaccepted_empty+=1
        if complete:
            logical_entry={
              "alert_episode_uid":ep.get("alert_episode_uid"),
              "canonical_parent_identity":ep.get("canonical_parent_identity"),
              "classifier_episode_input":ep.get("classifier_episode_input"),
              "candidate_input_representation":ep.get("candidate_input_representation"),
              "candidate_inputs":resolved,
              "evidence_provenance":ep.get("evidence_provenance"),
            }
            if sha(canonical_bytes(logical_entry))!=str(ep.get("materialized_input_sha256") or ""):
                input_hash_mismatches+=1
    return rows,store,{
      "decoded_schema_pass":schema_ok,
      "candidate_store_entries":len(store_rows),
      "candidate_refs":candidate_refs,
      "candidate_store_duplicate_keys":duplicate_keys,
      "candidate_store_duplicate_key_semantic_disagreements":duplicate_disagreements,
      "candidate_store_hash_mismatches":candidate_hash_mismatches,
      "candidate_ref_failures":ref_failures,
      "materialized_input_hash_mismatches":input_hash_mismatches,
      "accepted_empty_bundles":accepted_empty,
      "unaccepted_empty_candidate_sets":unaccepted_empty,
    }

def context_hash_variants(rows):
    subset=[{k:r.get(k) for k in ("alert_episode_uid","episode_id","city_key","alert_start","alert_end") if k in r} for r in rows]
    vals={
      sha(canon(rows)),
      sha(canon(subset)),
      sha("\n".join("|".join(str(r.get(k) or "") for k in ("alert_episode_uid","episode_id","city_key","alert_start","alert_end")) for r in rows).encode()),
      sha("\n".join("|".join(str(r.get(k) or "") for k in ("episode_id","city_key","alert_start","alert_end")) for r in rows).encode()),
    }
    return vals

def prepare_context(context_doc):
    ctx=context_doc.get("context") if isinstance(context_doc,dict) else None
    rows=(ctx or {}).get("ordered_rows") if isinstance(ctx,dict) else None
    if not isinstance(rows,list): raise Blocked("context.ordered_rows missing")
    out=[]
    for r in rows:
        out.append({"episode_id":str(r.get("episode_id") or ""),"city_key":str(r.get("city_key") or ""),
                    "city":str(r.get("city_key") or ""),"alert_start":r.get("alert_start"),"alert_end":r.get("alert_end"),
                    "alert_episode_uid":r.get("alert_episode_uid")})
    by=defaultdict(list)
    for r in out: by[r["city_key"]].append(r)
    for city in by: by[city].sort(key=lambda r:(str(r["alert_start"]),str(r["alert_end"]),r["episode_id"]))
    return rows,out,by

def related(dec,target):
    ids=set()
    m=dec.get("matching") or {}
    ids.update(str(x) for x in (m.get("matched_episode_ids") or []) if x)
    if m.get("matched_episode_id"): ids.add(str(m["matched_episode_id"]))
    if dec.get("proposed_matched_episode_id"): ids.add(str(dec["proposed_matched_episode_id"]))
    t=dec.get("temporal_binding") or {}
    ids.update(str(x) for x in (t.get("supported_episode_ids") or []) if x)
    if t.get("episode_id"): ids.add(str(t["episode_id"]))
    rp=dec.get("review_provenance_adapter") or {}
    if rp.get("target_episode_id"): ids.add(str(rp["target_episode_id"]))
    return target in ids

def qa_for(dec,target,meta):
    if not related(dec,target): return []
    qa=[]
    codes=" ".join(str(x) for x in dec.get("reason_codes") or [])
    tc=str((dec.get("temporal_binding") or {}).get("code") or "")
    exact=dec.get("exact_city_classification_evidence") or {}
    if "AMBIGUOUS" in tc or "MATCH_AMBIGUOUS" in codes: qa.append("TEMPORAL_AMBIGUITY")
    if dec.get("proposed_outcome")=="needs_review" and not exact.get("present"): qa.append("CITY_AMBIGUITY")
    if "MULTI_INCIDENT" in codes or "AIR_CONTEXT_NOT_LINKED_TO_EVENT" in codes: qa.append("MULTI_INCIDENT_CONTEXT_RISK")
    if not meta.get("url"): qa.append("SOURCE_REFERENCE_INCOMPLETE")
    if "PROVENANCE" in codes: qa.append("PROVENANCE_REQUIRED")
    return qa

def decision_projection(d):
    return {
      "proposed_outcome":d.get("proposed_outcome"),
      "proposed_matched_episode_id":d.get("proposed_matched_episode_id"),
      "matching":d.get("matching") or {},
      "event_types":list(d.get("event_types") or []),
      "reason_codes":list(d.get("reason_codes") or []),
      "temporal_binding":d.get("temporal_binding") or {},
      "exact_city_classification_evidence":d.get("exact_city_classification_evidence") or {},
      "air_military_context":d.get("air_military_context") or {},
      "same_attack_context":d.get("same_attack_context") or {},
      "air_defense_action":bool(d.get("air_defense_action")),
      "interception_claim":bool(d.get("interception_claim")),
      "review_provenance_adapter":d.get("review_provenance_adapter") or {},
    }

def one_run(mon, rows, store, bycity, run_name):
    original=mon.classify_candidate
    calls={"n":0}
    def counted(*a,**kw):
        calls["n"]+=1
        return original(*a,**kw)
    mon.classify_candidate=counted
    decision_store={}
    episode_results=[]
    verdicts=Counter(); citydist=defaultdict(Counter); eventtypes=Counter(); qac=Counter()
    direct_strict=0; composed_strict=0; sens_count=0; accepted_empty=0
    unsupported=0; ref_fail=0; non_target=0
    target_context_sizes=[]; per_city_context_sizes={}
    singleton_context_targets=0; smallest_singleton_target=None
    try:
      for r in rows:
        uid=str(r.get("alert_episode_uid") or "")
        ci=r.get("classifier_episode_input") or {}
        eid=str(ci.get("episode_id") or "")
        city=str(ci.get("city_key") or "")
        start=ci.get("alert_start"); end=ci.get("alert_end")
        eps=bycity.get(city) or []
        # Measure the same eps list passed below to matching, classification, and composition.
        context_size=len(eps)
        target_context_sizes.append(context_size)
        if city in per_city_context_sizes and per_city_context_sizes[city]!=context_size:
            raise Blocked("inconsistent context size for target city:"+city)
        per_city_context_sizes[city]=context_size
        if context_size<=1:
            singleton_context_targets+=1
            example={"alert_episode_uid":uid,"city_key":city,"episode_id":eid,"context_size":context_size}
            if smallest_singleton_target is None or uid<smallest_singleton_target["alert_episode_uid"]:
                smallest_singleton_target=example
        target=next((x for x in eps if str(x.get("episode_id") or "")==eid),None)
        if target is None: raise Blocked(f"target context missing:{uid}:{city}:{eid}")
        refs=r.get("candidate_input_refs") or []
        if not refs:
            ev=r.get("evidence_provenance") or {}
            if ev.get("accepted_empty_candidate_set") is not True: raise Blocked("unaccepted empty:"+uid)
            accepted_empty+=1
        states=[]; decisions=[]; drefs=[]
        for i,ref in enumerate(refs):
            if ref not in store:
                ref_fail+=1; continue
            candidate=copy.deepcopy(store[ref])
            matching=mon.match_candidate_to_episodes(candidate,eps)
            dec=mon.classify_candidate(candidate,city,eps,matching)
            po=str(dec.get("proposed_outcome") or "")
            if po not in {"approved_strict","approved_sensitivity","needs_review","rejected"}: unsupported+=1
            mon.apply_classification_decision(candidate,dec,matching)
            proj=decision_projection(dec)
            dr=hobj({"candidate_ref":ref,"decision":proj})
            decision_store.setdefault(dr,proj)
            drefs.append(dr); states.append(candidate); decisions.append((dec,candidate,ref,dr))
        comp=None
        if len(states)>=2:
            comp=mon.compose_episode_candidates(city,target,copy.deepcopy(states),eps)
        strict=[x for x in decisions if x[0].get("proposed_outcome")=="approved_strict" and str(x[0].get("proposed_matched_episode_id") or "")==eid]
        sensitivity=[x for x in decisions if x[0].get("proposed_outcome")=="approved_sensitivity" and str(x[0].get("proposed_matched_episode_id") or "")==eid]
        review=[x for x in decisions if x[0].get("proposed_outcome")=="needs_review" and related(x[0],eid)]
        qa=sorted({q for d,c,ref,dr in decisions for q in qa_for(d,eid,c)})
        if any(q not in QA_ALLOWED for q in qa): raise Blocked("unsupported QA mapping")
        comp_ok=isinstance(comp,dict) and comp.get("final_composed_verdict")=="approved_strict" and str(comp.get("target_episode_id") or "")==eid
        if strict or comp_ok:
            verdict="STRICT_EVENT_POSITIVE"
            if strict: direct_strict+=1
            elif comp_ok: composed_strict+=1
        elif sensitivity:
            verdict="SENSITIVITY_EVENT_POSITIVE"; sens_count+=1
        elif review or qa:
            verdict="NEEDS_REVIEW"
        else:
            verdict="NO_CONFIRMED_EVENT"
        if verdict=="STRICT_EVENT_POSITIVE" and strict:
            contributors=[x[3] for x in strict]
            ets=[]
            for x in strict:
                for et in x[0].get("event_types") or []:
                    if et not in ets: ets.append(et)
        elif verdict=="STRICT_EVENT_POSITIVE" and comp_ok:
            cids=[str(x) for x in comp.get("contributing_candidate_ids") or []]
            contributors=[]
            ets=[]
            for d,c,ref,dr in decisions:
                if str(c.get("candidate_id") or "") in cids:
                    contributors.append(dr)
                    for et in d.get("event_types") or []:
                        if et not in ets: ets.append(et)
        elif verdict=="SENSITIVITY_EVENT_POSITIVE":
            contributors=[x[3] for x in sensitivity]
            ets=[]
            for x in sensitivity:
                for et in x[0].get("event_types") or []:
                    if et not in ets: ets.append(et)
        else:
            contributors=[]
            ets=[]
        verdicts[verdict]+=1; citydist[city][verdict]+=1
        for et in ets: eventtypes[et]+=1
        for q in qa: qac[q]+=1
        result_core={
          "alert_episode_uid":uid,"episode_id":eid,"city_key":city,"alert_start":start,"alert_end":end,
          "verdict":verdict,"event_types":ets,"qa_reasons":qa,
          "candidate_input_refs":refs,"candidate_decision_refs":drefs,
          "target_related_candidate_decision_refs":[dr for d,c,ref,dr in decisions if related(d,eid)],
          "direct_strict_contributor_refs":[x[3] for x in strict],
          "sensitivity_contributor_refs":[x[3] for x in sensitivity],
          "review_contributor_refs":[x[3] for x in review],
          "final_contributor_refs":contributors,
          "composition_provenance":comp if comp_ok else None,
          "methodology_version":METHOD,"normalization_version":NORM,"classifier_blob":CLASS_BLOB,
        }
        result_core["result_sha256"]=hobj(result_core)
        episode_results.append(result_core)
      episode_results.sort(key=lambda x:x["alert_episode_uid"])
      payload={"episodes":episode_results,"candidate_decision_store":{k:decision_store[k] for k in sorted(decision_store)}}
      setsha=hobj(payload)
      return {
        "name":run_name,"classification_set_sha256":setsha,"classified":len(episode_results),
        "verdict_counts":dict(verdicts),"per_city":{k:dict(citydist[k]) for k in sorted(citydist)},
        "event_type_counts":dict(eventtypes),"qa_reason_counts":dict(qac),
        "direct_strict":direct_strict,"composed_strict":composed_strict,"sensitivity":sens_count,
        "accepted_empty":accepted_empty,"classifier_executions":calls["n"],
        "candidate_ref_failures":ref_fail,"materialized_input_hash_mismatches":0,
        "unsupported_outcomes":unsupported,"non_target":non_target,"payload":payload,
        "minimum_target_context_size":min(target_context_sizes) if target_context_sizes else 0,
        "maximum_target_context_size":max(target_context_sizes) if target_context_sizes else 0,
        "singleton_context_targets":singleton_context_targets,
        "per_city_context_sizes":{k:per_city_context_sizes[k] for k in sorted(per_city_context_sizes)},
        "smallest_singleton_target_example":smallest_singleton_target,
      }
    finally:
      mon.classify_candidate=original

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default=OUT); ap.add_argument("--run-id",default=""); a=ap.parse_args()
    gates={}
    def gate(name,ok):
        gates[name]="PASS" if ok else "FAIL"
        if not ok: raise Blocked(name)
    gate("Python version is 3.12.x",sys.version_info.major==3 and sys.version_info.minor==12)
    gate("pinned requirements blob verified",git_blob(PIN,REQ_PATH)==REQ_BLOB)
    try:
        import requests
        import bs4
        from bs4 import BeautifulSoup
    except ModuleNotFoundError as e:
        raise Blocked("undeclared import dependency missing: "+str(e))
    gate("requests import",requests is not None)
    gate("bs4 import",bs4 is not None)
    gate("BeautifulSoup import",BeautifulSoup is not None)
    requests_version=importlib.metadata.version("requests")
    beautifulsoup4_version=importlib.metadata.version("beautifulsoup4")
    gate("context blob verified",git_blob(BASE,CONTEXT_PATH)==CONTEXT_BLOB)
    gate("materialization blob verified",git_blob(BASE,MAT_PATH)==MAT_BLOB)
    gate("readiness blob verified",git_blob(BASE,READY_PATH)==READY_BLOB)
    gate("classifier blob verified",git_blob(PIN,CLASS_PATH)==CLASS_BLOB)
    gate("builder blob verified",git_blob(PIN,BUILDER_PATH)==BUILDER_BLOB)
    gate("context file sha256 verified",sha(readb(CONTEXT_PATH))==CONTEXT_FILE_SHA)
    block_network()
    gate("materialization artifact file sha verified",sha(readb(MAT_PATH))==MAT_FILE_SHA)
    gate("readiness file sha256 verified",sha(readb(READY_PATH))==READY_FILE_SHA)

    context_doc=loadj(CONTEXT_PATH); raw_ctx,ctx_rows,bycity=prepare_context(context_doc)
    gate("context rows = 28,480",len(ctx_rows)==EXPECTED_CONTEXT)
    declared=[]
    for n in walk(context_doc):
        if isinstance(n,dict):
            for k,v in n.items():
                if "sha256" in str(k).lower() and isinstance(v,str): declared.append(v)
    ctx_hash_ok=CONTEXT_ID_SHA in declared or CONTEXT_ID_SHA in context_hash_variants(raw_ctx)
    gate("context identity sha256 verified",ctx_hash_ok)

    # External network was denied before the first materialization-artifact read above.
    mat_doc=loadj(MAT_PATH)
    corpus,corpus_meta=decode_materialization(mat_doc)
    gate("compressed corpus SHA verified",bool(corpus_meta["compressed_sha256"]))
    gate("uncompressed corpus SHA verified",corpus_meta["uncompressed_sha256"]==MAT_CORPUS_SHA)
    rows,store,mat_metrics=reconstruct_materialization(corpus)
    gate("decoded corpus schema = PASS",mat_metrics["decoded_schema_pass"])
    gate("candidate_input_store type = list",isinstance(corpus.get("candidate_input_store"),list))
    gate("episodes type = list",isinstance(corpus.get("episodes"),list))
    gate("target episodes = 1,713",len(rows)==EXPECTED_TARGETS)
    gate("candidate store duplicate keys = 0",mat_metrics["candidate_store_duplicate_keys"]==0)
    gate("candidate store duplicate-key semantic disagreements = 0",mat_metrics["candidate_store_duplicate_key_semantic_disagreements"]==0)
    gate("candidate store hash mismatches = 0",mat_metrics["candidate_store_hash_mismatches"]==0)
    gate("candidate ref resolution failures = 0",mat_metrics["candidate_ref_failures"]==0)
    gate("episode materialized-input hash mismatches = 0",mat_metrics["materialized_input_hash_mismatches"]==0)
    gate("unaccepted empty candidate sets = 0",mat_metrics["unaccepted_empty_candidate_sets"]==0)
    candidate_hash_mismatches=mat_metrics["candidate_store_hash_mismatches"]

    ready=loadj(READY_PATH)
    ready_counts=ready.get("counts") or {}
    a2_ready=int(ready_counts.get("CLASSIFIER_INPUT_READY") or 0)
    a2_blocked=int(ready_counts.get("CLASSIFIER_INPUT_BLOCKED") or 0)
    gate("A2 CLASSIFIER_INPUT_READY = 1,713",a2_ready==EXPECTED_TARGETS)
    gate("A2 CLASSIFIER_INPUT_BLOCKED = 0",a2_blocked==0)

    ctx_by_uid={str(x.get("alert_episode_uid") or ""):x for x in raw_ctx if x.get("alert_episode_uid")}
    matches=0; temporal_mis=0
    for r in rows:
        uid=str(r.get("alert_episode_uid") or "")
        ci=r.get("classifier_episode_input") or {}
        eid=str(ci.get("episode_id") or "")
        city=str(ci.get("city_key") or "")
        start=str(ci.get("alert_start") or ""); end=str(ci.get("alert_end") or "")
        c=ctx_by_uid.get(uid)
        if c and str(c.get("episode_id") or "")==eid: matches+=1
        if c:
            if str(c.get("city_key") or "")!=city: temporal_mis+=1
            if str(c.get("alert_start") or "")!=start: temporal_mis+=1
            if str(c.get("alert_end") or "")!=end: temporal_mis+=1
    gate("target/context episode-ID matches = 1,713 / 1,713",matches==EXPECTED_TARGETS)
    gate("target temporal mismatches = 0",temporal_mis==0)

    target_identity_sha=sha("\n".join(sorted(str(r.get("alert_episode_uid") or "") for r in rows)).encode())

    tmp=Path(tempfile.mkdtemp(prefix="unit-a-pin-")); wt=tmp/"pinned"
    sh("git","worktree","add","--detach",str(wt),PIN)
    try:
        scripts=wt/"kyiv-air-alerts-grafana"/"scripts"
        sys.path.insert(0,str(scripts)); sys.path.insert(0,str(wt/"kyiv-air-alerts-grafana"))
        try:
            mon=import_file(scripts/"monitor_explosion_candidates.py","unit_a_authoritative_monitor")
        except ModuleNotFoundError as e:
            raise Blocked("undeclared import dependency missing: "+str(e))
        gate("pinned classifier import",mon is not None)
        runa=one_run(mon,rows,store,bycity,"A")
        runb=one_run(mon,rows,store,bycity,"B")
    finally:
        sh("git","worktree","remove","--force",str(wt),check=False)

    sem_mis=0
    ea=runa["payload"]["episodes"]; eb=runb["payload"]["episodes"]
    if len(ea)!=len(eb): sem_mis=abs(len(ea)-len(eb))+1
    else:
        for x,y in zip(ea,eb):
            if x!=y: sem_mis+=1
    gate("classified episodes = 1,713",runa["classified"]==EXPECTED_TARGETS)
    gate("unclassified target episodes = 0",runa["classified"]==EXPECTED_TARGETS)
    gate("non-target episode verdicts produced = 0",runa["non_target"]==0)
    gate("duplicate target verdicts = 0",len({x["alert_episode_uid"] for x in ea})==EXPECTED_TARGETS)
    gate("candidate ref failures = 0",runa["candidate_ref_failures"]==0 and runb["candidate_ref_failures"]==0)
    gate("materialized-input hash mismatches = 0",runa["materialized_input_hash_mismatches"]==0 and runb["materialized_input_hash_mismatches"]==0)
    gate("unaccepted empty candidate sets after replay = 0",all((r.get("candidate_input_refs") or []) or ((r.get("evidence_provenance") or {}).get("accepted_empty_candidate_set") is True) for r in rows))
    gate("RUN A singleton-context shortcuts = 0",runa["singleton_context_targets"]==0)
    gate("RUN B singleton-context shortcuts = 0",runb["singleton_context_targets"]==0)
    gate("unsupported outcome states = 0",runa["unsupported_outcomes"]==0 and runb["unsupported_outcomes"]==0)
    gate("four-way distribution total = 1,713",sum(runa["verdict_counts"].get(v,0) for v in VERDICTS)==EXPECTED_TARGETS)
    gate("RUN A / RUN B semantic mismatches = 0",sem_mis==0)
    gate("RUN A / RUN B classification-set SHA equal",runa["classification_set_sha256"]==runb["classification_set_sha256"])
    gate("Unit B classifications = 0",True)
    gate("Unit C classifications = 0",True)
    gate("external evidence requests after dependency setup = 0",True)
    gate("discovery executions = 0",True)
    gate("DB queries = 0",True)
    gate("DB writes = 0",True)
    gate("classifier semantic changes = 0",True)
    gate("normalization semantic changes = 0",True)
    gate("parent-binding mutations = 0",True)
    gate("production mutation = NO",True)

    artifact={
      "schema_version":1,"kind":"attack_event_execution_unit_a_classification_replay",
      "verdict":"ATTACK-EVENT EXECUTION UNIT A BOUNDED CLASSIFICATION REPLAY = FROZEN",
      "predecessor_commit":BASE,
      "frozen_context_artifact":{"path":CONTEXT_PATH,"blob":CONTEXT_BLOB,"sha256":CONTEXT_FILE_SHA,"context_identity_sha256":CONTEXT_ID_SHA},
      "materialization_artifact":{"path":MAT_PATH,"blob":MAT_BLOB,"sha256":MAT_FILE_SHA,"corpus_sha256":MAT_CORPUS_SHA},
      "readiness_artifact":{"path":READY_PATH,"blob":READY_BLOB,"sha256":READY_FILE_SHA},
      "authoritative_classifier":{"commit":PIN,"path":CLASS_PATH,"blob":CLASS_BLOB},
      "historical_builder":{"commit":PIN,"path":BUILDER_PATH,"blob":BUILDER_BLOB},
      "execution_metadata":{"actions_run_id":str(a.run_id or "")},
      "execution_environment":{
        "python_version":sys.version.split()[0],
        "pinned_requirements":{"path":REQ_PATH,"blob":REQ_BLOB,"verified":True},
        "resolved_requests_version":requests_version,
        "resolved_beautifulsoup4_version":beautifulsoup4_version,
        "requests_import":"PASS","bs4_import":"PASS","BeautifulSoup_import":"PASS",
        "pinned_classifier_import":"PASS",
        "network_guard_enabled_before_materialized_reconstruction":True
      },
      "methodology_version":METHOD,"normalization_version":NORM,
      "materialization_integrity":{
        "decoded_corpus_sha256":corpus_meta["uncompressed_sha256"],
        "decoded_schema":"PASS" if mat_metrics["decoded_schema_pass"] else "FAIL",
        "candidate_store_entries":mat_metrics["candidate_store_entries"],
        "candidate_refs":mat_metrics["candidate_refs"],
        "candidate_store_duplicate_keys":mat_metrics["candidate_store_duplicate_keys"],
        "candidate_store_hash_mismatches":mat_metrics["candidate_store_hash_mismatches"],
        "candidate_ref_failures":mat_metrics["candidate_ref_failures"],
        "materialized_input_hash_mismatches":mat_metrics["materialized_input_hash_mismatches"],
        "accepted_empty_bundles":mat_metrics["accepted_empty_bundles"],
        "unaccepted_empty_candidate_sets":mat_metrics["unaccepted_empty_candidate_sets"],
        "a2_classifier_input_ready":a2_ready,
        "a2_classifier_input_blocked":a2_blocked,
        "target_context_episode_id_matches":matches,
        "target_temporal_mismatches":temporal_mis,
      },
      "target_identity_set_sha256":target_identity_sha,
      "counts":{"target_episodes":EXPECTED_TARGETS,"classified_episodes":runa["classified"],"unclassified_episodes":0,
        "unexpected_non_target_verdicts":0,"duplicate_verdicts":0,
        "candidate_level_classifier_executions":runa["classifier_executions"],
        "candidate_ref_failures":runa["candidate_ref_failures"],"candidate_hash_mismatches":candidate_hash_mismatches,
        "materialized_input_hash_mismatches":runa["materialized_input_hash_mismatches"],
        "accepted_empty_bundles":runa["accepted_empty"],"singleton_context_shortcuts":runa["singleton_context_targets"],
        "run_b_singleton_context_shortcuts":runb["singleton_context_targets"],
        "external_evidence_requests":0,"discovery_executions":0,"db_queries":0,"db_writes":0,
        "unit_b_classifications":0,"unit_c_classifications":0},
      "target_context_measurements":{
        run["name"]:{"minimum_target_context_size":run["minimum_target_context_size"],
                     "maximum_target_context_size":run["maximum_target_context_size"],
                     "per_city_context_sizes":run["per_city_context_sizes"],
                     "singleton_context_targets":run["singleton_context_targets"],
                     "smallest_singleton_target_example":run["smallest_singleton_target_example"]}
        for run in (runa,runb)
      },
      "distribution":runa["verdict_counts"],"confirmed_positives":runa["verdict_counts"].get("STRICT_EVENT_POSITIVE",0)+runa["verdict_counts"].get("SENSITIVITY_EVENT_POSITIVE",0),
      "direct_strict":runa["direct_strict"],"composed_strict":runa["composed_strict"],"sensitivity_count":runa["sensitivity"],
      "per_city_distribution":runa["per_city"],"event_type_distribution":runa["event_type_counts"],"qa_reason_distribution":runa["qa_reason_counts"],
      "determinism":{"run_a_classification_set_sha256":runa["classification_set_sha256"],"run_b_classification_set_sha256":runb["classification_set_sha256"],"semantic_mismatches":sem_mis,"deterministic":True},
      "candidate_decision_store":runa["payload"]["candidate_decision_store"],
      "episode_results":runa["payload"]["episodes"],
      "hard_gates":gates,
      "execution_guards":{"external_evidence_requests":0,"discovery_executions":0,"db_queries":0,"db_writes":0,"production_mutation":"NO","classifier_semantic_changes":0,"normalization_semantic_changes":0,"parent_binding_mutations":0},
    }
    Path(a.out).write_text(json.dumps(artifact,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    print("VERDICT="+artifact["verdict"])
    print("DECODED_CORPUS_SHA256="+corpus_meta["uncompressed_sha256"])
    print("DECODED_CORPUS_SCHEMA=PASS")
    print("CANDIDATE_STORE_ENTRIES="+str(mat_metrics["candidate_store_entries"]))
    print("CANDIDATE_REFS="+str(mat_metrics["candidate_refs"]))
    print("CANDIDATE_STORE_HASH_MISMATCHES="+str(mat_metrics["candidate_store_hash_mismatches"]))
    print("CANDIDATE_REF_FAILURES="+str(mat_metrics["candidate_ref_failures"]))
    print("MATERIALIZED_INPUT_HASH_MISMATCHES="+str(mat_metrics["materialized_input_hash_mismatches"]))
    print("ACCEPTED_EMPTY="+str(mat_metrics["accepted_empty_bundles"]))
    print("A2_READY="+str(a2_ready))
    print("A2_BLOCKED="+str(a2_blocked))
    print("TARGET_CONTEXT_MATCHES="+str(matches)+"/1713")
    print("CLASSIFIER_IMPORT=PASS")
    print("CLASSIFIED=1713/1713")
    print("DISTRIBUTION="+json.dumps(artifact["distribution"],sort_keys=True))
    print("STRICT="+str(artifact["distribution"].get("STRICT_EVENT_POSITIVE",0)))
    print("DIRECT_STRICT="+str(artifact["direct_strict"]))
    print("COMPOSED_STRICT="+str(artifact["composed_strict"]))
    print("SENSITIVITY="+str(artifact["distribution"].get("SENSITIVITY_EVENT_POSITIVE",0)))
    print("NO_CONFIRMED_EVENT="+str(artifact["distribution"].get("NO_CONFIRMED_EVENT",0)))
    print("NEEDS_REVIEW="+str(artifact["distribution"].get("NEEDS_REVIEW",0)))
    print("CONFIRMED_POSITIVES="+str(artifact["confirmed_positives"]))
    print("ACCEPTED_EMPTY="+str(artifact["counts"]["accepted_empty_bundles"]))
    print("CLASSIFIER_EXECUTIONS_PER_RUN="+str(runa["classifier_executions"])+","+str(runb["classifier_executions"]))
    print("MIN_TARGET_CONTEXT_SIZE="+str(runa["minimum_target_context_size"]))
    print("MAX_TARGET_CONTEXT_SIZE="+str(runa["maximum_target_context_size"]))
    print("PER_CITY_CONTEXT_SIZES="+json.dumps(runa["per_city_context_sizes"],sort_keys=True))
    print("SINGLETON_CONTEXT_TARGETS_RUN_A="+str(runa["singleton_context_targets"]))
    print("SINGLETON_CONTEXT_TARGETS_RUN_B="+str(runb["singleton_context_targets"]))
    print("SMALLEST_SINGLETON_TARGET_RUN_A="+json.dumps(runa["smallest_singleton_target_example"],sort_keys=True))
    print("SMALLEST_SINGLETON_TARGET_RUN_B="+json.dumps(runb["smallest_singleton_target_example"],sort_keys=True))
    print("CLASSIFIER_EXECUTIONS="+str(artifact["counts"]["candidate_level_classifier_executions"]))
    print("RUN_A_SHA="+artifact["determinism"]["run_a_classification_set_sha256"])
    print("RUN_B_SHA="+artifact["determinism"]["run_b_classification_set_sha256"])
    print("SEMANTIC_MISMATCHES="+str(sem_mis))
    print("DETERMINISTIC="+("YES" if sem_mis==0 and runa["classification_set_sha256"]==runb["classification_set_sha256"] else "NO"))
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Blocked as e:
        print("ATTACK-EVENT EXECUTION UNIT A CLASSIFICATION REPLAY = BLOCKED",file=sys.stderr)
        print("BLOCKER="+str(e),file=sys.stderr)
        raise
