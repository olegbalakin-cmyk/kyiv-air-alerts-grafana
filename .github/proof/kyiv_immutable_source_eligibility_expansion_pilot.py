#!/usr/bin/env python3
"""Only frozen Kyiv development evidence; never publisher/search/Telegram acquisition."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
ORIGINAL = HERE / ".github/proof/kyiv_new_immutable_development_replay.py"
FREEZE_FILE = HERE / "research/kyiv_immutable_development_source_set_freeze_2026-10-09.json"
BASE_COMMIT = "2a7b17c9514a43648e22eb795f0f2f7b65c3980f"
MANIFEST_HASH = "bc77629b7936e02488cd611da1515dc9f9b52db945d5cf334aaa60245ca295ee"
FREEZE_BLOB = "b959a6e0c98c3349a3525ae2f3a7040feef14701"
DIAG_HASH = "c89d7545953015007a96ff7d97b4406a82c86d25570771e5a6bd746a26435b8b"
CORPUS_HASHES = {
    "discovery": "fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
    "native": "bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
    "normalized": "e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d",
}
TARGETS = [
    "01ba82a909e539ff5cc3bd0b", "1216abdb8a6d4cf8febfa361",
    "168254a2ce25aaddeebac2ea", "26c809a6df927f379fa024c2",
    "4ccafc37528fe99ae73fab25", "4d27be817fdcaee69850917b",
    "bce8edfb6de8569f8f0cfb78", "d3111283a5df66d38a665c20",
    "f2225226e10802309d9e1f28", "f72f1143c41c1116e2acf0c4",
    "ff853b73b65d1efa270a3c00",
]
# Relevant candidate IDs reconstructed from the fixed source-dominant
# diagnosis and inspected unchanged source-native article texts. These
# affect ONLY the evaluation matrix; they do NOT alter candidate admission.
# 24_Kanal (nationwide alert), Kyiv24 (failed Oreshnik launch), and
# off-episode additional news items remain admitted by the original logic
# but do not earn relevant-target advancement credit.
RELEVANT = {
    TARGETS[0]: {"89d2be801621f199542aa9b4"},
    TARGETS[1]: {"9c87253c0bf69c8a4596f9e7"},
    TARGETS[2]: {"f80c7cec0bd7582e36458eb1", "ae310a41e509f21268ea3b38"},
    TARGETS[3]: {"dae9002fca7ca15fee315d16", "eb91286f83e581cb3dc83d78"},
    TARGETS[4]: {"e5a0b1e395f1094718c32567"},
    TARGETS[5]: {"7c7580174a07afd0bbc42193"},
    TARGETS[6]: {"264882eab6761411fce4d973", "fafa5f57c528fad3eefa09e8"},
    TARGETS[7]: {"6cbdf4909143c5622c726e0d"},
    TARGETS[8]: {"69eb0b7021613305dd4391d9"},
    TARGETS[9]: {"f54246952785ef1deed0fff2", "a48b96a9d675fa68ff2c1ff3"},
    TARGETS[10]: {"646bd5cdafb9d0797e3868a0"},
}
POSITIVES = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
PREEXISTING_HOLD = "f06c52e0ed82b44792ec2ec7"
CLEARED_HOLD = "e56cdca45ed5b1cd7b0b9746"
CLEARANCE = {
    "candidate_id": "daa340c00d22f5c8fc538510",
    "family": "Suspilne_National",
    "url": "https://suspilne.media/254105-zranku-u-sevcenkivskomu-rajoni-kieva-prolunali-vibuhi-z-dvoh-budinkiv-evakuuut-ludej-klicko/",
    "text_sha256": "fd41c256d699bc6eddb46b6f2a2725f8ecbf93df29265917c7ff27fa6242ea07",
    "classifier_outcome": "approved_strict",
}
BASE_SOURCES = [
    "VA_Kyiv", "KyivCityOfficial", "vitaliy_klitschko", "dsns_kyiv",
    "kpszsu", "suspilnenews", "suspilne_kyiv", "suspilne.media/kyiv",
    "BBC_Ukrainian", "Radio_Svoboda", "Suspilne_National",
    "war.telegraf.com.ua",
]
orig = None

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(o):
    return (json.dumps(o, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode()

def write_json(path, obj):
    Path(path).write_bytes(canonical(obj))

def git(*args):
    return subprocess.check_output(["git", *args], cwd=HERE, text=True).strip()

def verification():
    assert git("rev-parse", BASE_COMMIT) == BASE_COMMIT, "FREEZE_COMMIT_NOT_PRESENT"
    assert git("merge-base", BASE_COMMIT, "HEAD") == BASE_COMMIT, "WRONG_PROOF_BASE"
    assert git("rev-parse", f"HEAD:{FREEZE_FILE.relative_to(HERE)}") == FREEZE_BLOB, "FROZEN_MANIFEST_CHANGED"
    changed = set(git("diff", "--name-only", BASE_COMMIT, "HEAD").splitlines())
    authorized = {
        ".github/proof/kyiv_immutable_source_eligibility_expansion_pilot.py",
        ".github/workflows/kyiv-immutable-source-eligibility-expansion-pilot.yml",
        "research/kyiv_immutable_source_eligibility_expansion_pilot_2026-10-09.json",
    }
    assert changed <= authorized, "UNAUTHORIZED_PROOF_BRANCH_DIFF"
    d = json.loads(FREEZE_FILE.read_text())
    m = d["selected_source_set_manifest"]
    candidates = (
        canonical(m),
        json.dumps(m,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode(),
        (json.dumps(m,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode(),
    )
    assert MANIFEST_HASH in {sha(x) for x in candidates}, "SELECTED_MANIFEST_SHA_MISMATCH"
    assert d["selected_source_set_manifest_sha256"] == MANIFEST_HASH, "MANIFEST_REFERENCE_CHANGED"
    assert m["included_source_families"] == BASE_SOURCES, "SELECTED_SOURCE_FAMILIES_CHANGED"
    assert m["classifier_commit"] == "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453", "CLASSIFIER_COMMIT_CHANGED"
    assert m["classifier_blob_sha"] == "778469b74c2aa807d851cf2c2ee35cf4aa785589", "CLASSIFIER_BLOB_CHANGED"
    assert m["cohort_manifest"]["episodes"] == 67 and m["cohort_manifest"]["known_positives"] == 48 and m["cohort_manifest"]["holds"] == 19, "COHORT_IDENTITY_CHANGED"
    assert m["corpus_hashes_sha256"] == CORPUS_HASHES, "MANIFEST_CORPUS_CHANGED"
    b = m["selected_performance"]
    assert (b["candidate_positive_episodes"],b["strict_positive_episodes"],b["sensitivity_positive_episodes"],
            b["final_positive_episodes"],b["holds_with_candidate"],b["hold_strict"],b["hold_sensitivity"]) == (26,2,1,3,11,2,0), "MANIFEST_BASELINE_METRICS_CHANGED"
    return m

class Offline:
    def __init__(self, corpus, previous):
        global orig
        orig = __import__("importlib.util", fromlist=["x"])
        spec = orig.spec_from_file_location("immutable_runner_unchanged", ORIGINAL)
        mod = orig.module_from_spec(spec); spec.loader.exec_module(mod)
        orig = mod
        for k in ("DATABASE_URL","DIRECT_URL","PGPASSWORD","PGHOST","NEON_DATABASE_URL"):
            assert not os.getenv(k), "DB_CREDENTIAL_PRESENT:"+k
        self.manifest = verification()
        self.discovery = orig.load_verified(corpus / orig.EXPECTED["discovery"])
        self.native = orig.load_verified(corpus / orig.EXPECTED["native"])
        self.normalized = orig.load_verified(corpus / orig.EXPECTED["normalized"])
        assert {k:x["payload_sha256"] for k,x in [
            ("discovery",self.discovery),("native",self.native),
            ("normalized",self.normalized)]} == CORPUS_HASHES, "FROZEN_CORPUS_IDENTITY_MISMATCH"
        self.prior = json.loads(previous.read_text())
        assert self.prior["corpus_hashes"] == CORPUS_HASHES, "PRIOR_REPLAY_CORPUS_MISMATCH"
        assert self.prior["evidence_network_fetches"] == {"publisher":0,"search":0,"telegram":0}, "PRIOR_REPLAY_NETWORK_MISMATCH"
        assert not self.prior["blind_per_episode_data_inspected"], "PRIOR_BLIND_EXPOSURE"
        self.p = orig.load(orig.PILOT, "unchanged_dev_pilot")
        self.cohort = self.discovery["development_episodes"]
        assert len(self.cohort)==67 and len({e["episode_id"] for e in self.cohort})==67, "EPISODE_COUNT_MISMATCH"
        refbase = self.prior["results"]["STAGE2 SINGLE war.telegraf.com.ua"]
        self.truth = {e["episode_id"]:e["truth_label"] for e in refbase["per_episode"]}
        assert sum(v in POSITIVES for v in self.truth.values())==48 and sum(v=="HOLD_CONTROL" for v in self.truth.values())==19, "TRUTH_LABEL_COUNT_MISMATCH"
        assert {e["episode_id"] for e in self.cohort} == set(self.truth), "DEVELOPMENT_EPISODE_IDENTITY_MISMATCH"
        assert all(self.truth[t] in POSITIVES for t in TARGETS), "TARGET_NOT_KNOWN_POSITIVE"
        nmap = {r["requested_native_url"]:r for r in self.native["records"]}
        evidence = {r["requested_native_url"]:r for r in self.normalized["records"]}
        for url, rec in nmap.items():
            if rec.get("native") and rec["native"].get("text"):
                x = evidence.get(url)
                assert x and rec["native"]["text"]==x["exact_normalized_text"] and sha(rec["native"]["text"].encode())==x["normalized_text_sha256"], "NORMALIZED_TEXT_IDENTITY_MISMATCH"
        self.discovered=defaultdict(list)
        byfamily=defaultdict(dict)
        for hit in self.discovery["search_hits"]:
            url=hit.get("native_url")
            if url in nmap and nmap[url].get("native"):
                record=nmap[url]
                self.discovered[hit["episode_id"]].append((hit,record))
                byfamily[record.get("normalized_source_family")][url]=record
        self.passing = [f for f in orig.STAGE2 if orig.quality(list(byfamily[f].values()))[0]=="PASS"]
        assert self.passing == self.prior["stage2_pass_families"], "QUALITY_GATE_CHANGED"
        assert "ye.ua" not in self.passing, "REJECT_FAMILY_ELIGIBLE"
        self.tmp=Path(tempfile.mkdtemp(prefix="kyiv-source-expansion-offline-"))
        self.worktree=None
        self.monitor,self.worktree=self.p.prepare_authoritative_monitor(self.tmp)
        self.all_episodes=self.p.load_full_kyiv_episodes()
        orig.disable_evidence_network()
        self.base = None

    def close(self):
        if self.worktree:
            subprocess.run(["git","worktree","remove","--force",str(self.worktree)],cwd=HERE,capture_output=True)
        shutil.rmtree(self.tmp,ignore_errors=True)

    def replay(self, additions):
        assert set(additions) <= set(self.passing)-{"war.telegraf.com.ua"}, "NEW_SOURCE_FAMILY_FORBIDDEN"
        allowed = {x[0] for x in self.p.SOURCE_ORDER if x[0]!="generic_search"} | set(BASE_SOURCES) | set(additions)
        rows=[]
        for ep in self.cohort:
            found={}
            for hit,rec in self.discovered.get(ep["episode_id"],[]):
                fam=rec["normalized_source_family"]
                if fam not in allowed or orig.admission(self.p,rec["native"],ep)!="PASS":
                    continue
                row,meta=self.p.make_candidate(fam,rec["native"],"frozen_runner_search", {
                    "query_family":hit["query_family"],"result_rank":hit["result_rank"],
                    "wrapper_url":hit["wrapper_url"]})
                found[(fam,row["candidate_id"])]=(row,meta,rec)
            entries=list(found.values())
            final,records,composition,count=self.p.classify_episode(
                self.monitor,self.all_episodes,ep,[(x[0],x[1]) for x in entries])
            candidates=[]
            for row,meta,rec in entries:
                cr=next((x for x in records
                         if x.get("candidate_url")==row["url"] and x.get("source_family")==meta["source_family"]),{})
                candidates.append({
                    "candidate_id":row["candidate_id"],"family":meta["source_family"],
                    "url":row["url"],"text_sha256":rec["extracted_text_sha256"],
                    "classifier_outcome":cr.get("classifier_outcome"),
                    "classifier_episode_id":cr.get("classifier_episode_id"),
                    "reason_codes":cr.get("reason_codes") or [],
                    "temporal_binding":cr.get("temporal_binding") or {},
                    "classifier_error":cr.get("classifier_error")})
            candidates.sort(key=lambda c:(c["family"],c["candidate_id"]))
            rows.append({"episode_id":ep["episode_id"],"truth_label":self.truth[ep["episode_id"]],
                         "candidate_count":len(entries),"candidates":candidates,
                         "final":final,"composition":composition})
        assert len(rows)==67, "REPLAY_EPISODE_COUNT"
        return rows

    def assert_selected(self, fresh):
        original=self.prior["results"]["STAGE2 SINGLE war.telegraf.com.ua"]["per_episode"]
        assert len(fresh)==len(original)==67,"SELECTED_IDENTITY_EPISODES"
        fields=("episode_id","truth_label","candidate_count","final","candidates","composition")
        for now,was in zip(fresh,original):
            for f in fields:
                assert now[f]==was[f],f"SELECTED IMMUTABLE BASELINE IDENTITY MISMATCH:{f}:{now['episode_id']}"

def evidence_clearance(ep, baseline):
    if ep["episode_id"]==PREEXISTING_HOLD and baseline and baseline["final"] in POSITIVES:
        return "PREEXISTING_BASELINE_HOLD"
    if ep["episode_id"]==CLEARED_HOLD:
        cleared=any(all(c.get(k)==v for k,v in CLEARANCE.items()) for c in ep["candidates"])
        # Any added positive candidate or newly created composition would be
        # a different evidence identity and must not borrow the clearance.
        previous_ids={c["candidate_id"] for c in (baseline or {}).get("candidates",[])}
        new_positive=any(c["candidate_id"] not in previous_ids and c["classifier_outcome"] in ("approved_strict","approved_sensitivity") for c in ep["candidates"])
        unchanged_composition=ep.get("composition")== (baseline or {}).get("composition")
        if cleared and not new_positive and unchanged_composition:
            return "EXACT_PRECLEARED_SUSPILNE_IDENTITY"
    return "NEW_UNCLEARED_HOLD_PROMOTION"

def summarize(rows, additions, base=None):
    by={e["episode_id"]:e for e in rows}
    baseline={e["episode_id"]:e for e in base} if base else {}
    positive=[e for e in rows if e["truth_label"] in POSITIVES]
    holds=[e for e in rows if e["truth_label"]=="HOLD_CONTROL"]
    covered=sum(bool(e["candidate_count"]) for e in positive)
    strict=sum(e["final"]=="STRICT_EVENT_POSITIVE" for e in positive)
    sensitivity=sum(e["final"]=="SENSITIVITY_EVENT_POSITIVE" for e in positive)
    holddetail=[]
    for e in holds:
        if e["final"] not in POSITIVES:continue
        clearance=evidence_clearance(e,baseline.get(e["episode_id"]))
        holddetail.append({
            "episode_id":e["episode_id"],"classifier_verdict":e["final"],
            "clearance":clearance,
            "candidates":[{
                "source_family":c["family"],"candidate_id":c["candidate_id"],
                "frozen_url":c["url"],"frozen_text_sha256":c["text_sha256"],
                "classifier_verdict":c["classifier_outcome"],
                "classifier_episode_id":c["classifier_episode_id"]
            } for c in e["candidates"]]})
    unsafe=sorted(x["episode_id"] for x in holddetail if x["clearance"]=="NEW_UNCLEARED_HOLD_PROMOTION")
    recovered_ids=[t for t in TARGETS if not baseline[t]["candidate_count"] and
                    any(c["candidate_id"] in RELEVANT[t] for c in by[t]["candidates"])]
    final_advanced_ids=[t for t in TARGETS if baseline[t]["final"] not in POSITIVES and by[t]["final"] in POSITIVES]
    advanced=set(recovered_ids+final_advanced_ids)
    return {
        "included_source_families":BASE_SOURCES+list(additions),
        "added_families":list(additions), "total_source_family_count":12+len(additions),
        "eligible_known_positives":covered,
        "candidate_covered_known_positives":covered,
        "candidate_recall_pct":round(100*covered/48,3),
        "strict_known_positives":strict,"sensitivity_known_positives":sensitivity,
        "total_final_positives":strict+sensitivity,
        "final_positive_recall_pct":round(100*(strict+sensitivity)/48,3),
        "holds_with_candidate":sum(bool(e["candidate_count"]) for e in holds),
        "hold_strict":sum(e["final"]=="STRICT_EVENT_POSITIVE" for e in holds),
        "hold_sensitivity":sum(e["final"]=="SENSITIVITY_EVENT_POSITIVE" for e in holds),
        "unique_positive_hold_episode_ids":sorted(e["episode_id"] for e in holds if e["final"] in POSITIVES),
        "new_uncleared_hold_promotions":unsafe,
        "hold_safety_accounting":holddetail,
        "target_11_advanced_to_relevant_candidate_ids":recovered_ids,
        "target_11_advanced_to_final_ids":final_advanced_ids,
        "target_11_advanced_unique":sorted(advanced),
        "target_11_with_candidate_total":sum(by[t]["candidate_count"]>0 for t in TARGETS),
        "target_11_with_relevant_added_candidate_total":sum(any(c["candidate_id"] in RELEVANT[t] for c in by[t]["candidates"]) for t in TARGETS),
        "remaining_target_11_unrecovered":sorted(set(TARGETS)-advanced),
        "all_67_episode_verdicts":{e["episode_id"]:e["final"] for e in rows},
    }

def compact(x):
    return {k:v for k,v in x.items() if k!="all_67_episode_verdicts"}

def matrix(prior, pool_passing):
    base={e["episode_id"]:e for e in prior["results"]["STAGE2 SINGLE war.telegraf.com.ua"]["per_episode"]}
    result=[]
    relevant=set()
    rejected=[]
    for t in TARGETS:
        columns=[]
        for fam in pool_passing:
            if fam=="war.telegraf.com.ua":continue
            run=prior["results"].get("STAGE2 SINGLE "+fam)
            if run is None:raise RuntimeError("PREVIOUS_TESTED_FAMILY_RUN_MISSING:"+fam)
            ep=next(e for e in run["per_episode"] if e["episode_id"]==t)
            allcand=[c for c in ep["candidates"] if c["family"]==fam]
            good=[c for c in allcand if c["candidate_id"] in RELEVANT[t]]
            for c in allcand:
                if c not in good:
                    rejected.append({"episode_id":t,"family":fam,"candidate_id":c["candidate_id"],"url":c["url"],"reason":"RAW_CANDIDATE_NOT_DEMONSTRATED_RELEVANT_TO_THIS_TARGET"})
            if good:
                relevant.add(fam)
                columns.append({
                    "source_family":fam,
                    "baseline_candidate_count":base[t]["candidate_count"],
                    "baseline_final_verdict":base[t]["final"],
                    "tested_single_episode_verdict":ep["final"],
                    "frozen_evidence":[{
                        "url":c["url"],"frozen_text_sha256":c["text_sha256"],
                        "candidate_id":c["candidate_id"],"candidate_verdict":c["classifier_outcome"],
                        "classifier_episode_id":c["classifier_episode_id"],
                        "reason_codes":c["reason_codes"],
                        "advancement_in_original_tested_config":(
                            "STRICT" if ep["final"]=="STRICT_EVENT_POSITIVE" else
                            "SENSITIVITY" if ep["final"]=="SENSITIVITY_EVENT_POSITIVE" else
                            "CANDIDATE_ONLY")
                    } for c in good]})
        assert columns, "TARGET_NO_DEMONSTRATED_FAMILY:"+t
        result.append({"episode_id":t,"baseline_candidate_count":base[t]["candidate_count"],
                       "baseline_final_verdict":base[t]["final"],
                       "contributing_pass_families":columns})
    return result,sorted(relevant),rejected

def run_primary(corpus,priorfile):
    o=Offline(corpus,priorfile)
    try:
        base=o.replay(())
        o.assert_selected(base)
        basestat=summarize(base,(),base)
        assert (basestat["candidate_covered_known_positives"],basestat["strict_known_positives"],
                basestat["sensitivity_known_positives"],basestat["total_final_positives"],
                basestat["holds_with_candidate"],basestat["hold_strict"],
                basestat["hold_sensitivity"]) == (26,2,1,3,11,2,0), "SELECTED IMMUTABLE BASELINE IDENTITY MISMATCH"
        matrix_rows,pool,raw_exclusions=matrix(o.prior,o.passing)
        for family in pool:
            assert family in o.passing and family!="ye.ua", "DISALLOWED_FAMILY_IN_POOL"
        singles={}
        for fam in pool:
            singles[fam]=summarize(o.replay((fam,)),(fam,),base)
        # Only SAFE single additions may be used for the cumulative greedy path.
        safe=[f for f in pool if not singles[f]["new_uncleared_hold_promotions"]]
        candidate_results=[("BASELINE",basestat)]
        candidate_results += [("SINGLE "+f,singles[f]) for f in pool]
        cumulative={}
        added=[]
        for k in (1,2,3):
            options=[f for f in safe if f not in added]
            if not options:break
            # Source-eligibility greedy prediction from existing single additions,
            # not a brute-force pair/subset search.
            current=cumulative.get("EXPANSION-"+str(k-1),basestat)
            current_finals=set(current["target_11_advanced_to_final_ids"])
            current_candidates=set(current["target_11_advanced_to_relevant_candidate_ids"])
            current_adv=current_finals|current_candidates
            def rank(f):
                s=singles[f]
                final_inc=len(set(s["target_11_advanced_to_final_ids"])-current_finals)
                cand_inc=len(set(s["target_11_advanced_to_relevant_candidate_ids"])-current_candidates)
                if k==1:
                    final_inc=s["total_final_positives"]-basestat["total_final_positives"]
                    cand_inc=len(s["target_11_advanced_to_relevant_candidate_ids"])
                return (final_inc, cand_inc,
                        -(s["holds_with_candidate"]-basestat["holds_with_candidate"]),
                        -len(f))
            best=max(options,key=lambda f:(rank(f),tuple([-ord(c) for c in f])))
            if k==3 and rank(best)[:2] <= (0,0):break
            added.append(best)
            case=summarize(o.replay(tuple(added)),tuple(added),base)
            cumulative["EXPANSION-"+str(k)]=case
            candidate_results.append(("EXPANSION-"+str(k),case))
            if case["new_uncleared_hold_promotions"]:
                # Unsafe cumulative evidence must not silently become a base
                # for more combinations.
                break
        eligible=[(name,x) for name,x in candidate_results if not x["new_uncleared_hold_promotions"]]
        assert eligible,"NO_SAFE_BASELINE"
        pick=max(eligible,key=lambda e:(
            e[1]["total_final_positives"],e[1]["candidate_covered_known_positives"],
            len(e[1]["target_11_advanced_unique"]),-len(e[1]["added_families"]),
            -sum(len(f) for f in e[1]["added_families"])))
        best_label,beststat=pick
        gain=beststat["total_final_positives"]>3 or (
            beststat["total_final_positives"]==3 and
            beststat["candidate_covered_known_positives"]>26 and
            len(beststat["target_11_advanced_to_relevant_candidate_ids"])>0)
        unsafe_better=any(x["new_uncleared_hold_promotions"] and (
            x["total_final_positives"],x["candidate_covered_known_positives"]) >
            (beststat["total_final_positives"],beststat["candidate_covered_known_positives"])
            for _,x in candidate_results)
        if unsafe_better:
            outcome="HOLD SAFETY REVIEW REQUIRED"
            next_task="FORENSIC REVIEW NEW HOLD PROMOTION"
        elif gain:
            outcome="MATERIAL"
            next_task="FREEZE SAFE SOURCE-ELIGIBILITY EXPANSION"
        else:
            outcome="NO MATERIAL GAIN"
            next_task="MOVE TO NEXT RECOVERABLE NON-SOURCE LEVER"
        return {
            "schema":"kyiv-immutable-source-eligibility-expansion-pilot-v1",
            "base_freeze_commit":BASE_COMMIT,
            "selected_baseline_manifest_sha256":MANIFEST_HASH,
            "classifier_commit":o.manifest["classifier_commit"],
            "classifier_blob":o.manifest["classifier_blob_sha"],
            "immutable_corpus_hashes":CORPUS_HASHES,
            "acquisition_artifact_id":11608819645,"prior_replay_artifact_id":11609004684,
            "diagnosis_provenance":{"artifact_name":"kyiv_immutable_selected_baseline_remaining_failure_diagnosis_2026-10-09.json",
                "sha256":DIAG_HASH,"remaining_known_positive_failures":45,
                "no_candidate_failures":22,"candidate_covered_nonfinal_failures":23,
                "dominant_first_failure":"RELEVANT_FROZEN_RESULT_OUTSIDE_SELECTED_SOURCE_SET",
                "dominant_first_failure_count":12,"unique_source_eligibility_ceiling":11,
                "source_relevant_no_candidate_count":9,
                "candidate_covered_final_positive_recoverable_count":2},
            "target_source_eligibility_episode_ids":TARGETS,
            "family_contribution_matrix":matrix_rows,
            "raw_nonrelevant_candidate_exclusions":raw_exclusions,
            "relevant_expansion_family_pool":pool,
            "relevant_expansion_family_count":len(pool),
            "single_additions_tested":len(singles),
            "single_addition_results":{f:compact(v) for f,v in singles.items()},
            "cumulative_expansions_tested":len(cumulative),
            "cumulative_results":{f:compact(v) for f,v in cumulative.items()},
            "selected_baseline_result":compact(basestat),
            "provisional_best_name":best_label,
            "provisional_best_expansion":compact(beststat),
            "provisional_best_added_families":beststat["added_families"],
            "provisional_best_67_episode_verdicts":beststat["all_67_episode_verdicts"],
            "evidence_network_fetches":{"publisher":0,"google_search":0,"telegram":0,"new_wrapper_resolutions":0,"new_native_acquisitions":0},
            "no_network_enforced":True,
            "blind_per_episode_data_inspected":False,
            "historical_backfill_started":False,
            "independent_validation_readiness":"NOT READY",
            "neon_writes":0,"production_mutations":0,
            "selected_manifest_modified":False,"runtime_code_modified":False,
            "repeated_replay_proof":None,
            "materiality_verdict":outcome,
            "exactly_one_next_recommended_task":next_task,
            "verdict":"KYIV IMMUTABLE SOURCE-ELIGIBILITY EXPANSION PILOT = "+outcome,
        }
    finally:
        o.close()

def fingerprint(rows):
    return {
        "candidate_rows":[{"episode_id":e["episode_id"],
                           "candidate_ids":[c["candidate_id"] for c in e["candidates"]],
                           "candidate_outcomes":[(c["candidate_id"],c["classifier_outcome"],c["classifier_episode_id"]) for c in e["candidates"]],
                           "candidate_count":e["candidate_count"]} for e in rows],
        "episode_verdicts":[(e["episode_id"],e["final"]) for e in rows],
    }

def repeat(corpus,priorfile,selected):
    data=json.loads(selected.read_text())
    o=Offline(corpus,priorfile)
    try:
        rows=o.replay(tuple(data["provisional_best_added_families"]))
        by={r["episode_id"]:r["final"] for r in rows}
        assert by==data["provisional_best_67_episode_verdicts"],"BEST_REPLAY_VERDICT_CHANGED"
        return fingerprint(rows)
    finally:o.close()

def finalize(main,repa,repb):
    data=json.loads(main.read_text())
    a=json.loads(repa.read_text());b=json.loads(repb.read_text())
    assert len(a["candidate_rows"])==len(b["candidate_rows"])==67,"BEST_REPLAY_COUNT_CHANGED"
    assert len(a["episode_verdicts"])==len(b["episode_verdicts"])==67,"BEST_REPLAY_VERDICT_COUNT_CHANGED"
    if a!=b:raise RuntimeError("EXPANSION REPLAY NONDETERMINISTIC")
    data["repeated_replay_proof"]={
        "independent_clean_processes":2,"candidate_ids_equal":True,
        "candidate_counts_equal":True,"candidate_classifier_outcomes_equal":True,
        "episode_verdicts_equal":True,"episode_verdicts_equal_count":67,
        "replay_fingerprint_sha256":sha(canonical(a))}
    data["mutation_confirmation"]={
        "Neon_writes":0,"production_mutations":0,
        "new_publisher_fetches":0,"new_search_fetches":0,
        "new_telegram_fetches":0,"new_wrapper_resolutions":0,
        "new_native_acquisitions":0,"historical_backfill_started":False,
        "old_blind_per_episode_inspected":False,
        "classifier_semantics_changed":False,
        "source_manifest_changed":False,
        "proof_only_branch":True}
    return data

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",required=True,choices=("pilot","repeat","finalize"))
    parser.add_argument("--corpus-dir",type=Path)
    parser.add_argument("--prior-replay",type=Path)
    parser.add_argument("--selected-file",type=Path)
    parser.add_argument("--repeat-a",type=Path)
    parser.add_argument("--repeat-b",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.mode=="pilot":
        data=run_primary(args.corpus_dir,args.prior_replay)
    elif args.mode=="repeat":
        data=repeat(args.corpus_dir,args.prior_replay,args.selected_file)
    else:
        data=finalize(args.selected_file,args.repeat_a,args.repeat_b)
    write_json(args.output,data)
    print("PILOT_MODE="+args.mode)
    print("PILOT_OUTPUT_SHA256="+sha(args.output.read_bytes()))
    if args.mode=="pilot":
        print("PILOT_SUMMARY="+json.dumps({
            "best":data["provisional_best_name"],
            "pool":data["relevant_expansion_family_pool"],
            "single_additions":data["single_additions_tested"],
            "cumulative":data["cumulative_expansions_tested"],
            "materiality":data["materiality_verdict"]},sort_keys=True))

if __name__=="__main__":
    main()
