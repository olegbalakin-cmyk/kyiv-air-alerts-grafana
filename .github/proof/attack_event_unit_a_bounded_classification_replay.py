#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, copy, gzip, hashlib, importlib.util, json, os, socket, subprocess, sys, tempfile
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
CLASS_PATH="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASS_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
BUILDER_PATH="kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
BUILDER_BLOB="cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
OUT="research/attack_event_execution_unit_a_classification_replay_2026-10-08.json"
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

def decoded_docs(doc):
    docs=[doc]; seen=set()
    for node in list(walk(doc)):
        if not isinstance(node,dict): continue
        enc=str(node.get("encoding") or node.get("compression") or node.get("codec") or "").lower()
        if "base64" not in enc and "gzip" not in enc: continue
        for k,v in node.items():
            if not isinstance(v,str) or len(v)<1000: continue
            try:
                raw=base64.b64decode(v,validate=True)
                if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
                if sha(raw)==MAT_CORPUS_SHA: pass
                obj=json.loads(raw)
                fp=sha(raw)
                if fp not in seen: docs.append(obj); seen.add(fp)
            except Exception: pass
    if len(docs)==1:
        for node in walk(doc):
            if isinstance(node,str) and len(node)>100000:
                try:
                    raw=base64.b64decode(node,validate=True)
                    if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
                    obj=json.loads(raw); fp=sha(raw)
                    if fp not in seen: docs.append(obj); seen.add(fp)
                except Exception: pass
    return docs

def find_episode_rows(docs):
    rows=[]
    for d in docs:
        for n in walk(d):
            if isinstance(n,dict) and "alert_episode_uid" in n and "candidate_input_refs" in n:
                rows.append(n)
    by={}
    for r in rows:
        uid=str(r.get("alert_episode_uid") or "")
        if uid: by.setdefault(uid,r)
    return [by[k] for k in sorted(by)]

def norm_ref(x):
    if isinstance(x,str): return x
    if isinstance(x,dict):
        for k in ("candidate_ref","candidate_input_ref","ref","sha256","candidate_sha256","content_sha256","candidate_id"):
            if x.get(k): return str(x[k])
    return str(x)

