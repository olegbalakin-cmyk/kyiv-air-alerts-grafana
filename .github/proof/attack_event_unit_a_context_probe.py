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



# Deep probe authoritative classified source and predecessor gap source.
src=cont.get("authoritative_classification_source") or {}
print(json.dumps({"authoritative_classification_source_identity":src},ensure_ascii=False,sort_keys=True))
if src.get("commit") and src.get("path"):
    sdoc=json.loads(git_show(str(src["commit"]),str(src["path"])))
    shape("authoritative_classification_source_doc",sdoc)
    path_parts=str(src.get("classification_list_path") or "").split(".") if src.get("classification_list_path") else []
    cur=sdoc
    ok=True
    for part in path_parts:
        if isinstance(cur,dict) and part in cur:
            cur=cur[part]
        else:
            ok=False; break
    if ok:
        shape("authoritative_classification_list",cur)
        if isinstance(cur,list) and cur:
            print(json.dumps({"authoritative_classification_first":cur[0]},ensure_ascii=False,sort_keys=True))

pred=cont.get("predecessor_gap_audit_identity") or {}
print(json.dumps({"predecessor_gap_audit_identity":pred},ensure_ascii=False,sort_keys=True))
if pred.get("commit") and pred.get("path"):
    pdoc=json.loads(git_show(str(pred["commit"]),str(pred["path"])))
    shape("predecessor_gap_audit_doc",pdoc)
    for k,v in pdoc.items():
        if isinstance(v,list) and any(tok in k.lower() for tok in ("parent","episode","identity","classification")):
            print(json.dumps({"pred_collection":k,"count":len(v),"first_keys":list(v[0].keys()) if v and isinstance(v[0],dict) else None,"first":v[0] if v and isinstance(v[0],dict) else None},ensure_ascii=False,sort_keys=True))
        elif isinstance(v,dict) and any(tok in k.lower() for tok in ("parent","episode","identity","classification")):
            print(json.dumps({"pred_collection":k,"type":"dict","keys":list(v.keys())[:120]},ensure_ascii=False,sort_keys=True))



# Context reproducibility proof: old classified snapshot + all 2,100 uncovered parents.
src=cont["authoritative_classification_source"]
snap=json.loads(git_show(str(src["commit"]),str(src["path"])))
classified=list(snap.get("classifications") or [])
old=[]
for row in classified:
    old.append({
        "episode_id": str(row.get("historical_episode_id") or ""),
        "city_key": str(row.get("city_key") or ""),
        "alert_start": row.get("alert_start_utc_microseconds"),
        "alert_end": row.get("alert_end_utc_microseconds"),
    })
old_bad=sum(not all([x["episode_id"],x["city_key"],x["alert_start"],x["alert_end"]]) for x in old)
old_ids=[(x["city_key"],x["episode_id"]) for x in old]
old_identity=[(x["city_key"],x["alert_start"],x["alert_end"]) for x in old]
parents=list(cont.get("uncovered_parent_identities") or [])
cohort_rows=[]
for cohort_name in ("materialization_cohort","evidence_missing_cohort","identity_binding_cohort"):
    co=rec.get(cohort_name) or {}
    for row in co.get("rows") or []:
        rr=dict(row); rr["_cohort"]=cohort_name; cohort_rows.append(rr)
by_uid={}
dups=0
for row in cohort_rows:
    uid=str(row.get("alert_episode_uid") or "")
    if uid in by_uid: dups+=1
    else: by_uid[uid]=row
uncovered=[]
missing_row=[]
missing_live_id=[]
parent_mismatch=[]
cohort_counts={}
for p in parents:
    uid=str(p.get("alert_episode_uid") or "")
    rr=by_uid.get(uid)
    if rr is None:
        missing_row.append(uid); continue
    cohort_counts[rr["_cohort"]]=cohort_counts.get(rr["_cohort"],0)+1
    eid=str(rr.get("live_monitor_episode_id") or "")
    if not eid:
        missing_live_id.append({"uid":uid,"cohort":rr["_cohort"],"keys":list(rr.keys())})
    if rr.get("city_key")!=p.get("city_key") or rr.get("start_at")!=p.get("start_at") or rr.get("end_at")!=p.get("end_at"):
        parent_mismatch.append(uid)
    uncovered.append({
        "alert_episode_uid":uid,
        "episode_id":eid,
        "city_key":str(p.get("city_key") or ""),
        "alert_start":p.get("start_at"),
        "alert_end":p.get("end_at"),
        "cohort":rr["_cohort"],
    })
