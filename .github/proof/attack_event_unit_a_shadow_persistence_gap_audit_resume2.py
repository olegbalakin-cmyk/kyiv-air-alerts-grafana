#!/usr/bin/env python3
"""Resume2 A4 offline proof: adapt pinned historical forensic harness to repaired A3.

No classifier, matching, composition or Neon execution. This wrapper runs a
frozen audit algorithm after exact, reviewed source substitutions; it does not
replay candidate decisions. All substantial data remain on GitHub Actions.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = "0b9d7c57bbd1ace9675890744fcb098776abd0b5"
BRANCH = "attack-event-unit-a-shadow-persistence-gap-audit-resume2-2026-10-09"
OUTPUT = Path("research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2_2026-10-09.json")
OLD_RUNNER_COMMIT = "bc53bb897a285338940714216240fc6e9ca65869"
OLD_RUNNER_PATH = ".github/proof/attack_event_unit_a_shadow_persistence_gap_audit_resume.py"
OLD_RUNNER_BLOB = "2a0df97a1a417580a89892f875ec2267453d44a3"
REPAIR_PATH = "research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
REPAIR_BLOB = "a53f665c4f4da26f0b0699939c3b165f376da047"
REPAIR_SHA = "a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"
ORIGINAL_A3_PATH = "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
ORIGINAL_A3_BLOB = "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640"
ORIGINAL_A3_SHA = "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"
A1_PATH = "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
A1_BLOB = "52e89792352513664428da3a7fcb9b43f79f1ba1"
A1_SHA = "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"
A4A_PATH = "research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json"
A4A_BLOB = "a7e6b992180bfef3dd640fcd9ef8eec8a6436af7"
A4A_SHA = "568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891"
CROSS_PATH = "research/attack_event_unit_a_crossbranch_authority_overlap_audit_2026-10-09.json"
CROSS_BLOB = "4c228f800350ed74363747a9a93bdcae312a5c36"
CROSS_SHA = "3d63f49a118dcac3a2ef75db45e945cbc6f00a041b4f25ff8529c82cd95d9647"
A3_HARNESS_PATH = ".github/proof/attack_event_unit_a_bounded_classification_replay.py"
A3_HARNESS_COMMIT = "1422e8482303ec9262647ca55fef753a9aa2b3ea"
A3_HARNESS_BLOB = "f72f08336f1ebebcc766841f7baf73d196ed092a"
PIN_CLASS_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
PIN_HIST_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
PIN_CLASS_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
PIN_HIST_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
PIN_PROD_PATH = "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py"
PIN_PROD_BLOB = "0118ca9e5f1308173e657257f1b49fe91cc19fe1"
DIST = {"STRICT_EVENT_POSITIVE":9,"SENSITIVITY_EVENT_POSITIVE":1,
        "NEEDS_REVIEW":356,"NO_CONFIRMED_EVENT":1347}

def cmd(*args):
    p=subprocess.run(["git",*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        env=dict(os.environ,GIT_NO_LAZY_FETCH="1",GIT_TERMINAL_PROMPT="0"),check=False)
    if p.returncode:
        raise RuntimeError("PINNED_GIT_OBJECT_UNAVAILABLE "+str(args[:2])+" "+p.stderr.decode()[-200:])
    return p.stdout

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def pinned(commit,path,gitblob,filesha=None):
    actual=cmd("rev-parse",commit+":"+path).decode().strip()
    if actual!=gitblob:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT "+path+" "+actual)
    raw=cmd("show",commit+":"+path)
    if filesha and sha(raw)!=filesha:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT sha "+path)
    return raw

def patch(source,old,new):
    if source.count(old)!=1:
        raise RuntimeError("RESUME2_HARNESS_PATCH_CONTEXT_DRIFT "+repr(old[:90])+
                           " occurrences="+str(source.count(old)))
    return source.replace(old,new,1)

def main():
    if os.environ.get("GITHUB_REF_NAME")!=BRANCH:
        raise RuntimeError("UNIT_A_UNEXPECTED_EXECUTION_BRANCH")
    if cmd("merge-base","HEAD",BASE).decode().strip()!=BASE:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT base ancestry")

    # Immutable preflight: all inputs, plus pinned code authorities. No DB access.
    frozen=[
        ("HEAD",REPAIR_PATH,REPAIR_BLOB,REPAIR_SHA),
        ("HEAD",ORIGINAL_A3_PATH,ORIGINAL_A3_BLOB,ORIGINAL_A3_SHA),
        ("HEAD",A1_PATH,A1_BLOB,A1_SHA),
        ("HEAD",A4A_PATH,A4A_BLOB,A4A_SHA),
        ("HEAD",CROSS_PATH,CROSS_BLOB,CROSS_SHA),
        ("71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",PIN_CLASS_PATH,PIN_CLASS_BLOB,None),
        ("71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",PIN_HIST_PATH,PIN_HIST_BLOB,None),
        ("51adc76b715669e46e8c2c936906022d4d96ed44",PIN_PROD_PATH,PIN_PROD_BLOB,None)]
    for commit,path,blob,filesha in frozen:
        pinned(commit,path,blob,filesha)
    cross=json.loads(pinned("HEAD",CROSS_PATH,CROSS_BLOB,CROSS_SHA))
    if cross.get("A5_CROSSBRANCH_GATE")!="PASS" or (
        cross.get("overlap_totals",{}).get("potential_dual_authority_episodes_unique")!=0
    ):
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT CROSSBRANCH_GATE")

    repaired=json.loads(pinned("HEAD",REPAIR_PATH,REPAIR_BLOB,REPAIR_SHA))
    if repaired.get("distribution")!=DIST or len(repaired.get("episode_results") or [])!=1713:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT REPAIRED_A3_DISTRIBUTION")
    counts=repaired.get("counts") or {}
    expected_counts={
        "unit_a_targets":1713,
        "repaired_membership_occurrences":1559,
        "removed_memberships":182,
        "added_memberships":0,
        "affected_episodes":130,
        "direct_strict":6,
        "composed_strict":3,
        "sensitivity":1,
        "positive_contributor_refs_after":18}
    for key,val in expected_counts.items():
        if counts.get(key)!=val:
            raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT repaired count "+key)

    orig=json.loads(pinned("HEAD",ORIGINAL_A3_PATH,ORIGINAL_A3_BLOB,ORIGINAL_A3_SHA))
    prior={x["alert_episode_uid"]:x for x in orig["episode_results"]}
    episodes=repaired["episode_results"]
    if len(prior)!=1713:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT original episode count")
    total_membership=0
    positive=0
    positive_contributors=0
    for e in episodes:
        uid=e["alert_episode_uid"]
        p=prior.get(uid)
        if p is None:
            raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE unknown UID")
        for f in ("episode_id","city_key","alert_start","alert_end",
                  "candidate_input_refs","candidate_decision_refs","composition_provenance"):
            if e.get(f)!=p.get(f):
                raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE changed "+f)
        indexes=e.get("target_related_candidate_positions")
        drefs=e["candidate_decision_refs"]
        irefs=e["candidate_input_refs"]
        if not isinstance(indexes,list) or any(not isinstance(i,int) or i<0 or i>=len(drefs) for i in indexes):
            raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE positions")
        if ([drefs[i] for i in indexes]!=e["target_related_candidate_decision_refs"]
          or [irefs[i] for i in indexes]!=e["target_related_candidate_input_refs"]):
            raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE relation")
        if Counter(e["target_related_candidate_decision_refs"])-Counter(p["target_related_candidate_decision_refs"]):
            raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE introduced member")
        total_membership+=len(indexes)
        if e["verdict"] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
            positive+=1
            positive_contributors+=len(e.get("final_contributor_refs") or [])
    if total_membership!=1559 or positive!=10 or positive_contributors!=18:
        raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE totals")

    # Decision projection itself is a frozen 12-key lossy selection; independently
    # recover its exact field list using the pinned original A3 harness AST.
    a3code=pinned(A3_HARNESS_COMMIT,A3_HARNESS_PATH,A3_HARNESS_BLOB)
    tree=ast.parse(a3code.decode("utf-8"))
    f=next((x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="decision_projection"),None)
    ret=next((x.value for x in ast.walk(f) if isinstance(x,ast.Return)),None) if f else None
    if not isinstance(ret,ast.Dict) or not all(isinstance(k,ast.Constant) and isinstance(k.value,str) for k in ret.keys):
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT decision_projection AST")
    decision_capture_fields=sorted(k.value for k in ret.keys)
    if len(decision_capture_fields)!=12:
        raise RuntimeError("UNIT_A_A4_FROZEN_INPUT_DRIFT decision capture")

    old=pinned(OLD_RUNNER_COMMIT,OLD_RUNNER_PATH,OLD_RUNNER_BLOB).decode("utf-8")
    old=patch(old,'BASE = "7a076e6e1c9b71c2aab16fef9e2bb40b15e1b64c"',
                  'BASE = "'+BASE+'"')
    old=patch(old,'OUTPUT = Path("research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume_2026-10-09.json")',
                  'OUTPUT = Path("'+str(OUTPUT)+'")')
    old=patch(old,'"branch":"attack-event-unit-a-shadow-persistence-gap-audit-resume-2026-10-09"',
                  '"branch":"'+BRANCH+'"')
    old=patch(old,'"kind":"attack_event_execution_unit_a_shadow_persistence_gap_audit_resume"',
                  '"kind":"attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2"')
    old=patch(old,'\"NO_CONFIRMED_EVENT\":1260, \"NEEDS_REVIEW\":443}',
                  '\"NO_CONFIRMED_EVENT\":1347, \"NEEDS_REVIEW\":356}')
    old=patch(old,'\"matching_executions\":0','\"matching_executions\":0') if False else old

    hook='a3rows,decisions,a1_by_uid=env["verify_a3"](a3,a1episodes)\n'
    replacement=hook+'''    # Repaired A3 is authoritative ONLY for episode aggregation; old A3 remains
    # immutable candidate-decision authority. The verified wrapper already
    # checked exact identity, membership indexes, distribution and counts.
    a3rows=__repaired_episode_results
    out["crossbranch_gate"]="PASS"
    out["repaired_membership_occurrences"]=1559
    out["repaired_a3_authority"]="research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
'''
    old=patch(old,hook,replacement)
    scope={"__name__":"isolated_resume2_legacy_proof","__repaired_episode_results":episodes}
    exec(compile(old,"pinned_a4_resume_with_repaired_membership","exec"),scope)
    outcome=scope["main"]()
    if outcome!=0 or not OUTPUT.is_file():
        raise RuntimeError("UNIT_A_A4_RESUME2_AUDIT_RUNNER_ERROR")

    report=json.loads(OUTPUT.read_text("utf-8"))
    expected_first="UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS"
    if report.get("first_failing_gate")!=expected_first:
        # In particular, no falsely successful claim or unimplemented later phase.
        raise RuntimeError("UNIT_A_A4_RESUME2_UNEXPECTED_GATE "+
                           str(report.get("first_failing_gate"))+
                           " "+str(report.get("smallest_demonstrated_blocker"))[:1800])
    probe=report.get("source_payload_projection_probe") or {}
    if (report.get("a3_target_related_membership_occurrences")!=1559 or
        report.get("production_membership_occurrences")!=1559 or
        probe.get("production_related_source_occurrences")!=1559 or
        report.get("source_membership_mismatches")!={"missing":0,"extra":0,"affected_episodes":0}):
        raise RuntimeError("UNIT_A_A4_REPAIRED_MEMBERSHIP_PARITY_FAILURE")

    missing=sorted(set(report["pinned_mechanics"]["payload_required_decision_fields"])-set(decision_capture_fields))
    if not missing or not set(missing).issubset(set(probe["missing_required_decision_field_counts"])):
        raise RuntimeError("UNIT_A_A4_SOURCE_ROW_LOSSLESSNESS_GATE_UNVERIFIED")
    report.update({
        "A5_PERSISTENCE_DELTA_GATE":"FAIL",
        "persistence_action":"NOT_EXECUTED_AUDIT_ONLY",
        "crossbranch_gate":"PASS",
        "neon_contacted":False,
        "shadow_connection_attempted":False,
        "offline_gate_status":{"input_identity":"PASS","repaired_membership":"PASS",
            "source_payload_representability":"FAIL","complete_projection":"NOT_RUN",
            "projection_determinism":"NOT_RUN","neon_shadow":"NOT_CONTACTED"},
        "frozen_input_identities":[{"commit":c,"path":p,"blob":b,"sha256":s}
                                   for c,p,b,s in frozen],
        "repaired_input_identity":{"artifact":REPAIR_PATH,"sha256":REPAIR_SHA,
            "membership_occurrences":1559,"removed_temporal_only_memberships":182,
            "affected_episodes":130},
        "source_payload_field_recoverability":{
            "pinned_candidate_decision_projection_path":A3_HARNESS_PATH,
            "pinned_candidate_decision_projection_blob":A3_HARNESS_BLOB,
            "captured_candidate_decision_fields":decision_capture_fields,
            "required_production_evidence_fields":report["pinned_mechanics"]["payload_required_decision_fields"],
            "fields_not_frozen_in_A3_decisions":missing,
            "other_frozen_sources_examined":[A1_PATH,ORIGINAL_A3_PATH,REPAIR_PATH,A4A_PATH,
                "89 original historical queue snapshots (from pinned git objects)"],
            "mapping_status":"NO_CERTIFIED_LOSSLESS_DERIVATION",
            "reason":"A1 and historical queues hold source inputs; source identity parity does not prove equivalence of missing outputs of the pinned A3 classifier. Frozen A3 decision_projection discards these fields. Values must not be synthesized, copied from a different run, or reclassified."
        },
        "offline_projection":{
            "targets":1713,"repaired_membership_occurrences":1559,
            "positive_episode_states":10,
            "source_evidence_payload_representable":False,
            "affected_source_occurrences":report.get("affected_source_or_classification_count"),
            "affected_episodes":report.get("affected_episode_count"),
            "projected_classifications":None,"projected_events":None,
            "projected_source_links":None,
            "classification_key_uniqueness":None,"event_key_uniqueness":None,
            "source_link_key_uniqueness":None,
            "run_a_projection_sha256":None,"run_b_projection_sha256":None,
            "projection_semantic_mismatches":None
        },
        "neon_read_only_transaction":{"executed":False,"repeatable_read":False,
            "read_only":False,"verified_shadow_project":None,"verified_shadow_branch":None},
        "A5_frozen_delta_manifest":None,
        "safety":{**report["safety"],
            "matching_executions":0,"a5_executions":0,"unit_b_executions":0,
            "unit_c_executions":0,"production_mutation":"NO"}
    })
    report["phase_reached"]="PHASE_2_SOURCE_EVIDENCE_PAYLOAD_REPRESENTABILITY"
    report["verdict"]="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED"
    report["blocker_category"]="SOURCE_EVIDENCE_PAYLOAD_REPRESENTABILITY"
    OUTPUT.write_bytes((json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print("A4_RESUME2_VERDICT="+report["verdict"])
    print("A5_PERSISTENCE_DELTA_GATE=FAIL")
    print("PHASE_REACHED="+report["phase_reached"])
    print("FIRST_FAILING_GATE="+report["first_failing_gate"])
    print("REPAIRED_MEMBERSHIP="+str(total_membership))
    print("MISSING_REQUIRED_FIELD_COUNTS="+json.dumps(
        probe["missing_required_decision_field_counts"],sort_keys=True))
    print("SOURCE_AFFECTED_OCCURRENCES="+str(report["affected_source_or_classification_count"]))
    print("EPISODES_AFFECTED="+str(report["affected_episode_count"]))
    print("NEON_CONTACTED=NO; SQL_SELECT=0; ATTEMPTED_DB_WRITES=0; A5_EXECUTIONS=0")
    print("AUDIT_ARTIFACT_SHA256="+sha(OUTPUT.read_bytes()))

if __name__=="__main__":
    sys.exit(main())
