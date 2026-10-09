#!/usr/bin/env python3
"""Unit A A4 resumed audit. Frozen objects only until every offline gate passes.
No classifier import, classifier invocation, evidence fetch, or database connection.
"""
from __future__ import annotations
import ast
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

BASE = "7a076e6e1c9b71c2aab16fef9e2bb40b15e1b64c"
OUTPUT = Path("research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume_2026-10-09.json")
HELPER_COMMIT = "a0eb594dd4240d1d923ca5262725fc42f4807338"
HELPER_PATH = ".github/proof/attack_event_unit_a_source_identity_adapter_proof.py"
HELPER_BLOB = "83dd5279f4aeb17c8e06fe5bfaf143c07059efc2"
CLASSIFIER_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
A4A_PATH = "research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json"
A4A_BLOB = "a7e6b992180bfef3dd640fcd9ef8eec8a6436af7"
A4A_SHA = "568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891"
EXPECTED_DISTRIBUTION = {"STRICT_EVENT_POSITIVE":9, "SENSITIVITY_EVENT_POSITIVE":1,
                         "NO_CONFIRMED_EVENT":1260, "NEEDS_REVIEW":443}

class AuditStop(Exception):
    def __init__(self, code, example=None, category="OFFLINE_REPRESENTABILITY"):
        super().__init__(code)
        self.code, self.example, self.category = code, example, category

def demand(ok, code, example=None, category="OFFLINE_REPRESENTABILITY"):
    if not ok:
        raise AuditStop(code, example, category)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(*args):
    run = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"))
    demand(run.returncode == 0, "UNIT_A_LOCAL_FROZEN_OBJECT_UNAVAILABLE",
           {"command":list(args)[:3], "stderr":run.stderr.decode("utf-8","replace")[-220:]})
    return run.stdout

def blob(commit, path):
    return git("rev-parse", "%s:%s" % (commit,path)).decode().strip()

def read_pinned(commit,path,expected_blob):
    demand(blob(commit,path)==expected_blob, "UNIT_A_PINNED_INPUT_BLOB_MISMATCH",
           {"path":path, "ref":commit})
    return git("show","%s:%s" % (commit,path))

def import_pure(source, names, label):
    tree=ast.parse(source.decode("utf-8"))
    funcs={node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    demand(all(n in funcs for n in names),"UNIT_A_PINNED_MECHANICS_NOT_FOUND",
           {"label":label, "missing":[n for n in names if n not in funcs]})
    isolated=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(funcs[n]) for n in names],type_ignores=[]))
    env={"__builtins__":__builtins__,"__name__":"pinned_pure_mechanics"}
    exec(compile(isolated,label,"exec"),env)
    return env,funcs

def required_payload_decision_fields(monitor_code):
    tree=ast.parse(monitor_code.decode("utf-8"))
    methods={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    demand("classification_evidence_payload" in methods,
           "UNIT_A_PINNED_PAYLOAD_CONTRACT_NOT_FOUND")
    fn=methods["classification_evidence_payload"]
    keys=set()
    for n in ast.walk(fn):
        if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=="decision":
            if isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str):
                keys.add(n.slice.value)
        if (isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
            and n.func.attr=="get" and isinstance(n.func.value,ast.Name)
            and n.func.value.id=="decision" and n.args and isinstance(n.args[0],ast.Constant)
            and isinstance(n.args[0].value,str)):
            keys.add(n.args[0].value)
    demand(bool(keys),"UNIT_A_PINNED_PAYLOAD_CONTRACT_NOT_FOUND")
    return sorted(keys)