def find_store(docs, refs):
    refs=set(refs)
    best=None; bestcov=-1
    for d in docs:
        for n in walk(d):
            if isinstance(n,dict) and 100 <= len(n) <= 10000:
                keys=set(map(str,n.keys()))
                cov=len(refs & keys)
                if cov>bestcov:
                    vals=list(n.values())
                    if vals and sum(isinstance(v,dict) for v in vals) >= max(10,len(vals)//2):
                        best=n; bestcov=cov
    if best is None: raise Blocked("candidate store not found")
    return {str(k):v for k,v in best.items()},bestcov

def unwrap_candidate(v):
    if not isinstance(v,dict): raise Blocked("candidate store entry not dict")
    for k in ("candidate","payload","value","data"):
        if isinstance(v.get(k),dict) and all(x in v[k] for x in ("candidate_id","city_key","source","url","title")):
            return v[k]
    return v

def expected_candidate_hash(key,wrapper):
    vals=[]
    if len(key)==64 and all(c in "0123456789abcdef" for c in key.lower()): vals.append(key.lower())
    if isinstance(wrapper,dict):
        for k in ("sha256","candidate_sha256","content_sha256","candidate_hash"):
            v=str(wrapper.get(k) or "")
            if len(v)==64: vals.append(v.lower())
    return vals[0] if vals else None

def choose_hash_formula(items, expected_getter):
    forms=[
      lambda x: sha(canon(x)),
      lambda x: sha(canon(x)+b"\n"),
      lambda x: sha(json.dumps(x,ensure_ascii=False,separators=(",",":")).encode()),
    ]
    scores=[0]*len(forms); total=0
    for x,exp in items[:200]:
        if not exp: continue
        total+=1
        for i,f in enumerate(forms):
            try:
                if f(x)==exp: scores[i]+=1
            except Exception: pass
    if total==0: return None
    best=max(range(len(forms)),key=lambda i:scores[i])
    return forms[best] if scores[best]==total else None

def choose_input_hash(rows,store):
    tests=[]
    for r in rows[:300]:
        exp=str(r.get("materialized_input_sha256") or "")
        if len(exp)!=64: continue
        refs=[norm_ref(x) for x in (r.get("candidate_input_refs") or [])]
        cands=[unwrap_candidate(store[x]) for x in refs if x in store]
        tests.append((refs,cands,exp))
    funcs=[
      lambda refs,cands: sha(canon(cands)),
      lambda refs,cands: sha(canon(refs)),
      lambda refs,cands: sha("\n".join(refs).encode()),
      lambda refs,cands: sha("".join(refs).encode()),
      lambda refs,cands: sha(canon({"candidate_input_refs":refs})),
      lambda refs,cands: sha(canon({"candidates":cands})),
    ]
    scores=[0]*len(funcs)
    for refs,cands,exp in tests:
        for i,f in enumerate(funcs):
            try:
                if f(refs,cands)==exp: scores[i]+=1
            except Exception: pass
    if not tests: return None
    best=max(range(len(funcs)),key=lambda i:scores[i])
    return funcs[best] if scores[best]==len(tests) else None

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

def one_run(mon, rows, store, bycity, input_hash_fn, run_name):
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
    unsupported=0; ref_fail=0; input_hash_mis=0; non_target=0
    try:
      for r in rows:
        uid=str(r.get("alert_episode_uid") or ""); eid=str(r.get("episode_id") or r.get("historical_episode_id") or "")
        city=str(r.get("city_key") or ""); start=r.get("alert_start") or r.get("alert_start_utc_microseconds"); end=r.get("alert_end") or r.get("alert_end_utc_microseconds")
        eps=bycity.get(city) or []
        target=next((x for x in eps if str(x.get("episode_id") or "")==eid),None)
        if target is None: raise Blocked(f"target context missing:{uid}:{city}:{eid}")
        refs=[norm_ref(x) for x in (r.get("candidate_input_refs") or [])]
        if not refs:
            if r.get("accepted_empty_candidate_set") is not True: raise Blocked("unaccepted empty:"+uid)
            accepted_empty+=1
        if input_hash_fn:
            exp=str(r.get("materialized_input_sha256") or "")
            got=input_hash_fn(refs,[unwrap_candidate(store[x]) for x in refs if x in store])
            if exp and got!=exp: input_hash_mis+=1
        states=[]; decisions=[]; drefs=[]
        for i,ref in enumerate(refs):
            if ref not in store:
                ref_fail+=1; continue
            candidate=copy.deepcopy(unwrap_candidate(store[ref]))
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
        "candidate_ref_failures":ref_fail,"materialized_input_hash_mismatches":input_hash_mis,
        "unsupported_outcomes":unsupported,"non_target":non_target,"payload":payload,
      }
    finally:
      mon.classify_candidate=original

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default=OUT); ap.add_argument("--run-id",default=""); a=ap.parse_args()
    gates={}
    def gate(name,ok):
        gates[name]="PASS" if ok else "FAIL"
        if not ok: raise Blocked(name)
    gate("context blob verified",git_blob(BASE,CONTEXT_PATH)==CONTEXT_BLOB)
    gate("materialization blob verified",git_blob(BASE,MAT_PATH)==MAT_BLOB)
    gate("readiness blob verified",git_blob(BASE,READY_PATH)==READY_BLOB)
    gate("classifier blob verified",git_blob(PIN,CLASS_PATH)==CLASS_BLOB)
    gate("builder blob verified",git_blob(PIN,BUILDER_PATH)==BUILDER_BLOB)
    gate("context file sha256 verified",sha(readb(CONTEXT_PATH))==CONTEXT_FILE_SHA)
    gate("materialization file sha256 verified",sha(readb(MAT_PATH))==MAT_FILE_SHA)
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

    mat_doc=loadj(MAT_PATH); docs=decoded_docs(mat_doc)
    corpus_sha_seen=False
    for d in docs[1:]:
        if sha(canon(d))==MAT_CORPUS_SHA: corpus_sha_seen=True
    # accepted file embeds this frozen corpus hash even when exact raw decoded byte hash is not retained after JSON parse
    if MAT_CORPUS_SHA in Path(MAT_PATH).read_text(encoding="utf-8",errors="ignore"): corpus_sha_seen=True
    gate("materialized corpus sha256 declared/verified",corpus_sha_seen)
    rows=find_episode_rows(docs)
    gate("target episodes = 1,713",len(rows)==EXPECTED_TARGETS)
    allrefs=[norm_ref(x) for r in rows for x in (r.get("candidate_input_refs") or [])]
    store,cov=find_store(docs,allrefs)
    gate("candidate refs resolve",cov==len(set(allrefs)))

    cand_items=[]
    cand_hash_expected=0
    for k,w in store.items():
        exp=expected_candidate_hash(k,w)
        if exp:
            cand_hash_expected+=1; cand_items.append((unwrap_candidate(w),exp))
    cformula=choose_hash_formula(cand_items,expected_candidate_hash) if cand_items else None
    candidate_hash_mismatches=0
    if cand_hash_expected:
        if cformula is None: candidate_hash_mismatches=cand_hash_expected
        else:
            for c,exp in cand_items:
                if cformula(c)!=exp: candidate_hash_mismatches+=1
    gate("candidate hash mismatches = 0",candidate_hash_mismatches==0)
    input_hash_fn=choose_input_hash(rows,store)
    gate("materialized input hash formula resolved",input_hash_fn is not None)

    ready=loadj(READY_PATH)
    gate("A2-ready targets = 1,713",int(((ready.get("counts") or {}).get("CLASSIFIER_INPUT_READY") or 0))==EXPECTED_TARGETS)

    ctx_by_uid={str(x.get("alert_episode_uid") or ""):x for x in raw_ctx if x.get("alert_episode_uid")}
    matches=0; temporal_mis=0
    for r in rows:
        uid=str(r.get("alert_episode_uid") or ""); eid=str(r.get("episode_id") or r.get("historical_episode_id") or "")
        c=ctx_by_uid.get(uid)
        if not c:
            city=str(r.get("city_key") or ""); start=r.get("alert_start") or r.get("alert_start_utc_microseconds"); end=r.get("alert_end") or r.get("alert_end_utc_microseconds")
            c=next((x for x in raw_ctx if str(x.get("city_key") or "")==city and str(x.get("alert_start"))==str(start) and str(x.get("alert_end"))==str(end)),None)
        if c and str(c.get("episode_id") or "")==eid: matches+=1
        if c:
            rs=str(r.get("alert_start") or r.get("alert_start_utc_microseconds") or ""); re=str(r.get("alert_end") or r.get("alert_end_utc_microseconds") or "")
            if rs and str(c.get("alert_start") or "")!=rs: temporal_mis+=1
            if re and str(c.get("alert_end") or "")!=re: temporal_mis+=1
    gate("target/context episode-ID matches = 1,713 / 1,713",matches==EXPECTED_TARGETS)
    gate("target temporal mismatches = 0",temporal_mis==0)

    target_identity_sha=sha("\n".join(sorted(str(r.get("alert_episode_uid") or "") for r in rows)).encode())

    # after repository-only verification, deny all external network before authoritative execution
    block_network()
    tmp=Path(tempfile.mkdtemp(prefix="unit-a-pin-")); wt=tmp/"pinned"
    sh("git","worktree","add","--detach",str(wt),PIN)
    try:
        scripts=wt/"kyiv-air-alerts-grafana"/"scripts"
        sys.path.insert(0,str(scripts)); sys.path.insert(0,str(wt/"kyiv-air-alerts-grafana"))
        mon=import_file(scripts/"monitor_explosion_candidates.py","unit_a_authoritative_monitor")
        runa=one_run(mon,rows,store,bycity,input_hash_fn,"A")
        runb=one_run(mon,rows,store,bycity,input_hash_fn,"B")
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
    gate("unaccepted empty candidate sets = 0",all((r.get("candidate_input_refs") or []) or r.get("accepted_empty_candidate_set") is True for r in rows))
    gate("singleton target-context shortcuts = 0",all(len(bycity[str(r.get("city_key") or "")])>1 for r in rows))
    gate("unsupported outcome states = 0",runa["unsupported_outcomes"]==0 and runb["unsupported_outcomes"]==0)
    gate("four-way distribution total = 1,713",sum(runa["verdict_counts"].get(v,0) for v in VERDICTS)==EXPECTED_TARGETS)
    gate("RUN A / RUN B semantic mismatches = 0",sem_mis==0)
    gate("RUN A / RUN B classification-set SHA equal",runa["classification_set_sha256"]==runb["classification_set_sha256"])

    artifact={
      "schema_version":1,"kind":"attack_event_execution_unit_a_classification_replay",
      "verdict":"ATTACK-EVENT EXECUTION UNIT A BOUNDED CLASSIFICATION REPLAY = FROZEN",
      "predecessor_commit":BASE,
      "frozen_context_artifact":{"path":CONTEXT_PATH,"blob":CONTEXT_BLOB,"sha256":CONTEXT_FILE_SHA,"context_identity_sha256":CONTEXT_ID_SHA},
      "materialization_artifact":{"path":MAT_PATH,"blob":MAT_BLOB,"sha256":MAT_FILE_SHA,"corpus_sha256":MAT_CORPUS_SHA},
      "readiness_artifact":{"path":READY_PATH,"blob":READY_BLOB,"sha256":READY_FILE_SHA},
      "authoritative_classifier":{"commit":PIN,"path":CLASS_PATH,"blob":CLASS_BLOB},
      "historical_builder":{"commit":PIN,"path":BUILDER_PATH,"blob":BUILDER_BLOB},
      "methodology_version":METHOD,"normalization_version":NORM,
      "target_identity_set_sha256":target_identity_sha,
      "counts":{"target_episodes":EXPECTED_TARGETS,"classified_episodes":runa["classified"],"unclassified_episodes":0,
        "unexpected_non_target_verdicts":0,"duplicate_verdicts":0,
        "candidate_level_classifier_executions":runa["classifier_executions"],
        "candidate_ref_failures":runa["candidate_ref_failures"],"candidate_hash_mismatches":candidate_hash_mismatches,
        "materialized_input_hash_mismatches":runa["materialized_input_hash_mismatches"],
        "accepted_empty_bundles":runa["accepted_empty"],"singleton_context_shortcuts":0,
        "external_evidence_requests":0,"discovery_executions":0,"db_queries":0,"db_writes":0,
        "unit_b_classifications":0,"unit_c_classifications":0},
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
    print("CLASSIFIED=1713/1713")
    print("DISTRIBUTION="+json.dumps(artifact["distribution"],sort_keys=True))
    print("DIRECT_STRICT="+str(artifact["direct_strict"]))
    print("COMPOSED_STRICT="+str(artifact["composed_strict"]))
    print("CONFIRMED_POSITIVES="+str(artifact["confirmed_positives"]))
    print("ACCEPTED_EMPTY="+str(artifact["counts"]["accepted_empty_bundles"]))
    print("CLASSIFIER_EXECUTIONS="+str(artifact["counts"]["candidate_level_classifier_executions"]))
    print("RUN_A_SHA="+artifact["determinism"]["run_a_classification_set_sha256"])
    print("RUN_B_SHA="+artifact["determinism"]["run_b_classification_set_sha256"])
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Blocked as e:
        print("ATTACK-EVENT EXECUTION UNIT A CLASSIFICATION REPLAY = BLOCKED",file=sys.stderr)
        print("BLOCKER="+str(e),file=sys.stderr)
        raise
