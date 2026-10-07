#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, importlib.util, json, re, subprocess, sys
from collections import Counter
from datetime import timezone
from pathlib import Path

SNAPSHOT_COMMIT="efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAPSHOT_PATH="research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAPSHOT_BLOB="8a2f6bd33f879be9db978da59c12c34e61f6f843"
CLASSIFIER_COMMIT="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB="778469b74c2aa807d851cf2c2ee35cf4aa785589"
CUTOFF="2025-02-12"
EXPECTED=(145,57,209)

def run(*args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
    if p.returncode: raise RuntimeError("command failed: "+" ".join(args)+"\n"+p.stderr[-3000:])
    return p.stdout.strip()

def git_blob(commit,path): return run("git","rev-parse",f"{commit}:{path}")

def load_mod(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if not spec or not spec.loader: raise RuntimeError(f"cannot load {path}")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def strip_review(c):
    x=copy.deepcopy(c)
    x.pop("review_provenance",None)
    for k in list(x):
        if "review" in str(k).lower(): x.pop(k,None)
    return x

def parse_dt(monitor,v):
    try: return monitor.parse_dt(v)
    except Exception: return None

def current_state(replay, monitor, cands, ep, episodes):
    decisions=[]
    eid=ep["episode_id"]
    for c in cands:
        m=monitor.match_candidate_to_episodes(c,episodes)
        d=monitor.classify_candidate(c,"kyiv",episodes,m)
        decisions.append(d)
    strict=[d for d in decisions if d.get("proposed_outcome")=="approved_strict" and d.get("proposed_matched_episode_id")==eid]
    sens=[d for d in decisions if d.get("proposed_outcome")=="approved_sensitivity" and d.get("proposed_matched_episode_id")==eid]
    rev=[d for d in decisions if d.get("proposed_outcome")=="needs_review"]
    if strict: return "STRICT_EVENT_POSITIVE", replay.best_decision(strict)
    if sens: return "SENSITIVITY_EVENT_POSITIVE", replay.best_decision(sens)
    if rev or not decisions: return "NEEDS_REVIEW", replay.best_decision(rev or decisions)
    return "NO_CONFIRMED_EVENT", replay.best_decision(decisions)

def temporal_eval(monitor,c,episodes,target_id,decision):
    t=(decision.get("candidate_evidence") or {}).get("temporal_binding") or {}
    inf=(decision.get("candidate_evidence") or {}).get("single_episode_day_inference") or {}
    if t.get("present") and t.get("episode_specific") and str(t.get("episode_id") or "")==target_id:
        return "UNIQUE_ALERT_BINDING_SUPPORTED"
    near=t.get("near_boundary") or {}
    if near.get("present") and near.get("episode_specific") and str(near.get("episode_id") or "")==target_id:
        return "UNIQUE_ALERT_BINDING_SUPPORTED"
    if inf.get("present") and str(inf.get("episode_id") or "")==target_id:
        return "UNIQUE_ALERT_BINDING_SUPPORTED"
    ids=set(str(x) for x in (t.get("supported_episode_ids") or []) if x)
    if len(ids)>1: return "MULTIPLE_ALERTS_PLAUSIBLE"
    m=decision.get("matching") or {}
    if m.get("outcome")=="ambiguous_match": return "MULTIPLE_ALERTS_PLAUSIBLE"
    txt=monitor.classification_text(c)
    if re.search(r"\b(сьогодні|вранці|зранку|увечері|ввечері|вночі|цієї ночі|раніше|пізніше|today|this morning|this evening|overnight|earlier|later)\b",txt,re.I):
        return "TIME_TOO_BROAD"
    return "NO_EVENT_TIME"

def literal_dims(monitor,c,decision,target_id,episodes):
    text=monitor.classification_text(c)
    segs=monitor.classification_segments(c)
    attack=any(monitor.strict_attack_event_signal(s) for s in segs)
    exact=any(monitor.city_mentioned("kyiv",s) and monitor.strict_attack_event_signal(s) for s in segs)
    air=any(monitor.air_military_context(s) for s in segs)
    same=bool(((decision.get("candidate_evidence") or {}).get("same_attack_context") or {}).get("present"))
    if not same:
        same=any(monitor.city_mentioned("kyiv",s) and monitor.strict_attack_event_signal(s) and monitor.air_military_context(s) for s in segs)
    temporal=temporal_eval(monitor,c,episodes,target_id,decision)
    return {"attack":attack,"exact_city":exact,"air":air,"same_attack":same,"temporal":temporal,"text_len":len(text)}

def payload_complete(replay,cands):
    texts=[replay.evidence_text(c) for c in cands]
    return any(isinstance(t,str) and len(t.strip())>=12 for t in texts)

def episode_eval(replay,monitor,cands,ep,episodes):
    target_id=ep["episode_id"]
    if not cands or not payload_complete(replay,cands):
        return {
          "attack":"EVIDENCE_TEXT_INCOMPLETE","exact_city":"EVIDENCE_TEXT_INCOMPLETE",
          "air":"EVIDENCE_TEXT_INCOMPLETE","same_attack":"EVIDENCE_TEXT_INCOMPLETE",
          "temporal":"EVIDENCE_TEXT_INCOMPLETE","single_full":False,"composed_full":False,
          "payload_complete":False
        }
    stripped=[strip_review(c) for c in cands]
    rows=[]
    single_full=False
    temporal_statuses=[]
    for c in stripped:
        m=monitor.match_candidate_to_episodes(c,episodes)
        d=monitor.classify_candidate(c,"kyiv",episodes,m)
        dims=literal_dims(monitor,c,d,target_id,episodes)
        rows.append((c,d,dims))
        temporal_statuses.append(dims["temporal"])
        if dims["attack"] and dims["exact_city"] and dims["air"] and dims["same_attack"] and dims["temporal"]=="UNIQUE_ALERT_BINDING_SUPPORTED":
            single_full=True

    attack=any(x[2]["attack"] for x in rows)
    exact=any(x[2]["exact_city"] for x in rows)
    air=any(x[2]["air"] for x in rows)
    same=any(x[2]["same_attack"] for x in rows)

    # Safe episode-level composition using only stripped stored evidence.
    queue=[]
    for c,d,dm in rows:
        q=copy.deepcopy(c)
        mm=d.get("matching") or {}
        if mm.get("outcome")=="unique_match" and mm.get("matched_episode_id")==target_id:
            q["matched_episode_id"]=target_id
            q["status"]="needs_review"
            if not q.get("candidate_id"):
                q["candidate_id"]=replay.candidate_key(q)[:24]
            queue.append(q)
    composed=monitor.compose_episode_candidates("kyiv",ep,queue,episodes) if queue else {"final_composed_verdict":"no_composed_strict"}
    composed_full=composed.get("final_composed_verdict")=="approved_strict"
    if composed_full:
        attack=exact=air=same=True

    if "UNIQUE_ALERT_BINDING_SUPPORTED" in temporal_statuses or composed_full:
        temporal="UNIQUE_ALERT_BINDING_SUPPORTED"
    elif "MULTIPLE_ALERTS_PLAUSIBLE" in temporal_statuses:
        temporal="MULTIPLE_ALERTS_PLAUSIBLE"
    elif "TIME_TOO_BROAD" in temporal_statuses:
        temporal="TIME_TOO_BROAD"
    else:
        temporal="NO_EVENT_TIME"

    return {
      "attack":"YES" if attack else "NO",
      "exact_city":"YES" if exact else "NO",
      "air":"YES" if air else "NO",
      "same_attack":"YES" if same else "NO",
      "temporal":temporal,
      "single_full":single_full,
      "composed_full":composed_full,
      "payload_complete":True
    }

def current_gate(replay,best,state):
    if state in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"): return "none"
    if not best: return "other"
    g=replay.decision_first_failure(best)
    mp={
      "attack-event semantics":"qualifying attack-event semantics",
      "exact-city semantics":"exact Kyiv",
      "air context":"air context",
      "same-attack relation":"same attack",
      "temporal binding":"temporal composition",
      "alert ambiguity":"temporal composition",
      "missing evidence payload":"other",
      "other actual gate":"other"
    }
    return mp.get(g,"other")

def profile(rows):
    n=len(rows)
    if not n: return {}
    yes=lambda k:sum(1 for r in rows if r["evidence"][k]=="YES")
    temp=sum(1 for r in rows if r["evidence"]["temporal"]=="UNIQUE_ALERT_BINDING_SUPPORTED")
    complete=sum(1 for r in rows if r["evidence"]["payload_complete"])
    return {
      "n":n,
      "explicit_attack_event":{"count":yes("attack"),"rate":round(yes("attack")/n,4)},
      "exact_city":{"count":yes("exact_city"),"rate":round(yes("exact_city")/n,4)},
      "air_context":{"count":yes("air"),"rate":round(yes("air")/n,4)},
      "unique_temporal":{"count":temp,"rate":round(temp/n,4)},
      "payload_complete":{"count":complete,"rate":round(complete/n,4)}
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",required=True); ap.add_argument("--stack",required=True)
    ap.add_argument("--out",required=True); ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    out=Path(a.out)
    base={
      "schema_version":1,"kind":"kyiv_postcutoff_evidence_semantic_sufficiency",
      "actions_run_id":int(a.run_id),
      "frozen_snapshot":{"commit":SNAPSHOT_COMMIT,"path":SNAPSHOT_PATH,"blob":SNAPSHOT_BLOB},
      "authoritative_classifier":{"commit":CLASSIFIER_COMMIT,"path":CLASSIFIER_PATH,"blob":CLASSIFIER_BLOB},
      "mutation_confirmation":{
        "classifier_mutations":0,"parser_mutations":0,"temporal_representation_mutations":0,
        "alert_grouping_mutations":0,"source_evidence_mutations":0,"review_provenance_mutations":0,
        "classification_mutations":0,"historical_state_mutations":0,"queue_mutations":0,
        "persistence_mutations":0,"neon_db_queries":0,"neon_db_writes":0,"deployments":0
      }
    }
    try:
      if git_blob(SNAPSHOT_COMMIT,SNAPSHOT_PATH)!=SNAPSHOT_BLOB: raise RuntimeError("SNAPSHOT_BLOB_MISMATCH")
      if git_blob(CLASSIFIER_COMMIT,CLASSIFIER_PATH)!=CLASSIFIER_BLOB: raise RuntimeError("CLASSIFIER_BLOB_MISMATCH")
      replay=load_mod("replay",Path(".github/proof/kyiv_411_classification_continuity_replay.py"))
      stack=Path(a.stack)
      sys.path.insert(0,str(stack/"kyiv-air-alerts-grafana"/"scripts"))
      monitor=load_mod("monitor",stack/CLASSIFIER_PATH)
      data=json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
      class_path,class_rows,verdict_sem=replay.locate_classifications(data)
      arrays=replay.discover_arrays(data); table_records,idx=replay.build_index(arrays)
      table_records[class_path]=class_rows
      for i,r in enumerate(class_rows):
        for kv in replay.id_pairs(r,class_path):
          if (class_path,i) not in idx[kv]: idx[kv].append((class_path,i))
      kyiv_idx=[i for i,r in enumerate(class_rows) if replay.row_city(r)=="kyiv"]
      contexts={}
      episodes=[]; ep_for={}
      for i in kyiv_idx:
        recs=replay.related_records(class_path,class_rows,i,table_records,idx)
        pairs=replay.context_pairs(recs,class_path,i); contexts[i]=(recs,pairs)
        st,en=replay.row_bounds(class_rows[i],pairs)
        if not st or not en: raise RuntimeError(f"ALERT_BOUNDARY_MISSING:{i}")
        ep=monitor.make_episode("kyiv",st,en,source="frozen_authoritative_snapshot")
        episodes.append(ep); ep_for[i]=ep
      episodes.sort(key=lambda x:(x["alert_start"],x["alert_end"],x["episode_id"]))

      pos=[]; holds=[]; post=[]
      for i in kyiv_idx:
        pairs=contexts[i][1]; v=replay.row_verdict(class_rows[i],verdict_sem)
        st,_=replay.row_bounds(class_rows[i],pairs)
        date=st.date().isoformat() if st else None
        _,_,ev=replay.evidence_flags(pairs)
        if v in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"): pos.append(i)
        elif v=="NEEDS_REVIEW" and ev and date and date<=CUTOFF: holds.append(i)
        elif v=="NEEDS_REVIEW" and ev and date and date>CUTOFF: post.append(i)
      if (len(pos),len(holds),len(post))!=EXPECTED: raise RuntimeError(f"COHORT_MISMATCH:{len(pos)},{len(holds)},{len(post)}")

      led=[]
      cohort_map={**{i:"HISTORICAL_ACCEPTED_POSITIVE" for i in pos},**{i:"HISTORICAL_REVIEW_HOLD" for i in holds},**{i:"POST_CUTOFF" for i in post}}
      for i in pos+holds+post:
        recs,_=contexts[i]
        cands,_=replay.extract_candidates(recs,class_path,i)
        state,best=current_state(replay,monitor,cands,ep_for[i],episodes)
        ev=episode_eval(replay,monitor,cands,ep_for[i],episodes)
        led.append({"idx":i,"episode_id":ep_for[i]["episode_id"],"cohort":cohort_map[i],"current_state":state,"current_gate":current_gate(replay,best,state),"evidence":ev})

      post_rows=[r for r in led if r["cohort"]=="POST_CUTOFF"]
      cats=Counter(); gates=Counter()
      examples={k:[] for k in "ABCDEF"}
      for r in post_rows:
        e=r["evidence"]
        if not e["payload_complete"]:
          cat="D"
        else:
          non_temp=all(e[k]=="YES" for k in ("attack","exact_city","air","same_attack"))
          full=non_temp and e["temporal"]=="UNIQUE_ALERT_BINDING_SUPPORTED"
          if full and e["single_full"]:
            cat="A"
          elif full and (e["composed_full"] or not e["single_full"]):
            cat="B"
          elif non_temp and e["temporal"]=="MULTIPLE_ALERTS_PLAUSIBLE":
            cat="E"
          elif any(e[k]=="NO" for k in ("attack","exact_city","air","same_attack")) or e["temporal"] in ("NO_EVENT_TIME","TIME_TOO_BROAD"):
            cat="C"
          else:
            cat="F"
        r["category"]=cat; cats[cat]+=1
        if cat in ("A","B"): gates[r["current_gate"]]+=1
        if len(examples[cat])<5: examples[cat].append(r["episode_id"])

      recov=cats["A"]+cats["B"]
      hp=[r for r in led if r["cohort"]=="HISTORICAL_ACCEPTED_POSITIVE"]
      hh=[r for r in led if r["cohort"]=="HISTORICAL_REVIEW_HOLD"]
      pp=profile(post_rows); ph=profile(hp); hhold=profile(hh)
      diffs=[]
      for key,label in [("explicit_attack_event","explicit attack-event wording"),("exact_city","exact-city wording"),("air_context","air-context wording"),("unique_temporal","temporal specificity"),("payload_complete","evidence payload completeness")]:
        d=round(pp[key]["rate"]-ph[key]["rate"],4)
        diffs.append({"dimension":label,"postcutoff_rate":pp[key]["rate"],"historical_positive_rate":ph[key]["rate"],"difference_pp":round(d*100,1)})
      diffs.sort(key=lambda x:x["difference_pp"])
      materially_weaker=any(x["difference_pp"]<=-15 for x in diffs)

      if recov>=25:
        next_step="SEMANTIC EXTRACTION / COMPOSITION REPAIR"; verdict="KYIV POST-CUTOFF EVIDENCE SUFFICIENCY = EXTRACTION GAP DOMINANT"
      elif cats["E"]>max(cats["C"]+cats["D"],recov):
        next_step="TEMPORAL / ALERT ATTRIBUTION"; verdict="KYIV POST-CUTOFF EVIDENCE SUFFICIENCY = TEMPORAL GAP DOMINANT"
      elif recov<25 and (cats["C"]+cats["D"])>=(209/2):
        next_step="HISTORICAL EVIDENCE DISCOVERY / BACKFILL"; verdict="KYIV POST-CUTOFF EVIDENCE SUFFICIENCY = EVIDENCE GAP DOMINANT"
      else:
        next_step="MIXED"; verdict="KYIV POST-CUTOFF EVIDENCE SUFFICIENCY = MIXED"

      result={**base,
        "verdict":verdict,"episodes_audited":209,
        "category_counts":{
          "A_FULL_SEMANTICS_PRESENT_BUT_CLASSIFIER_FAILED_TO_DERIVE":cats["A"],
          "B_PARTIAL_SEMANTICS_PRESENT_EXTRACTION_OR_COMPOSITION_GAP":cats["B"],
          "C_EVIDENCE_GENUINELY_INSUFFICIENT":cats["C"],
          "D_EVIDENCE_PAYLOAD_INCOMPLETE":cats["D"],
          "E_ALERT_TEMPORAL_AMBIGUITY":cats["E"],
          "F_OTHER":cats["F"]},
        "existing_evidence_recoverable_ceiling_A_plus_B":recov,
        "top_failing_classifier_gates_within_A_plus_B":dict(gates.most_common()),
        "historical_control_profiles":{"historical_positives":ph,"historical_holds":hhold,"postcutoff_unresolved":pp},
        "strongest_evidence_content_differences_vs_historical_positives":diffs,
        "postcutoff_evidence_materially_weaker":materially_weaker,
        "primary_next_step":next_step,
        "representative_episode_ids":examples,
        "method_notes":{
          "review_provenance_used_as_positive_proof":False,
          "historical_labels_used_as_classifier_input":False,
          "public_web_used":False,
          "new_evidence_fetched":False,
          "evidence_support_evaluated_from_review_stripped_stored_text":True,
          "current_gate_measured_with_authoritative_classifier":True
        }}
      out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
      print(json.dumps({k:result[k] for k in ("verdict","episodes_audited","category_counts","existing_evidence_recoverable_ceiling_A_plus_B","top_failing_classifier_gates_within_A_plus_B","postcutoff_evidence_materially_weaker","primary_next_step","mutation_confirmation")},ensure_ascii=False,indent=2))
      return 0
    except Exception as exc:
      result={**base,"verdict":"KYIV POST-CUTOFF EVIDENCE SUFFICIENCY = BLOCKED","episodes_audited":0,"blocker":f"{type(exc).__name__}: {exc}"}
      out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
      print(json.dumps(result,ensure_ascii=False,indent=2)); return 2

if __name__=="__main__": raise SystemExit(main())