def basic_artifact():
    return {
      "schema_version":1,
      "kind":"attack_event_execution_unit_a_shadow_persistence_gap_audit_resume",
      "base_commit":BASE,
      "branch":"attack-event-unit-a-shadow-persistence-gap-audit-resume-2026-10-09",
      "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
      "verdict":"ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED",
      "persistence_action":"NOT_AUTHORIZED_PROJECTION_BLOCKED",
      "first_failing_gate":None, "smallest_demonstrated_blocker":None,
      "blocker_category":None, "affected_episode_count":None,
      "affected_source_or_classification_count":None,
      "a3_targets":1713, "frozen_verdict_distribution":EXPECTED_DISTRIBUTION,
      "source_identity_proof_accepted":False,
      "reconstructed_persistence_candidate_occurrences":None,
      "a3_target_related_membership_occurrences":None,
      "production_membership_occurrences":None,
      "source_membership_mismatches":None,
      "source_evidence_payload_representable":None,
      "expected_classifications":1713, "classification_key_uniqueness":None,
      "expected_positive_events":10, "event_key_uniqueness":None,
      "expected_source_links":None, "source_link_key_uniqueness":None,
      "run_a_projection_sha256":None, "run_b_projection_sha256":None,
      "projection_semantic_mismatches":None,
      "neon_project":"green-cake-44216048", "neon_branch":"br-bold-mode-b5rub8pq",
      "neon_branch_verified":False,"repeatable_read_read_only_transaction":False,
      "schema_compatible":None,
      "bound":None,"unbound":None,"ambiguous":None,"parent_drift":None,
      "classifications_exact_present":None,
      "classifications_missing_no_prior_revision":None,
      "classifications_missing_with_prior_revision":None,
      "classification_semantic_conflicts":None,
      "events_exact_present":None,"events_missing":None,
      "event_pointer_updates_required":None,"event_withdrawals_required":None,
      "event_semantic_conflicts":None,
      "source_links_exact_present":None,"source_links_missing":None,
      "source_link_semantic_conflicts":None,
      "phase_reached":"START",
      "safety":{
        "sql_select_count":0,"classifier_executions":0,"composition_executions":0,
        "discovery_executions":0,"external_evidence_requests":0,
        "attempted_db_writes":0,"actual_db_writes":0,
        "ddl_statements":0,"ingestion_runs_mutations":0,
        "public_alert_episodes_mutations":0,"production_mutation":"NO",
        "a5_executed":False,"unit_b_started":False,"unit_c_started":False
      }
    }

