#!/usr/bin/env python3
from __future__ import annotations
import base64, gzip, json, subprocess
from pathlib import Path

CONT_REF="48099cd6d93c2b911e331e79b5141dd482d242a8"
CONT_PATH="research/attack_event_classification_continuity_audit_2026-10-06.json"
REC_REF="ccb2e6ea2637b2bdbde5d21744a79d8f4a91ff4d"
REC_PATH="research/attack_event_partitioned_classification_recovery_audit_2026-10-06.json"
MAT_PATH="research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
READY_PATH="research/attack_event_execution_unit_a_classifier_readiness_validation_2026-10-08.json"

def git_show(ref,path):
    return subprocess.check_output(["git","show",f"{ref}:{path}"])

def shape(name,obj,depth=0):
    out={"name":name,"type":type(obj).__name__}
    if isinstance(obj,dict):
        out["keys"]=list(obj.keys())
        out["summary"]={}
        for k,v in obj.items():
            if isinstance(v,list):
                out["summary"][k]={"type":"list","count":len(v),"first_keys":list(v[0].keys()) if v and isinstance(v[0],dict) else None}
            elif isinstance(v,dict):
                out["summary"][k]={"type":"dict","keys":list(v.keys())[:80]}
    elif isinstance(obj,list):
        out["count"]=len(obj)
        out["first_keys"]=list(obj[0].keys()) if obj and isinstance(obj[0],dict) else None
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))

cont=json.loads(git_show(CONT_REF,CONT_PATH))
rec=json.loads(git_show(REC_REF,REC_PATH))
ready=json.loads(Path(READY_PATH).read_text(encoding="utf-8"))
mat=json.loads(Path(MAT_PATH).read_text(encoding="utf-8"))
payload=base64.b64decode(mat["corpus"]["payload_base64"])
corpus=json.loads(gzip.decompress(payload))

shape("continuity",cont)
shape("recovery",rec)
shape("readiness",ready)
shape("materialization_top",mat)
shape("materialization_manifest",mat.get("manifest") or {})
shape("materialization_governing_semantics",mat.get("governing_semantics") or {})
shape("materialization_corpus",corpus)

for label,obj in [("continuity",cont),("recovery",rec)]:
    for k,v in obj.items():
        lk=k.lower()
        if any(tok in lk for tok in ("episode","parent","universe","identity","classification","source","frozen","context")):
            if isinstance(v,list):
                print(json.dumps({"collection":f"{label}.{k}","type":"list","count":len(v),"first_keys":list(v[0].keys()) if v and isinstance(v[0],dict) else None},sort_keys=True))
            elif isinstance(v,dict):
                print(json.dumps({"collection":f"{label}.{k}","type":"dict","keys":list(v.keys())[:120]},sort_keys=True))

# Explore one level deeper for dicts that may contain episode collections.
for label,obj in [("continuity",cont),("recovery",rec)]:
    for k,v in obj.items():
        if not isinstance(v,dict):
            continue
        for sk,sv in v.items():
            l=(k+"."+sk).lower()
            if any(tok in l for tok in ("episode","parent","universe","identity","classification","source","frozen","context","unit","cohort")):
                if isinstance(sv,list):
                    print(json.dumps({"collection":f"{label}.{k}.{sk}","type":"list","count":len(sv),"first_keys":list(sv[0].keys()) if sv and isinstance(sv[0],dict) else None},sort_keys=True))
                elif isinstance(sv,dict):
                    print(json.dumps({"collection":f"{label}.{k}.{sk}","type":"dict","keys":list(sv.keys())[:120]},sort_keys=True))

episodes=corpus.get("episodes") or []
print(json.dumps({
 "materialized_episode_count":len(episodes),
 "episode_keys":list(episodes[0].keys()) if episodes else [],
 "classifier_episode_input_keys":list((episodes[0].get("classifier_episode_input") or {}).keys()) if episodes else [],
 "evidence_provenance_keys":list((episodes[0].get("evidence_provenance") or {}).keys()) if episodes else [],
 "manifest":mat.get("manifest"),
},ensure_ascii=False,sort_keys=True))

# continuity parent sample and counts by likely collections
for k in ["uncovered_parent_identities","covered_parent_identities","all_parent_identities","parent_identities","canonical_parent_identities"]:
    v=cont.get(k)
    if isinstance(v,list):
        print(json.dumps({"continuity_collection":k,"count":len(v),"first":v[0] if v else None},ensure_ascii=False,sort_keys=True))

print("CONTEXT_PROBE_DONE")