uncovered_identities={(x["city_key"],x["alert_start"],x["alert_end"]) for x in uncovered}
old_identity_set=set(old_identity)
overlap=old_identity_set & uncovered_identities

mat=json.loads(Path(MAT_PATH).read_text(encoding="utf-8"))
corpus=json.loads(gzip.decompress(base64.b64decode(mat["corpus"]["payload_base64"])))
targets=corpus.get("episodes") or []
target_context_missing=[]
target_context_mismatch=[]
uncovered_by_uid={x["alert_episode_uid"]:x for x in uncovered}
for t in targets:
    uid=str(t.get("alert_episode_uid") or "")
    ci=t.get("classifier_episode_input") or {}
    ctx=uncovered_by_uid.get(uid)
    if not ctx:
        target_context_missing.append(uid)
    elif (ci.get("episode_id"),ci.get("city_key"),ci.get("alert_start"),ci.get("alert_end")) != (ctx.get("episode_id"),ctx.get("city_key"),ctx.get("alert_start"),ctx.get("alert_end")):
        target_context_mismatch.append(uid)

pc=pdoc.get("parent_coverage") or {}
print(json.dumps({
 "context_proof":{
   "continuity_audited_main_commit":cont.get("audited_main_commit"),
   "classified_rows":len(old),
   "classified_bad_required_fields":old_bad,
   "classified_duplicate_city_episode_ids":len(old_ids)-len(set(old_ids)),
   "classified_duplicate_temporal_identities":len(old_identity)-len(old_identity_set),
   "uncovered_parent_rows":len(parents),
   "recovery_cohort_rows":len(cohort_rows),
   "recovery_cohort_duplicate_uids":dups,
   "cohort_counts_for_uncovered":cohort_counts,
   "uncovered_missing_recovery_row_count":len(missing_row),
   "uncovered_missing_live_episode_id_count":len(missing_live_id),
   "uncovered_parent_identity_mismatch_count":len(parent_mismatch),
   "classified_uncovered_temporal_overlap_count":len(overlap),
   "combined_context_count":len(old)+len(uncovered),
   "gap_audit_current_canonical_air_parent_count":pc.get("current_canonical_air_parent_count"),
   "gap_audit_covered_by_current_authoritative_classification":pc.get("covered_by_current_authoritative_classification"),
   "gap_audit_closed_without_current_authoritative_classification":pc.get("closed_without_current_authoritative_classification"),
   "target_context_missing_count":len(target_context_missing),
   "target_context_mismatch_count":len(target_context_mismatch),
   "smallest_missing_live_id":missing_live_id[0] if missing_live_id else None,
   "smallest_target_context_mismatch":target_context_mismatch[0] if target_context_mismatch else None
 }
},ensure_ascii=False,sort_keys=True))



# Authoritative loader proof from the continuity-pinned audited main commit.
import importlib, shutil, sys, types
audited=str(cont.get("audited_main_commit") or "")
pinned="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
for path in ("/tmp/unit_a_audited_main","/tmp/unit_a_pinned_impl"):
    shutil.rmtree(path,ignore_errors=True)
subprocess.check_call(["git","worktree","add","--detach","/tmp/unit_a_audited_main",audited],stdout=subprocess.DEVNULL)
subprocess.check_call(["git","worktree","add","--detach","/tmp/unit_a_pinned_impl",pinned],stdout=subprocess.DEVNULL)
scripts=Path("/tmp/unit_a_pinned_impl/kyiv-air-alerts-grafana/scripts")
sys.path.insert(0,str(scripts))
if "bs4" not in sys.modules:
    bs4_stub=types.ModuleType("bs4")
    def _unused_bs4(*args,**kwargs):
        raise RuntimeError("DISCOVERY_BS4_PATH_FORBIDDEN_IN_CONTEXT_PROBE")
    bs4_stub.BeautifulSoup=_unused_bs4
    sys.modules["bs4"]=bs4_stub
