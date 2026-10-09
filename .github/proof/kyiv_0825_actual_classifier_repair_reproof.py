#!/usr/bin/env python3
"""Bounded frozen 67-episode actual-classifier baseline and repaired replay."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
REPAIR = "c5dd5fec6fe8f9a3fa0bbdefdd2cf71cee2ff801"
OLD_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
NEW_BLOB = "4019b8374dcc44846df04ed0cc41356652214bff"
DIAG = "ba3cc8b04a4c689c17b223b9c1a989928c0b397a"
PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
TARGET_C = "f0882d6580bb10476195589f"
TARGET_E = "cfd8acaf2ae96fb3ab6508d6"
SOURCES = ("5.ua", "zaxid.net", "kyiv.novyny.live")
POS = ("STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE")
EXPECTED_HASHES = {"discovery":"fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
"native":"bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
"normalized":"e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d"}
SUPPORT_COMMIT = "b749e0195c4ec1b2262c998e381a92277a89a5e9"
SUPPORT = [
".github/proof/kyiv_immutable_source_eligibility_expansion_pilot.py",
".github/proof/kyiv_new_immutable_development_replay.py",
".github/proof/kyiv_historical_discovery_calibration_pilot.py",
"research/kyiv_immutable_development_source_set_freeze_2026-10-09.json",
"research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json",
]
def require(v, message):
    if not v: raise RuntimeError(message)
def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()
def canonical(v):
    return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def sha(v):
    return hashlib.sha256(v).hexdigest()
def install_support():
    # Only repository-pinned proof code; never evidence acquisition.
    for path in SUPPORT:
        dest=ROOT/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git","show",SUPPORT_COMMIT+":"+path],cwd=ROOT))
    require(git("rev-parse",BASE+":"+PATH)==OLD_BLOB,"AUTHORITATIVE_CLASSIFIER_BASE_MISMATCH")
    require(git("rev-parse",REPAIR+":"+PATH)==NEW_BLOB,"REPAIRED_CLASSIFIER_BLOB_MISMATCH")
    require(git("rev-parse","HEAD:"+PATH)==NEW_BLOB,"PROOF_HEAD_CLASSIFIER_CHANGED")
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def ordinal_trace(mon, selection):
    original=mon.exact_city_classification_evidence
    def wrapped(city,row):
        out=original(city,row)
        all_segments=[s for s in mon.classification_segments(row) if mon.city_mentioned(city,s)]
        chosen=list(out["segments"])
        ordinals=[]
        low=0
        for segment in chosen:
            idx=next((i for i in range(low,len(all_segments)) if all_segments[i]==segment),None)
            require(idx is not None,"SELECTED_SEGMENT_NOT_IN_SOURCE_ORDER")
            ordinals.append(idx+1);low=idx+1
        cid=row.get("candidate_id")
        if cid:
            existing=selection.setdefault(cid,ordinals)
            require(existing==ordinals,"INCONSISTENT_CANDIDATE_SELECTION")
        return out
    mon.exact_city_classification_evidence=wrapped
def prepare(mode, acquisition, prior):
    install_support()
    sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
    pilot=load(ROOT/SUPPORT[0],"frozen_expansion_pilot")
    manifest=json.loads((ROOT/SUPPORT[3]).read_text())["selected_source_set_manifest"]
    require(manifest["included_source_families"]==pilot.BASE_SOURCES,"SOURCE_MANIFEST_CHANGED")
    require(manifest["corpus_hashes_sha256"]==EXPECTED_HASHES,"MANIFEST_CORPUS_HASH_MISMATCH")
    pilot.verification=lambda:manifest
    offline=pilot.Offline(acquisition,prior)
    if mode=="repaired":
        offline.monitor=load(ROOT/PATH,"isolated_repaired_classifier")
    return offline
def run_one(mode, acquisition, prior, output):
    offline=prepare(mode,acquisition,prior)
    try:
        selected={}
        ordinal_trace(offline.monitor,selected)
        rows=offline.replay(SOURCES)
        require(len(rows)==67 and sum(r["candidate_count"] for r in rows)==105,"FROZEN_COHORT_COUNT_MISMATCH")
        require(len(selected)==105,"CANDIDATE_ORDINAL_TRACE_INCOMPLETE")
        for row in rows:
            for c in row["candidates"]:
                require(c["candidate_id"] in selected,"MISSING_CANDIDATE_SELECTION")
                c["selected_ordinals"]=selected[c["candidate_id"]]
        normalized=[{
            "episode_id":r["episode_id"],"truth":r["truth_label"],"final":r["final"],
            "candidates":[{
                "candidate_id":c["candidate_id"],"family":c["family"],
                "url":c["url"],"text_sha256":c["text_sha256"],
                "selected_ordinals":c["selected_ordinals"],
                "classifier_outcome":c["classifier_outcome"],
                "classifier_episode_id":c["classifier_episode_id"],
                "temporal_code":c["temporal_binding"].get("code"),
                "reason_codes":c["reason_codes"],"classifier_error":c["classifier_error"],
            } for c in r["candidates"]]
        } for r in rows]
        result={"mode":mode,"episodes":normalized,"fingerprint":sha(canonical(normalized)),
                "corpus_hashes":EXPECTED_HASHES,"network_evidence_fetches":0,
                "blind_inspected":False,"historical_backfill_started":False,
                "neon_queries":0,"neon_writes":0,"production_mutations":0}
        output.write_bytes(canonical(result))
        print(mode.upper()+"_FINGERPRINT="+result["fingerprint"],flush=True)
    finally:
        offline.close()
def finalize(base_path,a_path,b_path,output):
    baseline=json.loads(base_path.read_text())
    a=json.loads(a_path.read_text())
    b=json.loads(b_path.read_text())
    require(a["fingerprint"]==b["fingerprint"] and a["episodes"]==b["episodes"],"REPAIRED_CLASSIFIER_REPLAY_NOT_DETERMINISTIC")
    old={r["episode_id"]:r for r in baseline["episodes"]}
    new={r["episode_id"]:r for r in a["episodes"]}
    require(len(old)==len(new)==67 and set(old)==set(new),"EPISODE_UNIVERSE_CHANGED")
    oldc={c["candidate_id"]:(e,c) for e in old.values() for c in e["candidates"]}
    newc={c["candidate_id"]:(e,c) for e in new.values() for c in e["candidates"]}
    require(len(oldc)==len(newc)==105 and set(oldc)==set(newc),"REPAIR_MUTATED_CANDIDATE_UNIVERSE")
    changed_selection=[]
    changed_classifier=[]
    for cid,(oe,oc) in oldc.items():
        ne,nc=newc[cid]
        require(oe["episode_id"]==ne["episode_id"] and
          all(oc[k]==nc[k] for k in ("family","url","text_sha256")),"CANDIDATE_IDENTITY_CHANGED:"+cid)
        if oc["selected_ordinals"]!=nc["selected_ordinals"]:changed_selection.append(cid)
        if (oc["classifier_outcome"],oc["classifier_episode_id"])!=(nc["classifier_outcome"],nc["classifier_episode_id"]):
            changed_classifier.append(cid)
    changed_episodes=[eid for eid in old if old[eid]["final"]!=new[eid]["final"]]
    positives=[eid for eid in old if old[eid]["truth"] in POS]
    holds=[eid for eid in old if old[eid]["truth"]=="HOLD_CONTROL"]
    require(len(positives)==48 and len(holds)==19,"COHORT_TRUTH_CHANGED")
    def metrics(rows):
        p=[rows[e] for e in positives]
        h=[rows[e] for e in holds]
        return {"candidate_covered":sum(bool(r["candidates"]) for r in p),
          "strict":sum(r["final"]=="STRICT_EVENT_POSITIVE" for r in p),
          "sensitivity":sum(r["final"]=="SENSITIVITY_EVENT_POSITIVE" for r in p),
          "final_positives":sum(r["final"] in POS for r in p),
          "hold_strict":sum(r["final"]=="STRICT_EVENT_POSITIVE" for r in h),
          "hold_sensitivity":sum(r["final"]=="SENSITIVITY_EVENT_POSITIVE" for r in h)}
    bm=metrics(old);am=metrics(new)
    holds_safe=all(old[e]==new[e] for e in holds)
    previous_positives_safe=all(new[e]["final"]==old[e]["final"] for e in positives if old[e]["final"] in POS)
    target=next((c for c in new[TARGET_E]["candidates"] if c["candidate_id"]==TARGET_C),{})
    scope_ok=changed_selection==[TARGET_C] and changed_episodes==[TARGET_E]
    target_ok=(target.get("selected_ordinals")==[1,4,7,8] and
        target.get("temporal_code")=="TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE" and
        target.get("classifier_outcome")=="approved_strict" and
        target.get("classifier_episode_id")==TARGET_E and new[TARGET_E]["final"]=="STRICT_EVENT_POSITIVE")
    metrics_ok=(bm=={"candidate_covered":31,"strict":3,"sensitivity":2,"final_positives":5,"hold_strict":2,"hold_sensitivity":0}
            and am=={"candidate_covered":31,"strict":4,"sensitivity":2,"final_positives":6,"hold_strict":2,"hold_sensitivity":0})
    safe=scope_ok and target_ok and metrics_ok and holds_safe and previous_positives_safe
    report={"schema":"kyiv-0825-actual-classifier-repair-proof-v1",
       "coordination_main_read":"1fad23d3b1f169fa7b60f8f343876b0a0ca924ce",
       "project_state_read":True,"changelog_read":True,"diagnosis_predecessor":DIAG,
       "classifier_base_commit":BASE,"original_classifier_blob":OLD_BLOB,
       "repair_branch":"kyiv-0825-evidence-segment-selection-repair-2026-10-09",
       "semantic_repair_commit":REPAIR,"repaired_classifier_blob":NEW_BLOB,
       "changed_functions":["exact_city_classification_evidence"],
       "proof_branch":"kyiv-0825-evidence-segment-selection-repair-proof-2026-10-09",
       "github_actions_run":os.getenv("GITHUB_RUN_ID"),
       "episodes_processed":67,"candidates_processed":105,"candidate_universe_equal":True,
       "changed_selection_candidates":changed_selection,"changed_classifier_candidates":changed_classifier,
       "changed_episodes":changed_episodes,"baseline_metrics":bm,"repaired_metrics":am,
       "target_baseline_selection":oldc[TARGET_C][1]["selected_ordinals"],
       "target_repaired_selection":target.get("selected_ordinals"),
       "target_repaired_temporal_code":target.get("temporal_code"),
       "target_repaired_candidate_outcome":target.get("classifier_outcome"),
       "target_repaired_episode_binding":target.get("classifier_episode_id"),
       "target_repaired_episode_verdict":new[TARGET_E]["final"],
       "previous_positive_controls_preserved":previous_positives_safe,
       "holds_processed":len(holds),"holds_unchanged":holds_safe,
       "new_uncleared_hold_promotions":0 if holds_safe else None,
       "repaired_fingerprint_A":a["fingerprint"],"repaired_fingerprint_B":b["fingerprint"],
       "deterministic_equality":True,
       "regression_411":"411 REGRESSION NOT EXECUTED — BLIND DETAIL EXPOSURE WOULD BE REQUIRED",
       "frozen_corpus_hashes":EXPECTED_HASHES,"network_evidence_fetches":0,
       "blind_inspected":False,"historical_backfill_started":False,
       "neon_queries":0,"neon_writes":0,"production_mutations":0,
       "verdict":"KYIV EVIDENCE-SEGMENT SELECTION REPAIR = "+("PROVEN" if safe else "FAILED SAFETY GATE"),
       "exactly_one_next_task":("FREEZE THE REPAIRED DEVELOPMENT CLASSIFIER IDENTITY AND RE-DIAGNOSE REMAINING KYIV FAILURES" if safe else "DIAGNOSE ONLY THE OBSERVED SEGMENT-SELECTION REGRESSION")}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(canonical(report))
    print("REPAIR_PROOF_VERDICT="+report["verdict"],flush=True)
    print("REPAIR_PROOF_SHA256="+sha(output.read_bytes()),flush=True)
    require(safe,"REPAIR_FAILED_SAFETY_GATE")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["baseline","repaired","finalize"],required=True)
    p.add_argument("--corpus-dir",type=Path)
    p.add_argument("--prior-replay",type=Path)
    p.add_argument("--baseline",type=Path)
    p.add_argument("--run-a",type=Path)
    p.add_argument("--run-b",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.mode=="finalize":finalize(args.baseline,args.run_a,args.run_b,args.output)
    else:run_one(args.mode,args.corpus_dir,args.prior_replay,args.output)
if __name__=="__main__":main()
