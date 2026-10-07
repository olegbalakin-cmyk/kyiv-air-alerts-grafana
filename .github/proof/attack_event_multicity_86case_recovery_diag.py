#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, json, os, shutil, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARITY_PATH=HERE/"attack_event_multicity_classifier_parity.py"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import "+str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

p=load(PARITY_PATH,"parity_base")
AFFECTED={"cherkasy","lviv","sumy","vinnytsia","zaporizhzhia","zhytomyr"}

def summarize_obj(v):
    if isinstance(v,dict):
        return {"type":"dict","keys":sorted(v.keys())}
    if isinstance(v,list):
        return {"type":"list","length":len(v)}
    return {"type":type(v).__name__,"value":v}

def main():
    out=Path(sys.argv[1])
    for c in [p.SNAP_COMMIT,p.CAND_COMMIT,p.TARGET_COMMIT,p.REPAIR_COMMIT]:
        p.ensure_commit(c)
    doc=p.json_at(p.SNAP_COMMIT,p.SNAP_PATH)
    rows=doc.get("classifications") or []
    links=doc.get("source_links") or []
    by_key={str(r["classification_key"]):r for r in rows}
    links_by_key=defaultdict(list)
    for l in links:
        ck=str(l.get("classification_key_v2") or "")
        if ck in by_key:
            links_by_key[ck].append(l)
    rows_by_city=defaultdict(list)
    for r in rows:
        city=str(r.get("city_key") or "")
        if city in AFFECTED:
            rows_by_city[city].append(r)

    target=p.json_at(p.TARGET_COMMIT,p.TARGET_PATH)
    worker_ref={}
    for w in target.get("workers") or []:
        for city in w.get("cities") or []:
            worker_ref[str(city)]=str(w["tested_head"])
    for ref in sorted(set(worker_ref.values())):
        p.ensure_commit(ref)

    repair=p.json_at(p.REPAIR_COMMIT,p.REPAIR_PATH)
    changed=((repair.get("observations") or {}).get("changed_observations") or [])
    repair_by_ep=defaultdict(list)
    repair_by_obs=defaultdict(list)
    for x in changed:
        for eid in x.get("affected_episode_ids") or []:
            repair_by_ep[str(eid)].append(x)
        if x.get("observation_id"):
            repair_by_obs[str(x["observation_id"])].append(x)

    tmp=Path(tempfile.mkdtemp(prefix="recover86-diag-"))
    worker_py=tmp/"replay_worker.py"
    worker_py.write_text(p.REPLAY_WORKER,encoding="utf-8")
    candidate_bytes=p.git_bytes(p.CAND_COMMIT,p.CAND_PATH)
    worktrees={}
    results={}
    try:
        needed={p.CAND_COMMIT}|{worker_ref[c] for c in AFFECTED if c not in p.FIVE and c in worker_ref}
        for ref in sorted(needed):
            wt=tmp/("wt-"+ref[:12])
            p.sh(["git","worktree","add","--detach",str(wt),ref])
            worktrees[ref]=wt
            cand=wt/"kyiv-air-alerts-grafana"/"scripts"/"_candidate_parity_monitor.py"
            cand.write_bytes(candidate_bytes)
        for city in sorted(AFFECTED):
            comp="5" if city in p.FIVE else "18"
            ref=p.CAND_COMMIT if comp=="5" else worker_ref[city]
            eps=[p.episode_from_class(r) for r in rows_by_city[city]]
            city_links=[]
            for r in rows_by_city[city]:
                eid=str(r["historical_episode_id"])
                for l0 in links_by_key.get(str(r["classification_key"]),[]):
                    l=copy.deepcopy(l0); l["target_episode_id"]=eid; city_links.append(l)
            cfg={"city":city,"component":comp,"worktree":str(worktrees[ref]),
                 "candidate_path":str(worktrees[ref]/"kyiv-air-alerts-grafana"/"scripts"/"_candidate_parity_monitor.py"),
                 "episodes":eps,"links":city_links}
            cp=tmp/f"cfg-{city}.json"; op=tmp/f"out-{city}.json"
            cp.write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
            env=os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"]="1"
            proc=p.sh([sys.executable,str(worker_py),str(cp),str(op)],cwd=worktrees[ref],check=False,env=env)
            if not op.exists():
                raise RuntimeError(f"worker missing {city}: {proc.stderr[-1000:]}")
            results[city]=json.loads(op.read_text(encoding="utf-8"))

        ledger=[]
        reasons=Counter()
        for city in sorted(AFFECTED):
            rr=results[city]
            oldmap=rr.get("old") or {}; newmap=rr.get("candidate") or {}
            controls_by_target=defaultdict(list)
            for c in rr.get("link_controls") or []:
                controls_by_target[str(c.get("target_episode_id") or "")].append(c)
            comp="5" if city in p.FIVE else "18"
            for r in rows_by_city[city]:
                eid=str(r["historical_episode_id"]); fv=str(r["verdict"])
                observed_old=oldmap.get(eid); nv=newmap.get(eid)
                controls=controls_by_target.get(eid,[])
                reason=None
                if rr.get("error") or nv is None:
                    reason="INPUT_NOT_RECONSTRUCTABLE"
                else:
                    control_target=p.native_five_state(r) if comp=="5" else fv
                    control_ok=(control_target is not None and observed_old==control_target)
                    if not control_ok:
                        reason=p.mismatch_reason(r,False,nv,observed_old,controls)
                    elif comp=="5" and r.get("repair_overlay") and nv!=fv and nv==observed_old:
                        reason="TEMPORAL_REPRESENTATION_DIFFERENCE"
                if not reason:
                    continue
                reasons[reason]+=1
                ls=links_by_key.get(str(r["classification_key"]),[])
                obsids=sorted({str(x.get("observation_id") or "") for x in ls if x.get("observation_id")})
                rep=[]
                seen=set()
                for x in repair_by_ep.get(eid,[]):
                    if id(x) not in seen: rep.append(x); seen.add(id(x))
                for oid in obsids:
                    for x in repair_by_obs.get(oid,[]):
                        if id(x) not in seen: rep.append(x); seen.add(id(x))
                repair_matches=[{
                    "observation_id":x.get("observation_id"),
                    "affected_episode_ids":x.get("affected_episode_ids"),
                    "old_classification":x.get("old_classification"),
                    "new_classification":x.get("new_classification"),
                    "new_parsed_event_timestamp":x.get("new_parsed_event_timestamp"),
                    "new_temporal_binding":x.get("new_temporal_binding"),
                    "old_temporal_binding":x.get("old_temporal_binding"),
                    "source":x.get("source"),
                    "frozen_batch":x.get("frozen_batch"),
                } for x in rep]
                source_link_summaries=[]
                for l in ls:
                    payload=l.get("normalized_accepted_observation_payload")
                    source_link_summaries.append({
                        "source_link_key":l.get("source_link_key"),
                        "observation_id":l.get("observation_id"),
                        "source_type":l.get("source_type"),
                        "source_family":l.get("source_family"),
                        "source_timestamp":l.get("source_timestamp"),
                        "payload":summarize_obj(payload),
                        "payload_review_provenance": summarize_obj(payload.get("review_provenance")) if isinstance(payload,dict) and "review_provenance" in payload else None,
                        "payload_matched_episode_id": payload.get("matched_episode_id") if isinstance(payload,dict) else None,
                        "payload_status": payload.get("status") if isinstance(payload,dict) else None,
                        "payload_reason_codes": payload.get("classification_reason_codes") if isinstance(payload,dict) else None,
                    })
                native=r.get("native_frozen_episode_result")
                ledger.append({
                    "city":city,"episode_id":eid,"frozen_verdict":fv,
                    "reason":reason,"component":comp,
                    "observed_old":observed_old,"candidate_state":nv,
                    "repair_overlay":r.get("repair_overlay"),
                    "native_frozen_episode_result":native,
                    "row_keys":sorted(r.keys()),
                    "source_links":source_link_summaries,
                    "repair_matches":repair_matches,
                    "worker_ref":worker_ref.get(city),
                })
        assert len(ledger)==86, len(ledger)
        assert reasons["TEMPORAL_REPRESENTATION_DIFFERENCE"]==59, reasons
        assert reasons["INPUT_NOT_RECONSTRUCTABLE"]==27, reasons
        positives=sum(1 for x in ledger if x["frozen_verdict"] in p.POSITIVE)
        diag={
            "target_cases":len(ledger),"frozen_positives":positives,"reasons":dict(reasons),
            "cities":dict(Counter(x["city"] for x in ledger)),
            "temporal_repair_match_counts":dict(Counter(len(x["repair_matches"]) for x in ledger if x["reason"]=="TEMPORAL_REPRESENTATION_DIFFERENCE")),
            "input_native_shapes":dict(Counter(json.dumps(summarize_obj(x["native_frozen_episode_result"]),sort_keys=True) for x in ledger if x["reason"]=="INPUT_NOT_RECONSTRUCTABLE")),
            "ledger":ledger,
        }
        out.write_text(json.dumps(diag,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        compact={
            "target_cases":86,"frozen_positives":positives,"reasons":dict(reasons),"cities":diag["cities"],
            "temporal_repair_match_counts":diag["temporal_repair_match_counts"],
            "input_cases":[{
                "city":x["city"],"episode_id":x["episode_id"],"frozen_verdict":x["frozen_verdict"],
                "observed_old":x["observed_old"],"candidate_state":x["candidate_state"],
                "native_keys": sorted((x["native_frozen_episode_result"] or {}).keys()) if isinstance(x["native_frozen_episode_result"],dict) else None,
                "source_link_count":len(x["source_links"]),
                "source_payload_keys":sorted({k for l in x["source_links"] for k in ((l.get("payload") or {}).get("keys") or [])}),
            } for x in ledger if x["reason"]=="INPUT_NOT_RECONSTRUCTABLE"],
        }
        print("RECOVER86_DIAGNOSTIC="+json.dumps(compact,ensure_ascii=False,separators=(",",":")))
    finally:
        for wt in worktrees.values():
            p.sh(["git","worktree","remove","--force",str(wt)],check=False)
        shutil.rmtree(tmp,ignore_errors=True)

if __name__=="__main__":
    main()