monitor=importlib.import_module("monitor_explosion_candidates")
replay=importlib.import_module("replay_explosion_history")
audited_root=Path("/tmp/unit_a_audited_main/kyiv-air-alerts-grafana")
cities=sorted((cont.get("uncovered_counts_by_city") or {}).keys())
loaded_by_city={}
source_files={}
for city in cities:
    eps,sources=replay.load_historical_episodes(audited_root,city,monitor)
    eps=sorted([dict(x) for x in eps],key=lambda x:(str(x.get("alert_start") or ""),str(x.get("episode_id") or "")))
    loaded_by_city[city]=eps
    source_files[city]=sources
all_loaded=[x for city in cities for x in loaded_by_city[city]]
loaded_bad=sum(not all([x.get("episode_id"),x.get("alert_start"),x.get("alert_end")]) for x in all_loaded)
loaded_dup=sum(len(v)-len({str(x.get("episode_id") or "") for x in v}) for v in loaded_by_city.values())
loaded_index={(city,str(ep.get("episode_id") or "")):(ep.get("alert_start"),ep.get("alert_end")) for city,eps in loaded_by_city.items() for ep in eps}
loaded_temporal={(city,ep.get("alert_start"),ep.get("alert_end")):str(ep.get("episode_id") or "") for city,eps in loaded_by_city.items() for ep in eps}
target_exact=0
target_missing=[]
target_mismatch=[]
for t in targets:
    ci=t.get("classifier_episode_input") or {}
    key=(str(ci.get("city_key") or ""),str(ci.get("episode_id") or ""))
    got=loaded_index.get(key)
    if got is None:
        target_missing.append(str(t.get("alert_episode_uid") or ""))
    elif got!=(ci.get("alert_start"),ci.get("alert_end")):
        target_mismatch.append(str(t.get("alert_episode_uid") or ""))
    else:
        target_exact+=1
parent_exact=0
parent_missing=[]
for p in parents:
    key=(str(p.get("city_key") or ""),p.get("start_at"),p.get("end_at"))
    if key in loaded_temporal: parent_exact+=1
    else: parent_missing.append(str(p.get("alert_episode_uid") or ""))
context_repr=[
 {"city_key":city,"episode_id":str(ep.get("episode_id") or ""),"alert_start":ep.get("alert_start"),"alert_end":ep.get("alert_end")}
 for city in cities for ep in loaded_by_city[city]
]
context_bytes=(json.dumps(context_repr,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
print(json.dumps({
 "audited_loader_context_proof":{
   "audited_main_commit":audited,
   "pinned_replay_blob":git_text("rev-parse",f"{pinned}:kyiv-air-alerts-grafana/scripts/replay_explosion_history.py"),
   "city_count":len(cities),
   "loaded_episode_count":len(all_loaded),
   "loaded_bad_required_fields":loaded_bad,
   "loaded_duplicate_city_episode_ids":loaded_dup,
   "target_exact_matches":target_exact,
   "target_missing_count":len(target_missing),
   "target_mismatch_count":len(target_mismatch),
   "uncovered_parent_exact_temporal_matches":parent_exact,
   "uncovered_parent_missing_temporal_count":len(parent_missing),
   "context_sha256":__import__("hashlib").sha256(context_bytes).hexdigest(),
   "per_city_counts":{c:len(loaded_by_city[c]) for c in cities},
   "source_file_counts":{c:len(source_files[c]) for c in cities},
   "smallest_target_missing":target_missing[0] if target_missing else None,
   "smallest_target_mismatch":target_mismatch[0] if target_mismatch else None,
   "smallest_parent_missing":parent_missing[0] if parent_missing else None
 }
},ensure_ascii=False,sort_keys=True))

print("CONTEXT_PROBE_DONE")
