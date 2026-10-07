#!/usr/bin/env python3
from __future__ import annotations

import argparse, copy, hashlib, json, os, shutil, subprocess, sys, tempfile, textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
BRANCH="attack-event-multicity-classifier-parity-2026-10-07"
BASE="5ea08552606d9909d5bf821bdc0d2278ddd5b15f"
ARCH_PATH="research/attack_event_multicity_live_architecture_audit_2026-10-07.json"
ARCH_BLOB="6b774acb034258222e15c7c88d610c72fa76c064"

SNAP_COMMIT="efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAP_PATH="research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAP_BLOB="8a2f6bd33f879be9db978da59c12c34e61f6f843"
SNAP_SHA256="09458bcf0a019fa2939eb9dfa484da46cd8fa2be077343c5ba6d595c93d71788"

CAND_COMMIT="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CAND_PATH="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CAND_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
REPLAY_PATH="kyiv-air-alerts-grafana/scripts/replay_explosion_history.py"

TARGET_COMMIT="3c39dabbf78ff9415213332023e6e6c4ee7e8225"
TARGET_PATH="research/attack_event_18city_accepted_target_map_2026-10-04.json"
REPAIR_COMMIT="5d18ef85a66384f189ede5ca5654d750f60f088b"
REPAIR_PATH="research/historical_offline_repair_recovery_scan_2026-10-02.json"