def perform(out):
    demand(git("rev-parse","HEAD").decode().strip()!=BASE, "UNIT_A_EXECUTION_BRANCH_NOT_PREPARED")
    demand(git("merge-base", "HEAD", BASE).decode().strip()==BASE, "UNIT_A_BASE_ANCESTRY_DRIFT")
    adapter_raw=read_pinned(HELPER_COMMIT,HELPER_PATH,HELPER_BLOB)
    # Loading the old *pure helper definitions* does NOT rerun its main() proof.
    env={"__name__":"unit_a_offline_helpers"}
    exec(compile(adapter_raw,HELPER_PATH,"exec"),env)
    checked,docs=env["verify_inputs"]()
    corpus, a1episodes, store, refs_total=env["decode_a1"](json.loads(docs["A1"]))
    a3=json.loads(docs["A3"])
    a3rows,decisions,a1_by_uid=env["verify_a3"](a3,a1episodes)
    demand(refs_total==99663,"UNIT_A_FROZEN_INPUT_CARDINALITY_DRIFT")
    expected_q=read_pinned("a0eb594dd4240d1d923ca5262725fc42f4807338",A4A_PATH,A4A_BLOB)
    demand(sha(expected_q)==A4A_SHA, "UNIT_A_SOURCE_IDENTITY_PROOF_DRIFT")
    proof=json.loads(expected_q)
    demand(proof.get("verdict")=="ATTACK-EVENT EXECUTION UNIT A SOURCE IDENTITY ADAPTER = PROVEN"
           and proof.get("run_a_mapping_sha256")==proof.get("run_b_mapping_sha256")
           and proof.get("run_a_run_b_semantic_mismatches")==0,
           "UNIT_A_SOURCE_IDENTITY_ADAPTER_NOT_PROVEN")
    out["source_identity_proof_accepted"]=True
    out["source_identity_mapping_sha256"]=proof["run_a_mapping_sha256"]
    demand(dict(Counter(e["verdict"] for e in a3rows))==EXPECTED_DISTRIBUTION,
           "UNIT_A_A3_VERDICT_DISTRIBUTION_MISMATCH")
    out["phase_reached"]="PHASE_1_FROZEN_A3_ACCEPTED"

    pinned_mon=read_pinned(CLASSIFIER_COMMIT,CLASSIFIER_PATH,CLASSIFIER_BLOB)
    pinned_prod=docs["canonical_persistence"]
    match_env,_=import_pure(pinned_mon,["apply_matching_result"],"pinned_monitor")
    source_env,_=import_pure(pinned_prod,["_episode_refs"],"pinned_production_persistence")
    apply_match=match_env["apply_matching_result"]
    episode_refs=source_env["_episode_refs"]
    payload_required=required_payload_decision_fields(pinned_mon)
    norm=env["production_adapter"](pinned_prod)["_normalized_source_content"]
    canon_sha=env["production_adapter"](pinned_prod)["canonical_sha256"]
    out["pinned_mechanics"]={
        "persistence_blob":"0118ca9e5f1308173e657257f1b49fe91cc19fe1",
        "classifier_blob":CLASSIFIER_BLOB,
        "membership_function":"_episode_refs (AST-extracted)",
        "matching_mutation_function":"apply_matching_result (AST-extracted)",
        "payload_required_decision_fields":payload_required
    }

    snapshot_expect={(q["commit"],q["path"]):q for q in proof["frozen_queue_inputs"]}
    demand(len(snapshot_expect)==89,"UNIT_A_QUEUE_SNAPSHOT_COUNT_DRIFT")
    queue_cache={}
    observed_snapshot=set()
    total=0
    a3_related=0
    production_related=0
    missing=0
    extra=0
    affected=set()
    smallest=None
    composed_count=0
    composed_anchor_count=0
    missing_payload_fields=Counter()
    payload_affected=set()
    payload_source_rows=0
    missing_payload_sample=None
    all_payload_source_rows=0
    source_types=Counter()
    count_pos=0
    source_fields_samples={}

    for episode in a3rows:
        uid=episode["alert_episode_uid"]
        a1ep=a1_by_uid[uid]
        eid=str(episode["episode_id"])
        city=str(episode["city_key"])
        refs=episode["candidate_input_refs"]
        drefs=episode["candidate_decision_refs"]
        assert len(refs)==len(drefs)
        if episode["verdict"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}:
            count_pos+=1
        rows=[]
        if refs:
            qi=(a1ep.get("evidence_provenance") or {}).get("collection_queue_identity") or {}
            pair=(str(qi.get("commit") or ""),str(qi.get("path") or ""))
            expected=snapshot_expect.get(pair)
            demand(bool(expected),"UNIT_A_QUEUE_SNAPSHOT_NOT_PROVEN",{"uid":uid, "queue":pair})
            if pair not in queue_cache:
                queue_bytes=read_pinned(pair[0],pair[1],expected["blob"])
                demand(sha(queue_bytes)==expected["sha256"],"UNIT_A_QUEUE_SNAPSHOT_SHA_DRIFT",
                       {"uid":uid,"commit":pair[0]})
                queued=json.loads(queue_bytes)
                demand(isinstance(queued,list) and len(queued)==expected["rows"],
                       "UNIT_A_QUEUE_SNAPSHOT_ROW_COUNT_DRIFT",{"uid":uid})
                queue_cache[pair]=queued
            observed_snapshot.add(pair)
            chosen=env["selected_queue_rows"](
                queue_cache[pair],eid,
                (a1ep.get("evidence_provenance") or {}).get("followup_72h_checked_at"))
            provenance=(a1ep.get("evidence_provenance") or {}).get("candidate_selection_provenance") or []
            demand(len(chosen)==len(refs)==len(provenance),
                   "UNIT_A_FROZEN_QUEUE_ALIGNMENT_MISMATCH",
                   {"uid":uid,"selected":len(chosen),"refs":len(refs),"provenance":len(provenance)})
            for i,(ref,dref,original,provenance_row) in enumerate(zip(refs,drefs,chosen,provenance)):
                candidate=store[ref]
                decision=decisions[dref]
                demand(original.get("candidate_id")==candidate.get("candidate_id")==provenance_row.get("candidate_id")
                       and provenance_row.get("candidate_input_sha256")==ref
                       and norm(original)==norm(candidate),
                       "UNIT_A_FROZEN_CANDIDATE_SOURCE_PARITY_DRIFT",
                       {"uid":uid,"candidate_ref":ref,"position":i})
                row=copy.deepcopy(original)
                apply_match(row,decision.get("matching") or {})
                status=decision.get("proposed_outcome")
                demand(status in {"approved_strict","approved_sensitivity","needs_review","rejected"},
                       "UNIT_A_FROZEN_DECISION_STATUS_INVALID",{"uid":uid,"decision_ref":dref})
                row["status"]=status
                row["classification_reason_codes"]=list(decision.get("reason_codes") or [])
                row["event_types"]=list(decision.get("event_types") or [])
                # This is explicitly ONLY the minimal _episode_refs membership field;
                # it must not be confused with persisted classification_evidence_payload.
                row["classification_evidence"]={
                    "classification_episode_id":decision.get("proposed_matched_episode_id")
                }
                if status in {"approved_strict","approved_sensitivity"}:
                    row["matched_episode_id"]=decision.get("proposed_matched_episode_id")
                rows.append((row,dref,ref,decision))
                total+=1

        comp=episode.get("composition_provenance")
        if comp is not None:
            composed_count+=1
            demand(episode["verdict"]=="STRICT_EVENT_POSITIVE"
                   and comp.get("final_composed_verdict")=="approved_strict"
                   and str(comp.get("target_episode_id") or "")==eid
                   and not episode.get("direct_strict_contributor_refs"),
                   "UNIT_A_COMPOSED_PERSISTENCE_STATE_NOT_REPRESENTABLE",
                   {"uid":uid,"composition_fields":sorted(comp)})
            anchor_id=str(comp.get("anchor_candidate_id") or "")
            anchors=[v for v in rows if str(v[0].get("candidate_id") or "")==anchor_id]
            demand(len(anchors)==1 and anchor_id,
                   "UNIT_A_COMPOSED_PERSISTENCE_STATE_NOT_REPRESENTABLE",
                   {"uid":uid,"anchor_candidate_id":anchor_id,
                    "matching_anchor_rows":len(anchors)})
            anchor=anchors[0][0]
            demand(not any(x[0].get("status")=="approved_strict"
                          and str(x[0].get("matched_episode_id") or "")==eid for x in rows),
                   "UNIT_A_COMPOSED_PERSISTENCE_STATE_NOT_REPRESENTABLE",
                   {"uid":uid,"reason":"prior strict candidate"})
            anchor["status"]="approved_strict"
            anchor["matched_episode_id"]=eid
            anchor["composition_provenance"]=copy.deepcopy(comp)
            anchor["classification_evidence"]["episode_level_composition"]=copy.deepcopy(comp)
            codes=list(anchor.get("classification_reason_codes") or [])
            for code in comp.get("reason_codes") or []:
                if code not in codes: codes.append(code)
            anchor["classification_reason_codes"]=codes
            anchor["review_note"]="episode-level composed strict classification"
            composed_anchor_count+=1

        a3_refs=list(episode.get("target_related_candidate_decision_refs") or [])
        production_refs=[dref for row,dref,ref,decision in rows
                         if str(row.get("city_key") or "")==city and eid in episode_refs(row)]
        a3_related+=len(a3_refs)
        production_related+=len(production_refs)
        left=Counter(a3_refs)
        right=Counter(production_refs)
        missing_here=sum((left-right).values())
        extra_here=sum((right-left).values())
        missing+=missing_here
        extra+=extra_here
        if missing_here or extra_here:
            affected.add(uid)
            different_ref=next(iter((left-right) or (right-left)))
            example=next(((row,dec,rf) for row,dr,rf,dec in rows if dr==different_ref),None)
            sample={
                "alert_episode_uid":uid,"episode_id":eid,"city_key":city,
                "decision_ref":different_ref,
                "a3_related":left[different_ref],
                "production_related":right[different_ref],
                "production_episode_refs":sorted(episode_refs(example[0])) if example else [],
                "matching":example[1].get("matching") if example else None,
                "proposed_matched_episode_id":example[1].get("proposed_matched_episode_id") if example else None,
                "temporal_binding":example[1].get("temporal_binding") if example else None,
                "review_target_episode_id":(example[1].get("review_provenance_adapter") or {}).get("target_episode_id") if example else None
            }
            if smallest is None or (uid,different_ref)<(smallest["alert_episode_uid"],smallest["decision_ref"]):
                smallest=sample

        # Read-only gate-four evidence representability is evaluated only
        # for production-related source rows, not all A1 candidates.
        for row,dref,ref,decision in rows:
            if str(row.get("city_key") or "")!=city or eid not in episode_refs(row):
                continue
            all_payload_source_rows+=1
            gaps=[field for field in payload_required if field not in decision]
            if gaps:
                payload_source_rows+=1
                payload_affected.add(uid)
                missing_payload_fields.update(gaps)
                if missing_payload_sample is None or (uid,dref)<(
                    missing_payload_sample["alert_episode_uid"],
                    missing_payload_sample["decision_ref"]):
                    missing_payload_sample={
                      "alert_episode_uid":uid,"episode_id":eid,
                      "city_key":city,"decision_ref":dref,
                      "candidate_input_ref":ref,
                      "observation_id":row.get("candidate_id"),
                      "missing_decision_fields":gaps,
                      "missing_persisted_evidence_keys":"derived from pinned classification_evidence_payload AST",
                      "frozen_a1_candidate_fields":sorted(store[ref]),
                      "queue_has_preexisting_classification_evidence":isinstance(
                           queue_cache[pair][0].get("classification_evidence"),dict) if refs and queue_cache[pair] else None
                    }

    demand(total==99663,"UNIT_A_FROZEN_QUEUE_CANDIDATE_OCCURRENCES_DRIFT",{"total":total})
    demand(count_pos==10,"UNIT_A_POSITIVE_TARGET_COUNT_DRIFT",{"count":count_pos})
    demand(len(observed_snapshot)==89,"UNIT_A_QUEUE_SNAPSHOT_COVERAGE_DRIFT",
           {"used":len(observed_snapshot)})
    out["reconstructed_persistence_candidate_occurrences"]=total
    out["a3_target_related_membership_occurrences"]=a3_related
    out["production_membership_occurrences"]=production_related
    out["source_membership_mismatches"]={"missing":missing,"extra":extra,
                                        "affected_episodes":len(affected)}
    out["composed_strict_episodes_reconstructed"]=composed_count
    out["composed_strict_anchors_resolved"]=composed_anchor_count
    out["frozen_queue_snapshots_consumed"]=len(observed_snapshot)
    out["phase_reached"]="PHASE_3_MEMBERSHIP_AUDIT"
    demand(composed_count==3 and composed_anchor_count==3,
           "UNIT_A_COMPOSED_PERSISTENCE_STATE_NOT_REPRESENTABLE",
           {"composed_count":composed_count,"anchors":composed_anchor_count})
    if missing or extra:
        out["affected_episode_count"]=len(affected)
        out["affected_source_or_classification_count"]=missing+extra
        raise AuditStop("UNIT_A_SOURCE_MEMBERSHIP_SEMANTICS_DIVERGENCE",
                        {"a3_target_related_occurrences":a3_related,
                         "production_related_occurrences":production_related,
                         "missing":missing,"extra":extra,"smallest_example":smallest},
                        "PERSISTENCE_MEMBERSHIP_SEMANTICS")
    out["source_membership_exact_parity"]=True
    out["phase_reached"]="PHASE_4_SOURCE_EVIDENCE_REPRESENTABILITY"
    out["source_payload_projection_probe"]={
        "production_related_source_occurrences":all_payload_source_rows,
        "source_rows_missing_required_decision_fields":payload_source_rows,
        "affected_episodes":len(payload_affected),
        "missing_required_decision_field_counts":dict(sorted(missing_payload_fields.items()))
    }
    if payload_source_rows:
        out["source_evidence_payload_representable"]=False
        out["affected_episode_count"]=len(payload_affected)
        out["affected_source_or_classification_count"]=payload_source_rows
        raise AuditStop("UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS",
             {"reason":"Pinned classification_evidence_payload uses classifier decision fields not frozen in A3; A1 contains source inputs, not the A3 classifier output. Reusing old queue evidence or synthesizing defaults is not lossless.",
              "missing_fields":sorted(missing_payload_fields),
              "smallest_example":missing_payload_sample},
             "SOURCE_EVIDENCE_PAYLOAD_REPRESENTABILITY")
    out["source_evidence_payload_representable"]=True
    raise AuditStop("UNIT_A_CLASSIFICATION_PROJECTION_NOT_LOSSLESS",
                    {"reason":"Offline classification/source projection after the evidence-payload gate is not implemented in this bounded harness"},
                    "UNIMPLEMENTED_AUDIT_PHASE")

