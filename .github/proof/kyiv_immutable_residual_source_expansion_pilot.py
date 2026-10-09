#!/usr/bin/env python3
"""Bounded residual eligibility pilot on the frozen 15-family Kyiv immutable corpus.

Offline source evidence only. Reuses unchanged prior admission and pinned classifier.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "research/kyiv_immutable_development_source_set_expanded_freeze_2026-10-09.json"
DIAGNOSIS = ROOT / "research/kyiv_immutable_expanded_baseline_remaining_failure_diagnosis_2026-10-09.json"
PREVIOUS_PILOT = ROOT / "research/kyiv_immutable_source_eligibility_expansion_pilot_2026-10-09.json"
OLD_HELPER = ROOT / ".github/proof/kyiv_immutable_source_eligibility_expansion_pilot.py"
FREEZE_COMMIT = "7fdcc2903205e8fc489b2eff588332a45cfaca09"
DIAG_COMMIT = "cb46d7b8232bc3af75c29f40592b731001aed8ea"
MANIFEST_SHA = "58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e"
DIAGNOSIS_SHA = "d6f39ebf96a61814ce679f49193e53c798ae6750b7fdf9efee0e98febfa48969"
CLASSIFIER_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CORPUS_SHA = {
    "discovery": "fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
    "native": "bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
    "normalized": "e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d",
}
FAMILIES = [
    "VA_Kyiv", "KyivCityOfficial", "vitaliy_klitschko", "dsns_kyiv",
    "kpszsu", "suspilnenews", "suspilne_kyiv", "suspilne.media/kyiv",
    "BBC_Ukrainian", "Radio_Svoboda", "Suspilne_National",
    "war.telegraf.com.ua", "5.ua", "zaxid.net", "kyiv.novyny.live",
]
ELIGIBLE = [
    "24_Kanal", "Fakty_ICTV", "Focus", "Kyiv24", "bigkyiv.com.ua",
    "vikna.tv", "Glavcom", "Novynarnia",
]
TARGETS = [
    "01ba82a909e539ff5cc3bd0b", "4ccafc37528fe99ae73fab25",
    "6e4aada601d4b2bdd4e82796", "bce8edfb6de8569f8f0cfb78",
    "d38211541ab9a1cb801d172e", "f2225226e10802309d9e1f28",
    "ff853b73b65d1efa270a3c00", "ffdd8e7b96244ea6d8eff1ba",
]
OUTSIDE_11 = [
    "01ba82a909e539ff5cc3bd0b", "0e8524c2751c7a424a68005f",
    "1e5a30f90ed7c3d37acfec09", "33b1cae83785426737f84083",
    "4ccafc37528fe99ae73fab25", "6e4aada601d4b2bdd4e82796",
    "bce8edfb6de8569f8f0cfb78", "d38211541ab9a1cb801d172e",
    "d3bd74d1f16f20c03bea4c37", "f2225226e10802309d9e1f28",
    "ff853b73b65d1efa270a3c00",
]
POS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
E56 = "e56cdca45ed5b1cd7b0b9746"
F06 = "f06c52e0ed82b44792ec2ec7"
E56_CLEARANCE = {
    "candidate_id": "daa340c00d22f5c8fc538510",
    "family": "Suspilne_National",
    "url": "https://suspilne.media/254105-zranku-u-sevcenkivskomu-rajoni-kieva-prolunali-vibuhi-z-dvoh-budinkiv-evakuuut-ludej-klicko/",
    "text_sha256": "fd41c256d699bc6eddb46b6f2a2725f8ecbf93df29265917c7ff27fa6242ea07",
    "classifier_outcome": "approved_strict",
}
ALLOWED_DIFF = {
    ".github/proof/kyiv_immutable_residual_source_expansion_pilot.py",
    ".github/workflows/kyiv-immutable-residual-source-expansion-pilot.yml",
    "research/kyiv_immutable_residual_source_expansion_pilot_2026-10-09.json",
}
old = None
diagnosis = None

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def assert_static_identity():
    global diagnosis
    # Check frozen Git commits and no unauthorized proof-branch modifications.
    assert git("rev-parse", FREEZE_COMMIT) == FREEZE_COMMIT, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:COMMIT"
    assert git("rev-parse", DIAG_COMMIT) == DIAG_COMMIT, "DIAGNOSIS IDENTITY MISMATCH:COMMIT"
    assert git("merge-base", DIAG_COMMIT, "HEAD") == DIAG_COMMIT, "DIAGNOSIS IDENTITY MISMATCH:BASE"
    assert git("diff", "--name-only", FREEZE_COMMIT, DIAG_COMMIT).splitlines() == [
        "research/kyiv_immutable_expanded_baseline_remaining_failure_diagnosis_2026-10-09.json"
    ], "DIAGNOSIS IDENTITY MISMATCH:BASE_DIFF"
    assert set(git("diff", "--name-only", DIAG_COMMIT, "HEAD").splitlines()) <= ALLOWED_DIFF, "UNAUTHORIZED_PROOF_BRANCH_DIFF"
    assert git("rev-parse", CLASSIFIER_COMMIT + ":" + CLASSIFIER_PATH) == CLASSIFIER_BLOB, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:CLASSIFIER_BLOB"
    assert git("rev-parse", "HEAD:" + str(FREEZE.relative_to(ROOT))) == git(
        "rev-parse", FREEZE_COMMIT + ":" + str(FREEZE.relative_to(ROOT))
    ), "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:FREEZE_CHANGED"
    assert git("rev-parse", "HEAD:" + str(DIAGNOSIS.relative_to(ROOT))) == git(
        "rev-parse", DIAG_COMMIT + ":" + str(DIAGNOSIS.relative_to(ROOT))
    ), "DIAGNOSIS IDENTITY MISMATCH:ARTIFACT_CHANGED"

    f = load_json(FREEZE)
    manifest = f["expanded_development_manifest"]
    assert sha(canonical(manifest)) == MANIFEST_SHA, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:MANIFEST_BYTES"
    assert f["expanded_development_manifest_sha256"] == MANIFEST_SHA, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:MANIFEST_REFERENCE"
    assert f["verdict"] == "KYIV IMMUTABLE EXPANDED DEVELOPMENT SOURCE SET = FROZEN"
    assert manifest["included_source_families"] == FAMILIES, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:FAMILIES"
    assert manifest["source_family_count"] == 15, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:FAMILY_COUNT"
    assert manifest["classifier_commit"] == CLASSIFIER_COMMIT and manifest["classifier_blob_sha"] == CLASSIFIER_BLOB, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:CLASSIFIER"
    assert manifest["immutable_corpus"]["payload_hashes_sha256"] == CORPUS_SHA, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:CORPUS"
    assert manifest["cohort_manifest"]["episodes"] == 67 and manifest["cohort_manifest"]["known_positives"] == 48 and manifest["cohort_manifest"]["holds"] == 19, "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:COHORT"
    a = manifest["accepted_performance"]
    assert (
        a["candidate_covered_positives"], a["final_positive_episodes"],
        a["strict_positive_episodes"], a["sensitivity_positive_episodes"],
        a["holds_with_candidate"], a["hold_strict"], a["hold_sensitivity"]
    ) == (31, 5, 3, 2, 13, 2, 0), "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:ACCEPTED_METRICS"
    assert f["acceptance_proof_run_id"] == 37947654494 and f["candidate_set_equality"] == "67/67", "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:ACCEPTANCE_PROVENANCE"
    assert sha(DIAGNOSIS.read_bytes()) == DIAGNOSIS_SHA, "DIAGNOSIS IDENTITY MISMATCH:SHA256"
    d = load_json(DIAGNOSIS)
    fi = d["expanded_freeze_identity"]
    assert fi["base_commit"] == FREEZE_COMMIT and fi["expanded_manifest_sha256"] == MANIFEST_SHA, "DIAGNOSIS IDENTITY MISMATCH:FREEZE_LINK"
    assert fi["classifier_commit"] == CLASSIFIER_COMMIT and fi["classifier_blob"] == CLASSIFIER_BLOB, "DIAGNOSIS IDENTITY MISMATCH:CLASSIFIER"
    assert fi["source_families"] == FAMILIES, "DIAGNOSIS IDENTITY MISMATCH:FAMILIES"
    assert {k:fi[k+"_sha256"] for k in CORPUS_SHA} == CORPUS_SHA, "DIAGNOSIS IDENTITY MISMATCH:CORPUS"
    c = d["cohort"]
    assert (
        c["total"], c["known_positives"], c["historical_holds"],
        c["candidate_covered_positives"], c["final_positives"],
        c["strict_positives"], c["sensitivity_positives"],
        c["holds_with_candidate"], c["hold_strict"], c["hold_sensitivity"],
        c["remaining_failures"], c["no_candidate_failures"],
        c["candidate_covered_nonfinal_failures"]
    ) == (67, 48, 19, 31, 5, 3, 2, 13, 2, 0, 43, 17, 26), "DIAGNOSIS IDENTITY MISMATCH:METRICS"
    assert d["first_failure_counts"]["RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET"] == 11, "DIAGNOSIS IDENTITY MISMATCH:OUTSIDE_COUNT"
    r = d["residual_source_ceiling"]
    assert r["unique_recoverable_from_previously_tested_source_eligibility_alone"] == 8, "DIAGNOSIS IDENTITY MISMATCH:RESIDUAL_CEILING"
    assert r["candidate_gain_episode_ids"] == TARGETS and r["outside_episode_ids"] == OUTSIDE_11, "DIAGNOSIS IDENTITY MISMATCH:TARGET_IDS"
    assert d["parser_representation_ceilings"]["temporal_parser"]["unique_episode_count"] == 5, "DIAGNOSIS IDENTITY MISMATCH:TEMPORAL_PARSER"
    assert d["parser_representation_ceilings"]["temporal_representation"]["unique_episode_count"] == 4, "DIAGNOSIS IDENTITY MISMATCH:TEMPORAL_REPRESENTATION"
    assert d["admission_ceiling"]["publication_window"]["count"] == 1, "DIAGNOSIS IDENTITY MISMATCH:ADMISSION"
    assert d["first_failure_total"] == 43, "DIAGNOSIS IDENTITY MISMATCH:FAILURE_TOTAL"
    diagnosis = d
    return manifest

def load_old():
    global old
    spec = importlib.util.spec_from_file_location("unchanged_previous_eligibility_proof", OLD_HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.verification = assert_static_identity
    mod.BASE_SOURCES = FAMILIES
    mod.TARGETS = TARGETS
    mod.CORPUS_HASHES = CORPUS_SHA
    old = mod
    return mod

def prior_and_matrix(runner):
    """Reconstruct exactly 8 x 8 cells from diagnosis, prior tests and frozen native records."""
    d = diagnosis
    original = runner.prior
    assert set(ELIGIBLE) <= set(runner.passing), "PRIOR_STAGE2_PASS_UNIVERSE_MISMATCH"
    assert "ye.ua" not in runner.passing
    byid = {x["episode_id"]:x for x in d["exact_43_remaining_failures"]}
    byepisode = {x["episode_id"]:x for x in runner.cohort}
    native = {r["requested_native_url"]:r for r in runner.native["records"]}
    cells, relevant = [], {}
    for eid in TARGETS:
        item = byid[eid]
        assert item["candidate_count"] == 0 and item["final_alert_level_verdict"] == "NO_CONFIRMED_EVENT", "RESIDUAL_TARGET_BASELINE_MISMATCH"
        materials = item.get("no_candidate_corpus_audit", {}).get("outside_source_material_evidence", [])
        for family in ELIGIBLE:
            previous = original["results"]["STAGE2 SINGLE "+family]
            previous_episode = next(z for z in previous["per_episode"] if z["episode_id"] == eid)
            evidences = []
            for evidence in materials:
                if evidence["source_family"] != family or evidence.get("current_admission_outcome") != "PASS":
                    continue
                assert evidence["prior_quality_gate"]["verdict"] == "PASS", "NONPASS_FAMILY_INCLUDED"
                rec = native.get(evidence["url"])
                assert rec is not None and rec["normalized_source_family"] == family, "NATIVE_RECORD_NOT_FOUND"
                assert old.orig.admission(runner.p, rec["native"], byepisode[eid]) == "PASS", "ADMISSION_SEMANTICS_MISMATCH"
                assert rec["extracted_text_sha256"] == evidence["frozen_text_sha256"], "FROZEN_NATIVE_TEXT_MISMATCH"
                for prior_test in evidence["prior_test_outcomes"]:
                    if prior_test["configuration"] != "STAGE2 SINGLE "+family:
                        continue
                    assert prior_test["final_verdict"] == previous_episode["final"], "PRIOR_SINGLE_VERDICT_MISMATCH"
                    for trace in prior_test["candidate_traces"]:
                        if trace["family"] != family or trace["url"] != evidence["url"] or trace["text_sha256"] != evidence["frozen_text_sha256"]:
                            continue
                        matched = [v for v in previous_episode["candidates"] if v["family"] == family and v["candidate_id"] == trace["candidate_id"] and v["url"] == trace["url"] and v["text_sha256"] == trace["text_sha256"]]
                        assert len(matched) == 1, "PRIOR_SINGLE_CANDIDATE_NOT_FOUND"
                        candidate = matched[0]
                        assert candidate["classifier_outcome"] == trace["classifier_outcome"] and candidate["classifier_episode_id"] == trace["classifier_episode_id"], "PRIOR_CLASSIFIER_OUTCOME_MISMATCH"
                        key = (family, candidate["candidate_id"], candidate["url"], candidate["text_sha256"])
                        relevant.setdefault(eid, set()).add(key)
                        evidences.append({
                            "source_family": family,
                            "url": candidate["url"],
                            "frozen_text_sha256": candidate["text_sha256"],
                            "admission_outcome": "PASS",
                            "candidate_id": candidate["candidate_id"],
                            "candidate_classifier_outcome": candidate["classifier_outcome"],
                            "classifier_episode_id": candidate["classifier_episode_id"],
                            "historical_single_final_verdict": previous_episode["final"],
                            "historical_material_advancement": "FINAL_POSITIVE" if previous_episode["final"] in POS else "RELEVANT_CANDIDATE",
                        })
            found_ids = {z["candidate_id"] for z in evidences}
            ignored = sorted({z["candidate_id"] for z in previous_episode["candidates"] if z["family"] == family and z["candidate_id"] not in found_ids})
            cells.append({
                "episode_id": eid, "source_family": family,
                "material_target_evidence": sorted(evidences,key=lambda z:(z["candidate_id"],z["url"])),
                "nonmaterial_prior_candidate_ids_excluded": ignored,
                "material_advancement": ("FINAL_POSITIVE" if any(x["historical_material_advancement"] == "FINAL_POSITIVE" for x in evidences)
                    else "RELEVANT_CANDIDATE" if evidences else "NO_MATERIAL_ADVANCEMENT"),
            })
    assert len(cells) == len(TARGETS)*len(ELIGIBLE), "MATRIX_NOT_8x8"
    pool = sorted({x["source_family"] for x in cells if x["material_target_evidence"]})
    assert pool and set(pool) <= set(ELIGIBLE), "RESIDUAL_POOL_INVALID"
    # The eighth episode is a separate publication-window admission failure.
    assert "ffdd8e7b96244ea6d8eff1ba" not in relevant, "NO_ADMISSION_CHANGE_ALLOWABLE"
    return cells, pool, relevant

def fingerprint(rows):
    return {
        "candidate_rows": [{
            "episode_id":e["episode_id"],
            "candidate_ids":[c["candidate_id"] for c in e["candidates"]],
            "candidate_counts":e["candidate_count"],
            "candidate_classifier_outcomes":[
                (c["candidate_id"], c["classifier_outcome"], c["classifier_episode_id"])
                for c in e["candidates"]
            ],
        } for e in rows],
        "episode_verdicts":[(e["episode_id"],e["final"]) for e in rows],
    }

def summary(rows, additions, baseline, relevant):
    base = {r["episode_id"]:r for r in baseline}
    now = {r["episode_id"]:r for r in rows}
    positives = [r for r in rows if r["truth_label"] in POS]
    holds = [r for r in rows if r["truth_label"] == "HOLD_CONTROL"]
    covered = {r["episode_id"] for r in positives if r["candidate_count"]}
    base_covered = {r["episode_id"] for r in baseline if r["truth_label"] in POS and r["candidate_count"]}
    final_ids = {r["episode_id"] for r in positives if r["final"] in POS}
    base_final = {r["episode_id"] for r in baseline if r["truth_label"] in POS and r["final"] in POS}
    target_candidates, target_final = [], []
    for eid in TARGETS:
        current = now[eid]
        oldids = {(c["family"],c["candidate_id"],c["url"],c["text_sha256"]) for c in base[eid]["candidates"]}
        current_ids = {(c["family"],c["candidate_id"],c["url"],c["text_sha256"]) for c in current["candidates"]}
        if (current_ids-oldids) & relevant.get(eid,set()):
            target_candidates.append(eid)
        if base[eid]["final"] not in POS and current["final"] in POS:
            target_final.append(eid)
    hold_details, uncleared = [], []
    for r in holds:
        if r["final"] not in POS:
            continue
        eid = r["episode_id"]
        if eid == F06 and base[eid]["final"] in POS:
            clearance = "PREEXISTING_BASELINE_HOLD"
        elif eid == E56:
            precleared = any(all(c.get(k)==v for k,v in E56_CLEARANCE.items()) for c in r["candidates"])
            prior_ids = {c["candidate_id"] for c in base[eid]["candidates"]}
            extra_positive = any(c["candidate_id"] not in prior_ids and c["classifier_outcome"] in ("approved_strict","approved_sensitivity") for c in r["candidates"])
            unchanged_composition = r["composition"] == base[eid]["composition"]
            clearance = "EXACT_PRECLEARED_SUSPILNE_IDENTITY" if precleared and not extra_positive and unchanged_composition else "NEW_UNCLEARED_HOLD_PROMOTION"
        else:
            clearance = "NEW_UNCLEARED_HOLD_PROMOTION"
        if clearance == "NEW_UNCLEARED_HOLD_PROMOTION":
            uncleared.append(eid)
        hold_details.append({
            "episode_id":eid, "verdict":r["final"], "clearance":clearance,
            "candidates":[{"candidate_id":c["candidate_id"],"family":c["family"],"url":c["url"],
                           "text_sha256":c["text_sha256"],"classifier_outcome":c["classifier_outcome"]}
                          for c in r["candidates"]],
        })
    additions = list(additions)
    result = {
        "added_families": additions, "all_families":FAMILIES+additions,
        "total_source_family_count":len(FAMILIES)+len(additions),
        "candidate_covered_positives":len(covered),
        "candidate_recall_pct":round(100*len(covered)/48,3),
        "incremental_candidate_covered_positive_ids":sorted(covered-base_covered),
        "incremental_candidate_covered_positives":len(covered-base_covered),
        "strict_positives":sum(r["final"] == "STRICT_EVENT_POSITIVE" for r in positives),
        "sensitivity_positives":sum(r["final"] == "SENSITIVITY_EVENT_POSITIVE" for r in positives),
        "final_positives":len(final_ids),
        "final_positive_recall_pct":round(100*len(final_ids)/48,3),
        "incremental_final_positive_ids":sorted(final_ids-base_final),
        "incremental_final_positives":len(final_ids-base_final),
        "holds_with_candidate":sum(r["candidate_count"]>0 for r in holds),
        "hold_strict":sum(r["final"] == "STRICT_EVENT_POSITIVE" for r in holds),
        "hold_sensitivity":sum(r["final"] == "SENSITIVITY_EVENT_POSITIVE" for r in holds),
        "positive_hold_episode_ids":sorted(r["episode_id"] for r in holds if r["final"] in POS),
        "new_uncleared_hold_promotions":sorted(uncleared),
        "hold_safety_accounting":hold_details,
        "additional_hold_candidate_count":sum(max(0,r["candidate_count"]-base[r["episode_id"]]["candidate_count"]) for r in holds),
        "residual_target_episodes_gaining_relevant_candidate":sorted(target_candidates),
        "residual_target_episodes_becoming_final_positive":sorted(target_final),
        "residual_target_episodes_unrecovered":sorted(set(TARGETS)-set(target_candidates)-set(target_final)),
        "all_67_episode_verdicts":{r["episode_id"]:r["final"] for r in rows},
    }
    assert len(rows) == 67 and len(positives) == 48 and len(holds) == 19
    return result

def compact(s):
    return {k:v for k,v in s.items() if k!="all_67_episode_verdicts"}

def rank(s):
    # Exact frozen normalized family identity is equally deterministic for all eligible families.
    return (s["incremental_final_positives"],
            len(s["residual_target_episodes_gaining_relevant_candidate"]),
            s["candidate_covered_positives"],
            -len(s["added_families"]),
            -s["additional_hold_candidate_count"])

def primary(corpus, prior_path):
    load_old()
    runner = old.Offline(corpus, prior_path)
    try:
        cells, pool, relevant = prior_and_matrix(runner)
        base_rows = runner.replay(())
        assert all(base_rows[i]["episode_id"] == runner.cohort[i]["episode_id"] for i in range(67)), "BASELINE_EPISODE_ORDER_MISMATCH"
        base = summary(base_rows, (), base_rows, relevant)
        assert (base["candidate_covered_positives"],base["strict_positives"],
                base["sensitivity_positives"],base["final_positives"],
                base["holds_with_candidate"],base["hold_strict"],
                base["hold_sensitivity"],base["new_uncleared_hold_promotions"]) == (
                    31,3,2,5,13,2,0,[]), "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:REPLAY_METRICS"
        old_pilot = load_json(PREVIOUS_PILOT)
        proven = old_pilot["cumulative_results"]["EXPANSION-3"]
        assert (proven["candidate_covered_known_positives"],proven["total_final_positives"],
                proven["hold_strict"],proven["hold_sensitivity"]) == (31,5,2,0), "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:PRIOR_PROOF"
        assert base["all_67_episode_verdicts"] == old_pilot["provisional_best_67_episode_verdicts"], "FROZEN 15-FAMILY BASELINE IDENTITY MISMATCH:67_VERDICTS"
        singles = {fam:summary(runner.replay((fam,)),(fam,),base_rows,relevant) for fam in pool}
        safe_families = [fam for fam in pool if not singles[fam]["new_uncleared_hold_promotions"]]
        cum = {}
        selected_rows = {"BASELINE":base_rows}
        options = [("BASELINE",base)]
        options.extend(("SINGLE "+fam,singles[fam]) for fam in pool)
        if safe_families:
            # R1 highest-ranking safe single source, deterministic alphabetical tie.
            first = max(sorted(safe_families),key=lambda fam:(
                singles[fam]["incremental_final_positives"],
                len(singles[fam]["residual_target_episodes_gaining_relevant_candidate"]),
                -singles[fam]["additional_hold_candidate_count"],-len(fam)))
            rows1 = runner.replay((first,))
            s1 = summary(rows1,(first,),base_rows,relevant)
            cum["EXPANSION-R1"] = s1
            options.append(("EXPANSION-R1",s1))
            selected_rows["EXPANSION-R1"] = rows1
            # Only one more SAFE source and only if a genuinely new target candidate/final
            # is possible from already-proven single-addition evidence.
            target1 = set(s1["residual_target_episodes_gaining_relevant_candidate"])
            final1 = set(s1["residual_target_episodes_becoming_final_positive"])
            second_options = []
            for fam in safe_families:
                if fam == first: continue
                potential_new_candidates = set(singles[fam]["residual_target_episodes_gaining_relevant_candidate"])-target1
                potential_new_finals = set(singles[fam]["residual_target_episodes_becoming_final_positive"])-final1
                if potential_new_candidates or potential_new_finals:
                    second_options.append((fam,len(potential_new_finals),len(potential_new_candidates)))
            if second_options:
                second = max(sorted(second_options),key=lambda x:(x[1],x[2],
                             -singles[x[0]]["additional_hold_candidate_count"],-len(x[0])))[0]
                rows2 = runner.replay((first,second))
                s2 = summary(rows2,(first,second),base_rows,relevant)
                cum["EXPANSION-R2"] = s2
                options.append(("EXPANSION-R2",s2))
                selected_rows["EXPANSION-R2"] = rows2
        good = [(name,s) for name,s in options if not s["new_uncleared_hold_promotions"]]
        assert good, "NO_SAFE_CONFIGURATION"
        # Candidate sources are not documents; article count never participates.
        best_name,best = max(good,key=lambda pair:(rank(pair[1]),pair[0]=="BASELINE",pair[0]))
        # If the best actual improvement is unsafe, require forensic review instead of a freeze.
        unsafe = [(name,s) for name,s in options if s["new_uncleared_hold_promotions"]]
        safety_blocking = any(rank(s)>rank(best) for _,s in unsafe)
        if safety_blocking:
            verdict = "HOLD SAFETY REVIEW REQUIRED"
            next_task = "FORENSIC REVIEW NEW HOLD PROMOTION"
        elif best["incremental_final_positives"]>0 or len(best["residual_target_episodes_gaining_relevant_candidate"])>=5:
            verdict = "MATERIAL"
            next_task = "FREEZE NEXT SAFE SOURCE-ELIGIBILITY EXPANSION"
        elif best["residual_target_episodes_gaining_relevant_candidate"]:
            verdict = "SMALL GAIN"
            next_task = "REPAIR TEMPORAL PARSER ON FROZEN 15-FAMILY BASELINE"
        else:
            verdict = "NO MATERIAL GAIN"
            next_task = "REPAIR TEMPORAL PARSER ON FROZEN 15-FAMILY BASELINE"
        if best_name.startswith("SINGLE "):
            chosen_rows = runner.replay(tuple(best["added_families"]))
        else:
            chosen_rows = selected_rows[best_name]
        primary_fp = fingerprint(chosen_rows)
        return {
            "schema":"kyiv-immutable-residual-source-eligibility-pilot-v1",
            "frozen_baseline_identity":{
                "freeze_commit":FREEZE_COMMIT,"expanded_manifest_sha256":MANIFEST_SHA,
                "source_families":FAMILIES,"classifier_commit":CLASSIFIER_COMMIT,
                "classifier_blob":CLASSIFIER_BLOB,"corpus_payload_sha256":CORPUS_SHA,
                "development_cohort":{"episodes":67,"positives":48,"holds":19},
                "acceptance_run_id":37947654494,
                "candidate_covered_positives":31,"final_positives":5,
                "hold_strict":2,"hold_sensitivity":0,
            },
            "diagnosis_identity":{"commit":DIAG_COMMIT,"artifact_sha256":DIAGNOSIS_SHA,
                "remaining_failures":43,"outside_source_count":11,"residual_candidate_ceiling":8,
                "temporal_parser_ceiling":5,"temporal_representation_ceiling":4,
                "admission_ceiling":1,"proof_run_id":37951437545},
            "exact_residual_target_8":TARGETS,"full_outside_source_11":OUTSIDE_11,
            "eligible_residual_families":ELIGIBLE,"relevant_residual_family_pool":pool,
            "relevant_residual_family_pool_count":len(pool),
            "episode_family_contribution_matrix":cells,
            "single_additions_tested":len(singles),
            "single_addition_results":{k:compact(v) for k,v in singles.items()},
            "cumulative_additions_tested":len(cum),
            "cumulative_results":{k:compact(v) for k,v in cum.items()},
            "baseline_result":compact(base),
            "selected_best_configuration":best_name,
            "selected_best_safe_configuration":compact(best),
            "selected_best_added_families":best["added_families"],
            "selected_67_episode_verdicts":best["all_67_episode_verdicts"],
            "primary_fingerprint":primary_fp,
            "source_vs_competing_levers":{
                "source_actual_relevant_target_candidate_gain":len(best["residual_target_episodes_gaining_relevant_candidate"]),
                "source_actual_final_positive_gain":best["incremental_final_positives"],
                "previous_source_candidate_entry_ceiling_not_final_positive_proof":8,
                "temporal_parser_potential_repair_ceiling_not_actual_gain":5,
                "temporal_representation_potential_repair_ceiling_not_actual_gain":4,
                "admission_potential_repair_ceiling_not_actual_gain":1,
            },
            "unsafe_tested_configurations":[{"name":n,"uncleared_holds":s["new_uncleared_hold_promotions"]} for n,s in unsafe],
            "no_network_enforced":True,
            "evidence_network_fetches":{"publisher":0,"search":0,"telegram":0,"wrappers":0,"native":0},
            "blind_per_episode_inspected":False,"historical_backfill_started":False,
            "independent_validation_readiness":"NOT READY","neon_writes":0,
            "production_mutations":0,"source_manifest_modified":False,
            "runtime_code_modified":False,"materiality_verdict":verdict,
            "exactly_one_next_recommendation":next_task,
            "verdict":"KYIV IMMUTABLE RESIDUAL SOURCE-ELIGIBILITY PILOT = "+verdict,
        }
    finally:
        runner.close()

def repeat(corpus, prior_path, primary_doc):
    load_old()
    runner = old.Offline(corpus, prior_path)
    try:
        additions = primary_doc["selected_best_added_families"]
        assert len(additions)<=2 and set(additions)<=set(ELIGIBLE), "REPEAT_UNAUTHORIZED_ADDITION"
        rows = runner.replay(tuple(additions))
        assert {r["episode_id"]:r["final"] for r in rows} == primary_doc["selected_67_episode_verdicts"], "RESIDUAL SOURCE EXPANSION NONDETERMINISTIC:VERDICTS"
        return fingerprint(rows)
    finally:
        runner.close()

def finalize(doc, one, two):
    expected = doc.pop("primary_fingerprint")
    assert one == two == expected, "RESIDUAL SOURCE EXPANSION NONDETERMINISTIC"
    assert len(one["candidate_rows"]) == len(one["episode_verdicts"]) == 67, "RESIDUAL SOURCE EXPANSION NONDETERMINISTIC:EPISODE_COUNT"
    doc["deterministic_replay_proof"] = {
        "independent_clean_processes":2,
        "candidate_ids_equal":True,"candidate_counts_equal":True,
        "candidate_classifier_outcomes_equal":True,"classifier_episode_bindings_equal":True,
        "episode_verdicts_equal":67,
        "fingerprint_sha256":sha(canonical(one)),
    }
    doc["mutation_confirmation"] = {
        "proof_only_branch":True,"frozen_source_manifest_changed":False,
        "classifier_semantics_changed":False,
        "evidence_network_fetches":0,
        "blind_per_episode_inspected":False,"historical_backfill_started":False,
        "neon_writes":0,"production_mutations":0,
    }
    return doc

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",required=True,choices=("primary","repeat","finalize"))
    parser.add_argument("--corpus-dir",type=Path)
    parser.add_argument("--prior-replay",type=Path)
    parser.add_argument("--primary",type=Path)
    parser.add_argument("--repeat-a",type=Path)
    parser.add_argument("--repeat-b",type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    if args.mode=="primary":
        doc=primary(args.corpus_dir,args.prior_replay)
    elif args.mode=="repeat":
        doc=repeat(args.corpus_dir,args.prior_replay,load_json(args.primary))
    else:
        doc=finalize(load_json(args.primary),load_json(args.repeat_a),load_json(args.repeat_b))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(canonical(doc))
    print("RESIDUAL_PILOT_MODE="+args.mode,flush=True)
    print("RESIDUAL_PILOT_OUTPUT_SHA256="+sha(args.output.read_bytes()),flush=True)
    if args.mode in ("primary","finalize"):
        print("RESIDUAL_PILOT_RESULT="+json.dumps({
            "best":doc["selected_best_configuration"],
            "families":doc["selected_best_added_families"],
            "pool":doc["relevant_residual_family_pool"],
            "singles":doc["single_additions_tested"],
            "cumulative":doc["cumulative_additions_tested"],
            "materiality":doc["materiality_verdict"],
        },sort_keys=True),flush=True)

if __name__ == "__main__":
    main()
