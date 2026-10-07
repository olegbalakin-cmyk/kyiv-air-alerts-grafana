#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, json, os, shutil, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import attack_event_multicity_classifier_parity as p

# Trial re-run after diagnostic harness cleanup.
WORKER_REF="eaa77e2c2714d68a25dcd581c3194c1d394eb00a"
CITIES={"cherkasy","lviv","sumy","vinnytsia","zaporizhzhia","zhytomyr"}
POS={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def build5(link,city):
    text=str(link.get("excerpt") or "")
    st=str(link.get("source_type") or ""); sf=str(link.get("source_family") or "")
    chan=str(link.get("telegram_channel") or ""); is_tg=bool(chan) or "telegram" in st.casefold()
    if is_tg:
        source="Telegram / "+(sf or chan or "historical")
        basis="article_linked_public_telegram" if st=="article_linked_public_telegram" else "bounded_public_telegram_search"
        publisher=sf or chan or "historical"
    else:
        source=sf or st or "historical"; basis="historical_source_local_html"; publisher=sf or "historical"
    return {"candidate_id":str(link.get("observation_id") or ""),"city_key":city,"source":source,
      "title":text[:240],"snippet":text[:1200],"matched_text_excerpt":text,"publisher":publisher,
      "publisher_url":None,"url":link.get("source_url") or "","resolved_url":link.get("source_url") or None,
      "published_at":link.get("source_timestamp"),"discovery_basis":basis}

def manual_matching(eid):
    return {"outcome":"unique_match","matched_episode_ids":[eid],"logical_episode_groups":[[eid]],
            "matched_episode_id":eid,"reason":"durable_target_episode_binding"}

def verdict(decision):
    x=str(decision.get("proposed_outcome") or "")
    return {"approved_strict":"STRICT_EVENT_POSITIVE","approved_sensitivity":"SENSITIVITY_EVENT_POSITIVE",
            "needs_review":"NEEDS_REVIEW","rejected":"NO_CONFIRMED_EVENT"}.get(x,"NO_CONFIRMED_EVENT")

def episode_id_of(row):
    for k in ("episode_id","matched_episode_id","target_episode_id"):
        if row.get(k): return str(row[k])
    return ""

def find_final_row(root,city,eid):
    path=root/"kyiv-air-alerts-grafana"/"data"/"explosion_research"/city/"final_evidence.json"
    if not path.exists(): return None,None,None
    d=json.loads(path.read_text(encoding="utf-8"))
    for bucket in ("strict_events","sensitivity_only_events","review_events","ambiguous_events","excluded_events"):
        for row in d.get(bucket) or []:
            if episode_id_of(row)==eid:
                return copy.deepcopy(row),bucket,str(path.relative_to(root))
    return None,None,str(path.relative_to(root))

def factual_shadow_provenance(mon,row,eid):
    raw=row.get("raw_record") if isinstance(row.get("raw_record"),dict) else {}
    evidence=" ".join(str(row.get(k) or "") for k in ("evidence","evidence_text","text","excerpt","quote")).strip()
    basis=" ".join(str(row.get(k) or "") for k in ("decision_basis","basis","decision","reason")).strip()
    low=(" "+basis+" "+evidence+" ").casefold()
    provenance={"schema_version":mon.REVIEW_PROVENANCE_SCHEMA_VERSION,
                "methodology_version":"86case-frozen-factual-representability-v1",
                "target_episode_id":eid}
    used=[]
    city_status=str(raw.get("city_status") or "").casefold()
    if city_status=="exact_city" or "exact-city" in low or "exact_city" in low:
        provenance["exact_city_evidence"]={"present":True,"evidence_text":f"durable city_status={city_status or 'exact_city'}"}
        used.append("exact_city")
    war=str(raw.get("war_air_context") or "").casefold()
    if war=="confirmed" or "confirmed aerial-war" in low or "aerial_war" in low or "aerial-war" in low:
        provenance["aerial_war_evidence"]={"present":True,"evidence_text":f"durable war_air_context={war or 'confirmed'}"}
        used.append("air_context")

    # Attack-event role is never supplied from a frozen status/bucket.
    # It remains parser-derived unless the durable basis explicitly says attack-event evidence.
    tmp={"title":evidence,"snippet":"","publisher":"historical_audit","source":"frozen historical audit evidence"}
    strict=mon.strict_explosion_evidence(str(row.get("city_key") or ""),tmp) if row.get("city_key") else None
    if "attack-event evidence" in low or "attack_event evidence" in low:
        provenance["explosion_evidence"]={"present":True,"evidence_text":"durable basis explicitly records attack-event evidence"}
        used.append("attack_event")

    same_tokens=("same_attack","same-attack","same attack","same_episode","same-episode","same episode","corroborated_same_episode")
    if any(t in low for t in same_tokens):
        provenance["same_attack_basis"]={"present":True,"basis":"durable_same_attack_relation","evidence_text":basis[:1200]}
        used.append("same_attack")

    binding=str(row.get("binding_method") or "").casefold()
    temporal=str(raw.get("temporal_evidence") or row.get("temporal_evidence") or raw.get("temporal_match") or "").casefold()
    matched=episode_id_of(row)==eid
    strict_temporal=temporal in {"exact_time_in_alert","explicit_during_alert","validated_episode_binding"}
    basis_temporal=any(t in low for t in ("event_time_inside","time_inside","canonical_episode_binding","episode-specific canonical binding","episode_specific canonical binding","exact_city_time_inside_episode"))
    if matched and ("persisted_current_canonical_episode_id" in binding or strict_temporal or basis_temporal):
        provenance["temporal"]={"status":"validated_episode_binding","validated_by_review":True,"episode_specific":True,
            "temporal_evidence_type":"durable_frozen_episode_binding","evidence_text":(basis or temporal)[:1200],
            "neighboring_alert_check":{"passed":True}}
        used.append("temporal_episode_binding")

    sens=None
    if temporal=="near_boundary" or "near_boundary" in low or "near-boundary" in low:
        sens="near_boundary"
    elif temporal=="inferred_same_attack" or "inferred_same_attack" in low or "inferred same attack" in low:
        sens="inferred_same_attack"
    if matched and sens:
        provenance["sensitivity_binding"]={"present":True,"validated_by_review":True,"episode_specific":True,
            "basis":sens,"neighboring_alert_check":{"passed":True}}
        if "same_attack_basis" not in provenance:
            provenance["same_attack_basis"]={"present":True,"basis":"durable_"+sens,"evidence_text":basis[:1200]}
        used.append("sensitivity_"+sens)
    return provenance,used

def final_candidate(mon,row,city,eid):
    evidence_parts=[]
    for k in ("evidence","evidence_text","text","excerpt","quote","decision_basis","basis","decision","reason"):
        v=row.get(k)
        if v and str(v).strip() and str(v).strip() not in evidence_parts: evidence_parts.append(str(v).strip())
    text=" — ".join(evidence_parts)
    source_url=str(row.get("source_url") or "")
    cand={"candidate_id":"shadow-"+eid,"city_key":city,"title":text,"snippet":"","matched_text_excerpt":None,
          "publisher":"historical_audit","publisher_url":source_url or None,"url":source_url or f"historical://{city}/{eid}",
          "resolved_url":source_url or None,"source":"frozen historical audit evidence","published_at":None,
          "discovery_basis":"historical_audit_retained_evidence","matched_episode_id":eid}
    rr=copy.deepcopy(row); rr["city_key"]=city
    prov,used=factual_shadow_provenance(mon,rr,eid)
    cand["review_provenance"]=prov
    return cand,used

def repair_candidate(mon,base,eid,repair):
    tb=repair.get("new_temporal_binding") or {}
    if not (tb.get("present") is True and tb.get("episode_specific") is True and str(tb.get("episode_id") or "")==eid):
        return None,[]
    et=tb.get("event_time")
    if not et: return None,[]
    cand=copy.deepcopy(base)
    cand["matched_episode_id"]=eid
    cand["review_provenance"]={"schema_version":mon.REVIEW_PROVENANCE_SCHEMA_VERSION,
      "methodology_version":"86case-frozen-repair-temporal-representability-v1","target_episode_id":eid,
      "temporal":{"status":"validated_event_time","validated_by_review":True,"episode_specific":True,
        "event_time":et,"timestamp_precision":"retained","temporal_evidence_type":tb.get("evidence_type") or "frozen_repair_event_time",
        "evidence_text":str(tb.get("evidence") or et),"neighboring_alert_check":{"passed":True}}}
    return cand,["repair_event_time","repair_episode_specific_binding"]

def main():
    out=Path(sys.argv[1])
    # Recreate the accepted 86 ledger using the predecessor diagnostic, runner-side.
    tmp=Path(tempfile.mkdtemp(prefix="r86trial-"))
    diag=tmp/"diag.json"
    subprocess.run([sys.executable,str(HERE/"attack_event_multicity_86case_recovery_diag.py"),str(diag)],check=True,
                   stdout=subprocess.DEVNULL)
    dd=json.loads(diag.read_text(encoding="utf-8"))
    ledger=dd["ledger"]; assert len(ledger)==86
    p.ensure_commit(WORKER_REF); p.ensure_commit(p.CAND_COMMIT)
    wt=tmp/"worker"; p.sh(["git","worktree","add","--detach",str(wt),WORKER_REF])
    try:
        candpath=wt/"kyiv-air-alerts-grafana"/"scripts"/"_authoritative_86case.py"
        candpath.write_bytes(p.git_bytes(p.CAND_COMMIT,p.CAND_PATH))
        sys.path.insert(0,str(candpath.parent)); mon=load(str(candpath),"auth86trial")
        snap=p.json_at(p.SNAP_COMMIT,p.SNAP_PATH)
        class_by_eid={str(r["historical_episode_id"]):r for r in snap.get("classifications") or []}
        links_by_eid=defaultdict(list)
        classkey_to_eid={str(r["classification_key"]):str(r["historical_episode_id"]) for r in snap.get("classifications") or []}
        for l in snap.get("source_links") or []:
            eid=classkey_to_eid.get(str(l.get("classification_key_v2") or ""))
            if eid: links_by_eid[eid].append(l)
        repair=p.json_at(p.REPAIR_COMMIT,p.REPAIR_PATH)
        changed=(repair.get("observations") or {}).get("changed_observations") or []
        rep_by_ep=defaultdict(list)
        rep_by_obs=defaultdict(list)
        for x in changed:
            for eid in x.get("affected_episode_ids") or []: rep_by_ep[str(eid)].append(x)
            if x.get("observation_id"): rep_by_obs[str(x["observation_id"])].append(x)

        results=[]
        for item in ledger:
            city=item["city"]; eid=item["episode_id"]; fv=item["frozen_verdict"]
            crow=class_by_eid[eid]; episode=p.episode_from_class(crow); episodes=[episode]
            attempts=[]
            # 1) accepted frozen repair temporal value + original frozen excerpt.
            if item["reason"]=="TEMPORAL_REPRESENTATION_DIFFERENCE":
                repairs=list(rep_by_ep.get(eid,[]))
                obsids={str(l.get("observation_id") or "") for l in links_by_eid[eid]}
                for oid in obsids: repairs.extend(rep_by_obs.get(oid,[]))
                seen=set()
                for rp in repairs:
                    key=(rp.get("observation_id"),json.dumps(rp.get("new_temporal_binding"),sort_keys=True,default=str))
                    if key in seen: continue
                    seen.add(key)
                    for l in links_by_eid[eid]:
                        base=build5(l,city)
                        cand,used=repair_candidate(mon,base,eid,rp)
                        if not cand: continue
                        d=mon.classify_candidate(cand,city,episodes,manual_matching(eid))
                        attempts.append({"strategy":"frozen_repair_temporal_overlay","verdict":verdict(d),"used":used,
                                         "reason_codes":d.get("reason_codes"),"proposed":d.get("proposed_outcome")})
            # 2) accepted durable final_evidence factual fields, if exact target row exists.
            row,bucket,path=find_final_row(wt,city,eid)
            if row is not None:
                cand,used=final_candidate(mon,row,city,eid)
                d=mon.classify_candidate(cand,city,episodes,manual_matching(eid))
                attempts.append({"strategy":"durable_final_evidence_factual_adapter","verdict":verdict(d),"used":used,
                                 "artifact":path,"bucket_location":bucket,"reason_codes":d.get("reason_codes"),
                                 "proposed":d.get("proposed_outcome")})
            exact=next((a for a in attempts if a["verdict"]==fv),None)
            results.append({**{k:item[k] for k in ("city","episode_id","frozen_verdict","reason")},
                            "attempts":attempts,"exact_attempt":exact})
        recovered=[x for x in results if x["exact_attempt"]]
        summary={"target":86,"frozen_positives":dd["frozen_positives"],"recovered_exact":len(recovered),
                 "still_unrecovered":86-len(recovered),
                 "by_reason_recovered":dict(Counter(x["reason"] for x in recovered)),
                 "by_verdict_recovered":dict(Counter(x["frozen_verdict"] for x in recovered)),
                 "by_city_recovered":dict(Counter(x["city"] for x in recovered)),
                 "attempted_mismatch_only":sum(1 for x in results if x["attempts"] and not x["exact_attempt"]),
                 "no_attempt":sum(1 for x in results if not x["attempts"])}
        out.write_text(json.dumps({"summary":summary,"results":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("R86TRIAL="+json.dumps(summary,separators=(",",":")))
    finally:
        p.sh(["git","worktree","remove","--force",str(wt)],check=False)
        shutil.rmtree(tmp,ignore_errors=True)

if __name__=="__main__": main()