def main():
    out=basic_artifact()
    try:
        perform(out)
    except AuditStop as error:
        out["first_failing_gate"]=error.code
        out["smallest_demonstrated_blocker"]=error.example
        out["blocker_category"]=error.category
    except Exception as error:
        out["first_failing_gate"]="UNIT_A_A4_RESUME_EXECUTION_ERROR"
        out["smallest_demonstrated_blocker"]={
            "type":type(error).__name__,"message":str(error)[:500],
            "trace_tail":traceback.format_exc().splitlines()[-5:]
        }
        out["blocker_category"]="EXECUTION_ERROR"
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8")+b"\n"
    OUTPUT.write_bytes(payload)
    print("VERDICT="+out["verdict"])
    print("FIRST_FAILING_GATE="+str(out["first_failing_gate"]))
    print("BLOCKER_CATEGORY="+str(out["blocker_category"]))
    print("FIRST_BLOCKER_SAMPLE="+json.dumps(out["smallest_demonstrated_blocker"],
                                                ensure_ascii=False,sort_keys=True)[:3000])
    print("CANDIDATE_OCCURRENCES="+str(out["reconstructed_persistence_candidate_occurrences"]))
    print("A3_MEMBERSHIP_OCCURRENCES="+str(out["a3_target_related_membership_occurrences"]))
    print("PRODUCTION_MEMBERSHIP_OCCURRENCES="+str(out["production_membership_occurrences"]))
    print("MEMBERSHIP_MISMATCHES="+str(out["source_membership_mismatches"]))
    print("SOURCE_EVIDENCE_PAYLOAD_REPRESENTABLE="+str(out["source_evidence_payload_representable"]))
    print("ARTIFACT_SHA256="+sha(payload))
    return 0

if __name__=="__main__":
    sys.exit(main())