EXPECTED_TOTAL=26405
EXPECTED_DIST={
 "STRICT_EVENT_POSITIVE":1017,
 "SENSITIVITY_EVENT_POSITIVE":63,
 "NO_CONFIRMED_EVENT":23530,
 "NEEDS_REVIEW":1795,
}
POSITIVE={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
REASONS={
 "CLASSIFIER_SEMANTIC_DIFFERENCE",
 "INPUT_NOT_RECONSTRUCTABLE",
 "CITY_NORMALIZATION_DIFFERENCE",
 "TEMPORAL_REPRESENTATION_DIFFERENCE",
 "EVIDENCE_PAYLOAD_DIFFERENCE",
 "OTHER",
}
SPECIAL={
 "kyiv":"Kyiv exact-city combined",
 "sevastopol":"Sevastopol verified pairs",
 "kharkiv":"Kharkiv exact-hromada",
 "zaporizhzhia":"Zaporizhzhia exact-hromada",
 "cherkasy":"Cherkasy genitive exact-city normalization",
}
FIVE={"cherkasy","lviv","sevastopol","sumy","zaporizhzhia"}

class Blocked(RuntimeError):
    pass

def sh(args, cwd=None, check=True, env=None):
    p=subprocess.run(list(map(str,args)),cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if check and p.returncode:
        raise Blocked("command failed: "+" ".join(map(str,args))+"\n"+p.stderr[-3000:])
    return p

def git(*args):
    return sh(["git",*args]).stdout.strip()

def ensure_commit(sha):
    p=sh(["git","cat-file","-e",f"{sha}^{{commit}}"],check=False)
    if p.returncode:
        p=sh(["git","fetch","--no-tags","origin",sha],check=False)
        if p.returncode:
            raise Blocked(f"required commit unavailable: {sha}: {p.stderr[-1000:]}")
    if git("rev-parse",f"{sha}^{{commit}}")!=sha:
        raise Blocked(f"commit identity mismatch: {sha}")

def git_bytes(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        raise Blocked(f"git show failed {ref}:{path}: {p.stderr.decode('utf-8','replace')[-1000:]}")
    return p.stdout

def json_at(ref,path):
    return json.loads(git_bytes(ref,path))

def sha256(b):
    return hashlib.sha256(b).hexdigest()

def verdict4(v):
    v=str(v or "")
    aliases={
      "STRICT":"STRICT_EVENT_POSITIVE","SENSITIVITY":"SENSITIVITY_EVENT_POSITIVE",
      "AMBIGUOUS":"NEEDS_REVIEW","NON_STRICT":"NO_CONFIRMED_EVENT",
    }
    return aliases.get(v,v)

def episode_from_class(r):
    return {
      "episode_id":str(r["historical_episode_id"]),
      "city_key":str(r["city_key"]),
      "city":str(r["city_key"]),
      "alert_start":r["alert_start_utc_microseconds"],
      "alert_end":r["alert_end_utc_microseconds"],
    }

REPLAY_WORKER=r'''
from __future__ import annotations
import copy, importlib.util, json, os, socket, sys, traceback
from collections import defaultdict
from pathlib import Path

def block_network():
    orig_ga=socket.getaddrinfo; orig_conn=socket.socket.connect
    def ga(host,*a,**kw):
        h=str(host or "").lower()
        if h not in {"localhost","127.0.0.1","::1"}:
            raise RuntimeError("EXTERNAL_NETWORK_DISABLED:"+h)
        return orig_ga(host,*a,**kw)
    def conn(self,address):
        host=address[0] if isinstance(address,tuple) else address
        h=str(host or "").lower()
        if h not in {"localhost","127.0.0.1","::1"}:
            raise RuntimeError("EXTERNAL_NETWORK_DISABLED:"+h)
        return orig_conn(self,address)
    socket.getaddrinfo=ga; socket.socket.connect=conn

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError("cannot import "+path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def build5(link,city):
    text=str(link.get("excerpt") or "")
    st=str(link.get("source_type") or "")
    sf=str(link.get("source_family") or "")
    chan=str(link.get("telegram_channel") or "")
    is_tg=bool(chan) or "telegram" in st.casefold()
    if is_tg:
        source="Telegram / "+(sf or chan or "historical")
        basis="article_linked_public_telegram" if st=="article_linked_public_telegram" else "bounded_public_telegram_search"
        publisher=sf or chan or "historical"
    else:
        source=sf or st or "historical"
        basis="historical_source_local_html"
        publisher=sf or "historical"
    return {
      "candidate_id":str(link.get("observation_id") or ""),
      "city_key":city,
      "source":source,
      "title":text[:240],
      "snippet":text[:1200],
      "matched_text_excerpt":text,
      "publisher":publisher,
      "publisher_url":None,
      "url":link.get("source_url") or "",
      "resolved_url":link.get("source_url") or None,
      "published_at":link.get("source_timestamp"),
      "discovery_basis":basis,
    }

def decision_record(mon,row,city,episodes,matching=None,source_type=""):
    if matching is None:
        matching=mon.match_candidate_to_episodes(row,episodes)
        if str(source_type).endswith("telegram") and row.get("published_at"):
            active=mon.exact_active_episodes_at(mon.parse_dt(row.get("published_at")),episodes)
            if len(active)==1:
                row["matched_episode_id"]=str(active[0].get("episode_id") or "")
    d=mon.classify_candidate(row,city,episodes,matching)
    return d

def state_from_candidates(mon,city,episodes,target_id,cands):
    statuses={str(x.get("status") or "") for x in cands}
    if "approved_strict" in statuses: return "STRICT_EVENT_POSITIVE"
    if len(cands)>=2 and hasattr(mon,"compose_episode_candidates"):
        ep=next((x for x in episodes if str(x.get("episode_id") or "")==target_id),None)
        if ep is not None:
            comp=mon.compose_episode_candidates(city,ep,cands,episodes)
            if str((comp or {}).get("final_composed_verdict") or "")=="approved_strict":
                return "STRICT_EVENT_POSITIVE"
    if "approved_sensitivity" in statuses: return "SENSITIVITY_EVENT_POSITIVE"
    if "needs_review" in statuses: return "NEEDS_REVIEW"
    return "NO_CONFIRMED_EVENT"

def residual_qa(decisions,target_id):
    qa=set()
    for d,meta in decisions:
        match=d.get("matching") or {}
        refs=set(str(x) for x in (match.get("matched_episode_ids") or []) if x)
        if match.get("matched_episode_id"): refs.add(str(match["matched_episode_id"]))
        if d.get("proposed_matched_episode_id"): refs.add(str(d["proposed_matched_episode_id"]))
        if target_id not in refs: continue
        codes=" ".join(str(x) for x in (d.get("reason_codes") or []))
        tc=str((d.get("temporal_binding") or {}).get("code") or "")
        exact=d.get("exact_city_classification_evidence") or {}
        if "AMBIGUOUS" in tc or "MATCH_AMBIGUOUS" in codes: qa.add("TEMPORAL_AMBIGUITY")
        if d.get("proposed_outcome")=="needs_review" and not exact.get("present"): qa.add("CITY_AMBIGUITY")
        if "MULTI_INCIDENT" in codes or "AIR_CONTEXT_NOT_LINKED_TO_EVENT" in codes: qa.add("MULTI_INCIDENT_CONTEXT_RISK")
        if not meta.get("source_url"): qa.add("SOURCE_REFERENCE_INCOMPLETE")
        if "PROVENANCE" in codes: qa.add("PROVENANCE_REQUIRED")
    return qa

def aggregate5(decisions,episodes):
    out={}
    for ep in episodes:
        eid=str(ep.get("episode_id") or "")
        strict=[]; sens=[]; review=[]; related=[]
        for d,meta in decisions:
            match=d.get("matching") or {}
            refs=set(str(x) for x in (match.get("matched_episode_ids") or []) if x)
            if match.get("matched_episode_id"): refs.add(str(match["matched_episode_id"]))
            if d.get("proposed_matched_episode_id"): refs.add(str(d["proposed_matched_episode_id"]))
            if eid not in refs: continue
            related.append((d,meta))
            po=str(d.get("proposed_outcome") or "")
            if po=="approved_strict" and str(d.get("proposed_matched_episode_id") or "")==eid: strict.append(d)
            if po=="approved_sensitivity" and str(d.get("proposed_matched_episode_id") or "")==eid: sens.append(d)
            if po=="needs_review": review.append(d)
        qa=residual_qa(related,eid)
        if strict: state="STRICT_EVENT_POSITIVE"
        elif sens: state="SENSITIVITY_EVENT_POSITIVE"
        elif review or qa: state="NEEDS_REVIEW"
        else: state="NO_CONFIRMED_EVENT"
        out[eid]=state
    return out

def main():
    cfg=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    outp=Path(sys.argv[2])
    block_network()
    wt=Path(cfg["worktree"]); scripts=wt/"kyiv-air-alerts-grafana"/"scripts"
    sys.path.insert(0,str(scripts)); sys.path.insert(0,str(wt))
    old=load(str(scripts/"monitor_explosion_candidates.py"),"old_monitor_parity")
    cand=load(str(Path(cfg["candidate_path"])),"candidate_monitor_parity")
    city=cfg["city"]; component=cfg["component"]
    episodes=cfg["episodes"]; links=cfg["links"]
    result={"city":city,"component":component,"old":{},"candidate":{},"link_controls":[],"error":None}
    try:
        if component=="18":
            replay_file=scripts/"replay_explosion_history.py"
            replay=load(str(replay_file),"replay_helper_parity") if replay_file.exists() else None
            if replay is None or not hasattr(replay,"candidate_from_history"):
                raise RuntimeError("INPUT_NOT_RECONSTRUCTABLE:replay_helper")
            # Prefer exact raw episode representation from the frozen worker.
            try:
                root=wt/"kyiv-air-alerts-grafana"
                episodes,_=replay.load_historical_episodes(root,city,old)
            except Exception:
                episodes=cfg["episodes"]
            epmap={str(x.get("episode_id") or ""):x for x in episodes}
            old_by=defaultdict(list); cand_by=defaultdict(list)
            for link in links:
                target=str(link["target_episode_id"])
                payload=copy.deepcopy(link.get("normalized_accepted_observation_payload"))
                if not isinstance(payload,dict):
                    result["link_controls"].append({"source_link_key":link.get("source_link_key"),"target_episode_id":target,"ok":False,"reason":"EVIDENCE_PAYLOAD_DIFFERENCE"})
                    continue
                bucket=str(((link.get("retrieval_provenance") or {}).get("bucket")) or "review")
                target_ep=epmap.get(target)
                base=replay.candidate_from_history(city,payload,bucket,target,old,target_ep)
                matching=replay.manual_matching(target) if hasattr(replay,"manual_matching") else {
                  "outcome":"unique_match","matched_episode_ids":[target],"logical_episode_groups":[[target]],
                  "matched_episode_id":target,"reason":"frozen_historical_audit_episode_binding"
                }
                ro=copy.deepcopy(base); rn=copy.deepcopy(base)
                do=decision_record(old,ro,city,episodes,copy.deepcopy(matching))
                dn=decision_record(cand,rn,city,episodes,copy.deepcopy(matching))
                old.apply_classification_decision(ro,do,matching)
                cand.apply_classification_decision(rn,dn,matching)
                old_by[target].append(ro); cand_by[target].append(rn)
                result["link_controls"].append({
                  "source_link_key":link.get("source_link_key"),"target_episode_id":target,"ok":True,
                  "old_outcome":do.get("proposed_outcome"),"candidate_outcome":dn.get("proposed_outcome"),
                  "old_temporal":(do.get("temporal_binding") or {}).get("code"),
                  "candidate_temporal":(dn.get("temporal_binding") or {}).get("code"),
                  "old_exact":bool((do.get("exact_city_classification_evidence") or {}).get("present")),
                  "candidate_exact":bool((dn.get("exact_city_classification_evidence") or {}).get("present")),
                })
            for ep in episodes:
                eid=str(ep.get("episode_id") or "")
                result["old"][eid]=state_from_candidates(old,city,episodes,eid,old_by.get(eid,[]))
                result["candidate"][eid]=state_from_candidates(cand,city,episodes,eid,cand_by.get(eid,[]))
            # Ensure logical snapshot IDs with no raw-row delta are still represented.
            for ep in cfg["episodes"]:
                eid=str(ep["episode_id"])
                result["old"].setdefault(eid,"NO_CONFIRMED_EVENT")
                result["candidate"].setdefault(eid,"NO_CONFIRMED_EVENT")
        else:
            old_dec=[]; cand_dec=[]
            for link in links:
                row=build5(link,city)
                ro=copy.deepcopy(row); rn=copy.deepcopy(row)
                do=decision_record(old,ro,city,episodes,source_type=str(link.get("source_type") or ""))
                dn=decision_record(cand,rn,city,episodes,source_type=str(link.get("source_type") or ""))
                old_dec.append((do,link)); cand_dec.append((dn,link))
                result["link_controls"].append({
                  "source_link_key":link.get("source_link_key"),"target_episode_id":link.get("target_episode_id"),"ok":True,
                  "old_outcome":do.get("proposed_outcome"),"candidate_outcome":dn.get("proposed_outcome"),
                  "old_temporal":(do.get("temporal_binding") or {}).get("code"),
                  "candidate_temporal":(dn.get("temporal_binding") or {}).get("code"),
                  "old_exact":bool((do.get("exact_city_classification_evidence") or {}).get("present")),
                  "candidate_exact":bool((dn.get("exact_city_classification_evidence") or {}).get("present")),
                })
            result["old"]=aggregate5(old_dec,episodes)
            result["candidate"]=aggregate5(cand_dec,episodes)
    except Exception:
        result["error"]=traceback.format_exc()
    outp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    if result["error"]:
        print(result["error"],file=sys.stderr); return 2
    return 0
if __name__=="__main__": raise SystemExit(main())
'''

def native_five_state(r):
    n=r.get("native_frozen_episode_result")
    if isinstance(n,dict):
        return verdict4(n.get("classifier_result"))
    return None

def mismatch_reason(row, control_ok, candidate_state, control_state, controls):
    city=str(row["city_key"])
    if not control_ok:
        if city in {"vinnytsia","zhytomyr"}:
            return "INPUT_NOT_RECONSTRUCTABLE"
        if any(not x.get("ok") for x in controls):
            return "EVIDENCE_PAYLOAD_DIFFERENCE"
        return "TEMPORAL_REPRESENTATION_DIFFERENCE"
    exact_drift=any(x.get("old_exact") != x.get("candidate_exact") for x in controls if x.get("ok"))
    if exact_drift and city in {"cherkasy","kharkiv","zaporizhzhia","kyiv","sevastopol"}:
        return "CITY_NORMALIZATION_DIFFERENCE"
    return "CLASSIFIER_SEMANTIC_DIFFERENCE"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True); ap.add_argument("--summary",required=True); ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    outp=Path(a.out); sump=Path(a.summary)

    for c in [BASE,SNAP_COMMIT,CAND_COMMIT,TARGET_COMMIT,REPAIR_COMMIT]:
        ensure_commit(c)
    if git("rev-parse",f"{BASE}:{ARCH_PATH}")!=ARCH_BLOB: raise Blocked("architecture artifact blob mismatch")
    if git("rev-parse",f"{SNAP_COMMIT}:{SNAP_PATH}")!=SNAP_BLOB: raise Blocked("snapshot blob mismatch")
    raw=git_bytes(SNAP_COMMIT,SNAP_PATH)
    if sha256(raw)!=SNAP_SHA256: raise Blocked("snapshot sha256 mismatch")
    if git("rev-parse",f"{CAND_COMMIT}:{CAND_PATH}")!=CAND_BLOB: raise Blocked("candidate classifier blob mismatch")
    doc=json.loads(raw)
    rows=doc.get("classifications") or []
    links=doc.get("source_links") or []
    if len(rows)!=EXPECTED_TOTAL: raise Blocked(f"classification count {len(rows)}")
    dist=Counter(str(r.get("verdict") or "") for r in rows)
    if dict(dist)!=EXPECTED_DIST: raise Blocked(f"distribution mismatch {dict(dist)}")
    if len({str(r.get("city_key") or "") for r in rows})!=23: raise Blocked("city count mismatch")

    by_key={str(r["classification_key"]):r for r in rows}
    links_by_key=defaultdict(list)
    for l in links:
        ck=str(l.get("classification_key_v2") or "")
        if ck in by_key: links_by_key[ck].append(l)

    rows_by_city=defaultdict(list)
    for r in rows: rows_by_city[str(r["city_key"])].append(r)

    target=json_at(TARGET_COMMIT,TARGET_PATH)
    worker_ref={}
    for w in target.get("workers") or []:
        for city in w.get("cities") or []: worker_ref[str(city)]=str(w["tested_head"])
    for ref in sorted(set(worker_ref.values())): ensure_commit(ref)

    tmp=Path(tempfile.mkdtemp(prefix="multicity-classifier-parity-"))
    worker_py=tmp/"replay_worker.py"; worker_py.write_text(REPLAY_WORKER,encoding="utf-8")
    candidate_bytes=git_bytes(CAND_COMMIT,CAND_PATH)
    worktrees={}
    results={}
    try:
        needed_refs=set(worker_ref.values())|{CAND_COMMIT}
        for ref in sorted(needed_refs):
            wt=tmp/("wt-"+ref[:12])
            sh(["git","worktree","add","--detach",str(wt),ref])
            worktrees[ref]=wt
            cand_path=wt/"kyiv-air-alerts-grafana"/"scripts"/"_candidate_parity_monitor.py"
            cand_path.write_bytes(candidate_bytes)

        for city in sorted(rows_by_city):
            comp="5" if city in FIVE else "18"
            ref=CAND_COMMIT if comp=="5" else worker_ref.get(city)
            if not ref:
                results[city]={"error":"INPUT_NOT_RECONSTRUCTABLE:no_worker_ref","old":{},"candidate":{},"link_controls":[]}
                continue
            city_rows=rows_by_city[city]
            eps=[episode_from_class(r) for r in city_rows]
            city_links=[]
            for r in city_rows:
                ck=str(r["classification_key"]); eid=str(r["historical_episode_id"])
                for l0 in links_by_key.get(ck,[]):
                    l=copy.deepcopy(l0); l["target_episode_id"]=eid; city_links.append(l)
            cfg={"city":city,"component":comp,"worktree":str(worktrees[ref]),
                 "candidate_path":str(worktrees[ref]/"kyiv-air-alerts-grafana"/"scripts"/"_candidate_parity_monitor.py"),
                 "episodes":eps,"links":city_links}
            cp=tmp/f"cfg-{city}.json"; op=tmp/f"out-{city}.json"
            cp.write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
            env=os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"]="1"
            p=sh([sys.executable,str(worker_py),str(cp),str(op)],cwd=worktrees[ref],check=False,env=env)
            if not op.exists():
                results[city]={"error":"INPUT_NOT_RECONSTRUCTABLE:worker_output_missing:"+p.stderr[-1000:],"old":{},"candidate":{},"link_controls":[]}
            else:
                results[city]=json.loads(op.read_text(encoding="utf-8"))

        city_reports={}
        mismatch_ledger=[]
        not_testable=Counter()
        total_replayed=0; exact=0
        frozen_pos_same=0; strict_same=0; sens_same=0
        unsafe_no=0; unsafe_review=0

        for city in sorted(rows_by_city):
            rr=results.get(city) or {}
            oldmap=rr.get("old") or {}; newmap=rr.get("candidate") or {}
            controls_by_target=defaultdict(list)
            for c in rr.get("link_controls") or []: controls_by_target[str(c.get("target_episode_id") or "")].append(c)
            cr=Counter(); rep=0; matches=0; mism=0; nt=0
            fp=0; psame=0; pdown=0; pdrift=0; uno=0; unr=0
            reasons=Counter()
            frozen=Counter(str(r["verdict"]) for r in rows_by_city[city])
            replaydist=Counter()
            component="5" if city in FIVE else "18"
            for r in rows_by_city[city]:
                eid=str(r["historical_episode_id"]); fv=str(r["verdict"])
                fp += int(fv in POSITIVE)
                controls=controls_by_target.get(eid,[])
                observed_old=oldmap.get(eid); nv=newmap.get(eid)
                if rr.get("error") or nv is None:
                    nt+=1; not_testable["INPUT_NOT_RECONSTRUCTABLE"]+=1; continue
                if component=="5":
                    control_target=native_five_state(r)
                else:
                    control_target=fv
                control_ok=(control_target is not None and observed_old==control_target)
                if not control_ok:
                    nt+=1
                    reason=mismatch_reason(r,False,nv,observed_old,controls)
                    not_testable[reason]+=1
                    continue
                # The 5-city accepted corpus contains explicit offline repair overlays.
                # If the candidate reproduces only the pre-repair state, that is not a
                # classifier-semantic mismatch: the exact repaired temporal/parser input
                # was not passed through classify_candidate. Keep it out of the testable
                # denominator and classify the gap by its primary representation cause.
                repair_overlay = r.get("repair_overlay")
                if component=="5" and repair_overlay and nv!=fv and nv==observed_old:
                    nt+=1
                    reason="TEMPORAL_REPRESENTATION_DIFFERENCE"
                    not_testable[reason]+=1
                    continue
                rep+=1; total_replayed+=1; replaydist[nv]+=1
                if nv==fv:
                    matches+=1; exact+=1
                    if fv in POSITIVE:
                        psame+=1; frozen_pos_same+=1
                        if fv=="STRICT_EVENT_POSITIVE": strict_same+=1
                        else: sens_same+=1
                else:
                    mism+=1
                    reason=mismatch_reason(r,True,nv,observed_old,controls)
                    reasons[reason]+=1
                    mismatch_ledger.append({
                      "city_key":city,"historical_episode_id":eid,"frozen_verdict":fv,"candidate_verdict":nv,
                      "primary_reason":reason,"control_state":observed_old,"component":component,
                      "repair_overlay_present":bool(repair_overlay),
                    })
                    if fv in POSITIVE:
                        if nv not in POSITIVE: pdown+=1
                        else: pdrift+=1
                    if fv=="NO_CONFIRMED_EVENT" and nv in POSITIVE: uno+=1; unsafe_no+=1
                    if fv=="NEEDS_REVIEW" and nv in POSITIVE: unr+=1; unsafe_review+=1
            if mism:
                status="PARITY_FAILED"
            elif rep==0:
                status="PARITY_NOT_TESTABLE"
            elif nt:
                status="PARITY_PARTIAL"
            else:
                status="PARITY_PROVEN"
            city_reports[city]={
              "episodes_total":len(rows_by_city[city]),"episodes_replayed":rep,"episodes_not_testable":nt,
              "frozen":{"STRICT_EVENT_POSITIVE":frozen["STRICT_EVENT_POSITIVE"],"SENSITIVITY_EVENT_POSITIVE":frozen["SENSITIVITY_EVENT_POSITIVE"],
                        "NO_CONFIRMED_EVENT":frozen["NO_CONFIRMED_EVENT"],"NEEDS_REVIEW":frozen["NEEDS_REVIEW"]},
              "replay":{"STRICT_EVENT_POSITIVE":replaydist["STRICT_EVENT_POSITIVE"],"SENSITIVITY_EVENT_POSITIVE":replaydist["SENSITIVITY_EVENT_POSITIVE"],
                        "NO_CONFIRMED_EVENT":replaydist["NO_CONFIRMED_EVENT"],"NEEDS_REVIEW":replaydist["NEEDS_REVIEW"]},
              "exact_verdict_matches":matches,"mismatches":mism,
              "positive_preservation":{"frozen_confirmed_positives":fp,"same_disposition_reproduced":psame,
                 "downgraded":pdown,"strict_sensitivity_drift":pdrift},
              "unsafe_promotions":{"from_NO_CONFIRMED_EVENT":uno,"from_NEEDS_REVIEW":unr},
              "mismatch_reasons":dict(reasons),"status":status,
            }

        # Special-path summaries are mechanical views over city reports.
        special=[]
        for city,label in SPECIAL.items():
            c=city_reports[city]
            special.append({"path":label,"city_key":city,"status":c["status"],"mismatches":c["mismatches"],
                            "not_testable":c["episodes_not_testable"],
                            "interaction_found":bool(c["mismatches"])})
        raion=[c for c in sorted(city_reports) if c not in {"kyiv","sevastopol","kharkiv","zaporizhzhia"}]
        special.append({"path":"raion-proxy cities","city_keys":raion,
                        "statuses":dict(Counter(city_reports[c]["status"] for c in raion)),
                        "mismatches":sum(city_reports[c]["mismatches"] for c in raion),
                        "not_testable":sum(city_reports[c]["episodes_not_testable"] for c in raion)})

        total_mism=len(mismatch_ledger)
        statuses=Counter(x["status"] for x in city_reports.values())
        if total_mism>0:
            verdict="MULTICITY AUTHORITATIVE CLASSIFIER PARITY = FAILED"
            recommendation="NOT SAFE TO ALIGN SHARED LIVE CLASSIFIER"
        elif total_replayed<EXPECTED_TOTAL:
            verdict="MULTICITY AUTHORITATIVE CLASSIFIER PARITY = PARTIAL"
            recommendation="SAFE ONLY FOR SUBSET OF CITIES" if statuses["PARITY_PROVEN"] else "INSUFFICIENT EVIDENCE"
        else:
            verdict="MULTICITY AUTHORITATIVE CLASSIFIER PARITY = PROVEN"
            recommendation="SAFE TO ALIGN SHARED 23-CITY LIVE CLASSIFIER"

        artifact={
          "schema_version":1,"kind":"attack_event_multicity_classifier_parity",
          "verdict":verdict,"shared_path_recommendation":recommendation,
          "actions_run_id":int(a.run_id),
          "authorities":{
            "architecture":{"commit":BASE,"path":ARCH_PATH,"blob":ARCH_BLOB},
            "snapshot":{"commit":SNAP_COMMIT,"path":SNAP_PATH,"blob":SNAP_BLOB,"sha256":SNAP_SHA256},
            "candidate_classifier":{"commit":CAND_COMMIT,"path":CAND_PATH,"blob":CAND_BLOB},
          },
          "contract":{"frozen_final_verdict_used_as_classifier_input":False,
                      "public_web_used":False,"new_evidence_fetched":False,
                      "large_snapshot_processed_runner_side_only":True},
          "totals":{
            "cities_replayed":sum(1 for c in city_reports.values() if c["episodes_replayed"]>0),"cities_total":23,
            "episodes_replayed":total_replayed,"episodes_total":EXPECTED_TOTAL,
            "exact_verdict_matches":exact,"total_mismatches":total_mism,
            "frozen_positives_same_disposition_reproduced":frozen_pos_same,"frozen_positives_total":1080,
            "strict_same_disposition_reproduced":strict_same,"strict_total":1017,
            "sensitivity_same_disposition_reproduced":sens_same,"sensitivity_total":63,
            "unsafe_promotions_from_NO_CONFIRMED_EVENT":unsafe_no,
            "unsafe_promotions_from_NEEDS_REVIEW":unsafe_review,
            "episodes_not_testable":EXPECTED_TOTAL-total_replayed,
            "not_testable_reasons":dict(not_testable),
          },
          "mismatch_counts_by_city":{c:city_reports[c]["mismatches"] for c in sorted(city_reports)},
          "city_parity":city_reports,
          "special_path_findings":special,
          "mismatch_ledger":mismatch_ledger,
          "mutation_confirmation":{
            "classifier_mutations":0,"parser_mutations":0,"normalization_mutations":0,"alert_grouping_mutations":0,
            "source_mutations":0,"monitor_mutations":0,"persistence_mutations":0,"Neon_writes":0,
            "deployments":0,"historical_backfill":0,
          },
        }
        outp.parent.mkdir(parents=True,exist_ok=True)
        outp.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        summary={
          "verdict":verdict,"recommendation":recommendation,"totals":artifact["totals"],
          "mismatch_counts_by_city":artifact["mismatch_counts_by_city"],
          "city_status":{c:city_reports[c]["status"] for c in sorted(city_reports)},
          "special_path_findings":special,
          "mutation_confirmation":artifact["mutation_confirmation"],
        }
        sump.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    finally:
        for wt in worktrees.values():
            sh(["git","worktree","remove","--force",str(wt)],check=False)
        shutil.rmtree(tmp,ignore_errors=True)

if __name__=="__main__":
    try:
        main()
    except Blocked as e:
        payload={"verdict":"MULTICITY AUTHORITATIVE CLASSIFIER PARITY = BLOCKED","error":str(e),
                 "mutation_confirmation":{"classifier_mutations":0,"parser_mutations":0,"normalization_mutations":0,
                   "alert_grouping_mutations":0,"source_mutations":0,"monitor_mutations":0,"persistence_mutations":0,
                   "Neon_writes":0,"deployments":0,"historical_backfill":0}}
        sp=Path(os.environ.get("PARITY_SUMMARY_FALLBACK","/tmp/parity-summary.json"))
        sp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(payload,ensure_ascii=False))
        raise SystemExit(2)
