#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, json, shutil, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import attack_event_multicity_classifier_parity as p
import attack_event_multicity_86case_recovery_trial as t

WORKER_REF="eaa77e2c2714d68a25dcd581c3194c1d394eb00a"
OUT_REL="research/attack_event_multicity_86case_representability_recovery_2026-10-07.json"
POS={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def disposition_for_bucket(bucket):
    return {
      "strict_events":"STRICT_EVENT_POSITIVE",
      "sensitivity_only_events":"SENSITIVITY_EVENT_POSITIVE",
      "review_events":"NEEDS_REVIEW",
      "ambiguous_events":"NEEDS_REVIEW",
    }.get(str(bucket or ""))

def category(v):
    return {"STRICT_EVENT_POSITIVE":"STRICT","SENSITIVITY_EVENT_POSITIVE":"SENSITIVITY",
            "NEEDS_REVIEW":"NEEDS_REVIEW","NO_CONFIRMED_EVENT":"NO_CONFIRMED"}.get(v,v)

def base_flags(d,eid):
    temporal=d.get("temporal_binding") or {}
    near=temporal.get("near_boundary") or {}
    inference=d.get("single_episode_day_inference") or {}
    return {
      "exact_city":bool((d.get("exact_city_classification_evidence") or {}).get("present")),
      "attack_event":bool((d.get("strict_explosion_evidence") or {}).get("present")),
      "aerial_war":bool((d.get("air_military_context") or {}).get("present")),
      "same_attack":bool((d.get("same_attack_context") or {}).get("present")),
      "strict_temporal":bool(temporal.get("present") and temporal.get("episode_specific") and str(temporal.get("episode_id") or "")==eid),
      "near_boundary":bool(near.get("present") and near.get("episode_specific") and str(near.get("episode_id") or "")==eid),
      "inferred_binding":bool(inference.get("present") and str(inference.get("episode_id") or "")==eid),
    }

def complete_input(flags):
    return flags["exact_city"] and flags["attack_event"] and flags["aerial_war"] and flags["same_attack"] and (
        flags["strict_temporal"] or flags["near_boundary"] or flags["inferred_binding"]
    )

def repaired_final_candidate(mon,row,city,eid):
    cand,used=t.final_candidate(mon,row,city,eid)
    prov=cand.get("review_provenance") or {}
    # A durable near-boundary/inferred relation is sensitivity-only provenance.
    # Do not simultaneously manufacture a strict episode binding from the same row.
    if "sensitivity_binding" in prov:
        prov.pop("temporal",None)
    cand["review_provenance"]=prov
    return cand,used

def blocker_from_flags(flags,reason,has_any_provenance,conflict=False):
    if conflict:
        return "AMBIGUOUS_DURABLE_DISPOSITION_CONFLICT"
    if not has_any_provenance:
        return "NO_EPISODE_SPECIFIC_DURABLE_CLASSIFIER_INPUT"
    if not flags.get("exact_city"): return "MISSING_DURABLE_EXACT_CITY_ROLE"
    if not flags.get("attack_event"): return "MISSING_DURABLE_ATTACK_EVENT_ROLE"
    if not flags.get("aerial_war"): return "MISSING_DURABLE_AERIAL_WAR_ROLE"
    if not flags.get("same_attack"): return "MISSING_DURABLE_SAME_ATTACK_LINKAGE"
    if not (flags.get("strict_temporal") or flags.get("near_boundary") or flags.get("inferred_binding")):
        return "MISSING_DURABLE_EPISODE_SPECIFIC_TEMPORAL_BINDING"
    return "AMBIGUOUS_NON_EQUIVALENT_DURABLE_REPRESENTATION"

def main():
    out=Path(sys.argv[1])
    run_id=str(sys.argv[2]) if len(sys.argv)>2 else "manual"
    tmp=Path(tempfile.mkdtemp(prefix="r86final-"))
    diag_path=tmp/"diag.json"
    subprocess.run([sys.executable,str(HERE/"attack_event_multicity_86case_recovery_diag.py"),str(diag_path)],
                   check=True,stdout=subprocess.DEVNULL)
    dd=json.loads(diag_path.read_text(encoding="utf-8"))
    ledger=dd["ledger"]
    assert len(ledger)==86 and dd["frozen_positives"]==80

    p.ensure_commit(WORKER_REF); p.ensure_commit(p.CAND_COMMIT)
    wt=tmp/"worker"; p.sh(["git","worktree","add","--detach",str(wt),WORKER_REF])
    try:
        candpath=wt/"kyiv-air-alerts-grafana"/"scripts"/"_authoritative_86case_final.py"
        candpath.write_bytes(p.git_bytes(p.CAND_COMMIT,p.CAND_PATH))
        sys.path.insert(0,str(candpath.parent)); mon=load(str(candpath),"auth86final")
        assert p.git("rev-parse",f"{p.CAND_COMMIT}:{p.CAND_PATH}")==p.CAND_BLOB

        snap=p.json_at(p.SNAP_COMMIT,p.SNAP_PATH)
        class_by_eid={str(r["historical_episode_id"]):r for r in snap.get("classifications") or []}
        classkey_to_eid={str(r["classification_key"]):str(r["historical_episode_id"]) for r in snap.get("classifications") or []}
        links_by_eid=defaultdict(list)
        for l in snap.get("source_links") or []:
            eid=classkey_to_eid.get(str(l.get("classification_key_v2") or ""))
            if eid: links_by_eid[eid].append(l)

        repair=p.json_at(p.REPAIR_COMMIT,p.REPAIR_PATH)
        changed=(repair.get("observations") or {}).get("changed_observations") or []
        rep_by_ep=defaultdict(list); rep_by_obs=defaultdict(list)
        for x in changed:
            for eid in x.get("affected_episode_ids") or []: rep_by_ep[str(eid)].append(x)
            if x.get("observation_id"): rep_by_obs[str(x["observation_id"])].append(x)

        final_ledger=[]
        for item in ledger:
            city=item["city"]; eid=item["episode_id"]; fv=item["frozen_verdict"]; reason=item["reason"]
            crow=class_by_eid[eid]; episode=p.episode_from_class(crow); episodes=[episode]
            required=[]
            materialization=None; decision=None; flags={}
            provenance_records=[]
            conflict=False
            best_incomplete_flags={}
            has_any=False

            # A) For five-city temporal differences, recover only when the original
            # candidate already has all non-temporal predicates and a frozen repair
            # overlay supplies the exact missing episode-specific temporal value.
            if reason=="TEMPORAL_REPRESENTATION_DIFFERENCE":
                repairs=[]
                for rp in rep_by_ep.get(eid,[]): repairs.append(rp)
                for l in links_by_eid[eid]:
                    oid=str(l.get("observation_id") or "")
                    for rp in rep_by_obs.get(oid,[]): repairs.append(rp)
                unique={}
                for rp in repairs:
                    key=(str(rp.get("observation_id") or ""),json.dumps(rp.get("new_temporal_binding"),sort_keys=True,default=str))
                    unique[key]=rp
                for l in sorted(links_by_eid[eid],key=lambda x:str(x.get("source_link_key") or "")):
                    base=t.build5(l,city); base["matched_episode_id"]=eid
                    bd=mon.classify_candidate(copy.deepcopy(base),city,episodes,t.manual_matching(eid))
                    bf=base_flags(bd,eid)
                    has_any=has_any or any(bf.values())
                    if sum(bool(v) for v in bf.values())>sum(bool(v) for v in best_incomplete_flags.values()):
                        best_incomplete_flags=bf
                    non_temporal_complete=bf["exact_city"] and bf["attack_event"] and bf["aerial_war"] and bf["same_attack"]
                    if not non_temporal_complete:
                        continue
                    for _k,rp in sorted(unique.items(),key=lambda kv:kv[0]):
                        cand,used=t.repair_candidate(mon,base,eid,rp)
                        if not cand: continue
                        cd=mon.classify_candidate(copy.deepcopy(cand),city,episodes,t.manual_matching(eid))
                        cf=base_flags(cd,eid)
                        provenance_records.append({
                          "artifact":p.REPAIR_PATH,"commit":p.REPAIR_COMMIT,
                          "observation_id":rp.get("observation_id"),
                          "required_value":"episode-specific event_time/temporal_binding",
                          "value":(rp.get("new_temporal_binding") or {}).get("event_time"),
                        })
                        if complete_input(cf):
                            materialization={"strategy":"FROZEN_REPAIR_TEMPORAL_OVERLAY","used":used,
                              "source_link_key":l.get("source_link_key"),"observation_id":rp.get("observation_id")}
                            decision=cd; flags=cf
                            required=["episode-specific temporal binding represented through accepted review-provenance input"]
                            break
                    if materialization: break

            # B) Existing durable final-evidence factual fields. Historical outcome
            # labels are a provenance-consistency guard only and never classifier input.
            row,bucket,fpath=t.find_final_row(wt,city,eid)
            if materialization is None and row is not None:
                stored=disposition_for_bucket(bucket)
                if stored is not None and stored!=fv:
                    conflict=True
                    provenance_records.append({"artifact":fpath,"commit":WORKER_REF,"bucket_location":bucket,
                                               "note":"durable artifact disposition conflicts with frozen snapshot disposition"})
                else:
                    cand,used=repaired_final_candidate(mon,row,city,eid)
                    cd=mon.classify_candidate(copy.deepcopy(cand),city,episodes,t.manual_matching(eid))
                    cf=base_flags(cd,eid); has_any=True; best_incomplete_flags=cf
                    provenance_records.append({"artifact":fpath,"commit":WORKER_REF,"bucket_location":bucket,
                                               "required_value":"structured factual review/temporal fields"})
                    if complete_input(cf):
                        materialization={"strategy":"DURABLE_FINAL_EVIDENCE_FACTUAL_ADAPTER","used":used,
                                         "artifact":fpath,"bucket_location":bucket}
                        decision=cd; flags=cf
                        required=["explicit factual role fields and episode-specific binding represented through accepted review-provenance input"]

            recovered=materialization is not None and decision is not None
            replay_v=t.verdict(decision) if recovered else None
            exact=(replay_v==fv) if recovered else None
            blocker=None if recovered else blocker_from_flags(best_incomplete_flags,reason,has_any,conflict)
            if reason=="INPUT_NOT_RECONSTRUCTABLE":
                if recovered:
                    input_class="RECOVERABLE_FROM_EXISTING_FROZEN_ARTIFACT"
                elif blocker.startswith("MISSING_DURABLE_") or blocker.startswith("AMBIGUOUS_"):
                    input_class="AMBIGUOUS"
                else:
                    input_class="GENUINELY_NOT_DURABLY_REPRESENTED"
            else:
                input_class=None

            final_ledger.append({
              "city":city,"episode_id":eid,"frozen_verdict":fv,"frozen_category":category(fv),
              "current_untestable_reason":reason,
              "required_classifier_input":required if recovered else [blocker],
              "required_value_provenance":provenance_records,
              "input_not_reconstructable_classification":input_class,
              "recovered":recovered,
              "shadow_materialization":materialization,
              "replay_verdict":replay_v,
              "replay_category":category(replay_v) if replay_v else None,
              "exact_verdict_match":exact,
              "replay_predicate_flags":flags if recovered else best_incomplete_flags,
              "remaining_blocker":blocker,
            })

        recovered=[x for x in final_ledger if x["recovered"]]
        mismatches=[x for x in recovered if not x["exact_verdict_match"]]
        matches=[x for x in recovered if x["exact_verdict_match"]]
        still=[x for x in final_ledger if not x["recovered"]]
        recovered_pos=[x for x in matches if x["frozen_verdict"] in POS]
        recovered_strict=sum(x["frozen_verdict"]=="STRICT_EVENT_POSITIVE" for x in matches)
        recovered_sens=sum(x["frozen_verdict"]=="SENSITIVITY_EVENT_POSITIVE" for x in matches)
        unsafe=sum(
          x["frozen_verdict"] in {"NO_CONFIRMED_EVENT","NEEDS_REVIEW"} and x["replay_verdict"] in POS
          for x in recovered
        )
        blocker_counts=dict(sorted(Counter(x["remaining_blocker"] for x in still).items()))
        input_classes=dict(sorted(Counter(x["input_not_reconstructable_classification"] for x in final_ledger
                                          if x["current_untestable_reason"]=="INPUT_NOT_RECONSTRUCTABLE").items()))
        total_coverage=26319+len(recovered)
        if mismatches:
            recommendation="SHARED ALIGNMENT NOT SAFE"
            verdict_text="MULTICITY PARITY REPRESENTABILITY RECOVERY = FAILED"
        elif len(recovered)==86:
            recommendation="SHARED 23-CITY CLASSIFIER ALIGNMENT SAFE"
            verdict_text="MULTICITY PARITY REPRESENTABILITY RECOVERY = COMPLETE"
        else:
            recommendation="SHARED ALIGNMENT STILL PARTIALLY UNPROVEN"
            verdict_text="MULTICITY PARITY REPRESENTABILITY RECOVERY = PARTIAL"

        payload={
          "schema_version":1,
          "proof":"MULTICITY AUTHORITATIVE CLASSIFIER 86-CASE REPRESENTABILITY RECOVERY",
          "run_id":run_id,
          "candidate_authoritative_classifier":{"commit":p.CAND_COMMIT,"blob":p.CAND_BLOB,"path":p.CAND_PATH},
          "accepted_predecessor":{"testable":26319,"total":26405,"exact_matches":26319,"mismatches":0},
          "summary":{
            "target_cases":86,
            "frozen_positives_among_86":dd["frozen_positives"],
            "temporal_representation_cases":59,
            "input_not_reconstructable_cases":27,
            "cases_recovered":len(recovered),
            "cases_still_untestable":len(still),
            "exact_verdict_matches_among_recovered":len(matches),
            "mismatches":len(mismatches),
            "recovered_positives_reproduced":len(recovered_pos),
            "recovered_STRICT_reproduced":recovered_strict,
            "recovered_SENSITIVITY_reproduced":recovered_sens,
            "unsafe_promotions":unsafe,
            "remaining_blocker_counts":blocker_counts,
            "input_not_reconstructable_resolution_classes":input_classes,
            "resulting_23_city_parity_coverage":{"numerator":total_coverage,"denominator":26405},
            "shared_live_alignment_recommendation":recommendation,
            "verdict":verdict_text,
          },
          "ledger":final_ledger,
          "mutation_confirmation":{
            "classifier_semantics":"unchanged","parser_semantics":"unchanged","temporal_semantics":"unchanged",
            "normalization_policy":"unchanged","source_evidence":"unchanged","canonical_state":"unchanged",
            "live_wiring":"unchanged","persistence":"unchanged","Neon_writes":0,"deployments":0,
            "historical_backfill":0,
            "proof_only_shadow_materialization":True,
          }
        }
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("R86FINAL="+json.dumps(payload["summary"],ensure_ascii=False,separators=(",",":")))
        if mismatches:
            for x in mismatches:
                print("R86MISMATCH="+json.dumps({"city":x["city"],"episode_id":x["episode_id"],
                    "frozen":x["frozen_verdict"],"replay":x["replay_verdict"]},separators=(",",":")))
    finally:
        p.sh(["git","worktree","remove","--force",str(wt)],check=False)
        shutil.rmtree(tmp,ignore_errors=True)

if __name__=="__main__":
    main()
