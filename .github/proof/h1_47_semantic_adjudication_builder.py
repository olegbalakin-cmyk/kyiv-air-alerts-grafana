#!/usr/bin/env python3
"""Bounded H1 47-case historical semantic adjudication from immutable Git, not Neon."""
import collections
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CAP_COMMIT = "63e244b7d2cc0c5b302f7814f5a4cc9b82d1052e"
CAP_PATH = "research/neon_h1_47_binding_evidence_capsule_2026-10-12.json"
CAP_BLOB = "7eab80d8f13948ae377e49c3b5173118db6482a0"
CAP_BYTES = 1103142
CAP_SHA = "5f7738ee4d593ea5163ae905500c3052f0ca95aaa6fa8ee700d1eceae618873f"
CAMP = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
REPAIR = "5d18ef85a66384f189ede5ca5654d750f60f088b"
REPAIR_PATH = "research/historical_offline_repair_recovery_scan_2026-10-02.json"
WORKER = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
MONITOR = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
ORIGINAL_PROOF = "cbce9910a1a6b79753c06b0fe2cb2dffd84653dc"
BASE = "cae1f7a9b7c1fdd00fdbbe3d88cf3991985e01cb"

def cmd(*a):
    return subprocess.check_output(a, stderr=subprocess.PIPE)

def raw(commit, path):
    return cmd("git", "show", commit + ":" + path)

def blob(commit, path):
    return cmd("git", "rev-parse", commit + ":" + path).decode().strip()

def sha(value):
    return hashlib.sha256(value).hexdigest()

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def require(x, code):
    if not x:
        raise AssertionError(code)

def refs(o):
    m = o.get("candidate_matching") or {}
    return {str(y) for y in [o.get("classification_episode_id"), m.get("matched_episode_id"), *(m.get("matched_episode_ids") or [])] if y}

def supported_time(binding, target):
    b = binding or {}
    return bool(b.get("present") and b.get("episode_specific") and
                (target == b.get("episode_id") or target in (b.get("supported_episode_ids") or [])))

def time_summary(binding, target, origin):
    b = binding or {}
    ok = supported_time(b, target)
    instant = b.get("event_time") if ok else None
    code = b.get("code")
    if ok and instant:
        kind = "EPISODE_SPECIFIC_EVENT_TIME_UNDER_" + origin
    elif ok:
        kind = "EPISODE_SPECIFIC_TEMPORAL_RELATION_WITHOUT_EXACT_EVENT_CLOCK"
    else:
        kind = "NO_EPISODE_SPECIFIC_EVENT_TIME_SUPPORT"
    return {"inference": kind, "episode_specific": ok, "explicit_event_time": instant,
            "temporal_binding_code": code, "boundary": b.get("near_boundary") if ok else None,
            "publication_time_is_not_event_time": True, "physical_attack_identity": "NOT_OBSERVABLE"}

def decision_for(o, m, parent, batches, repair_art):
    oid, city, target = o["observation_id"], o["city_key"], m["episode_id"]
    parent_original = parent["original_record"]
    p = parent["record_git_identity"]["path"]
    batch = batches[p]
    native = o["original_native_observation_record"]
    nmatch = native.get("candidate_matching") or {}
    src_loc = o["record_git_identity"]
    source_provenance = {"commit": src_loc["commit"], "path": src_loc["path"],
                         "blob": src_loc["git_blob"], "record_sha256": src_loc["record_canonical_sha256"]}
    parent_provenance = {"commit": parent["record_git_identity"]["commit"], "path": p,
                         "blob": parent["record_git_identity"]["git_blob"],
                         "record_sha256": parent["record_git_identity"]["record_canonical_sha256"]}
    target_observations = [r for r in batch.get("observations") or [] if r.get("observation_id") == oid]
    context = None
    witness = None
    if m["accepted_repair_member"]:
        require(not m["original_batch_member"], "REPAIR_NOT_SEPARATE:" + oid)
        require(oid not in parent_original.get("source_observation_ids", []), "REPAIR_ALREADY_ORIGINAL:" + oid)
        exact_target = [r for r in repair_art["targets"]["changed_targets"] if r["city"] == city and r["episode_id"] == target]
        exact_change = [r for r in repair_art["observations"]["changed_observations"] if r["city"] == city and r["observation_id"] == oid]
        require(len(exact_target) == 1 and len(exact_change) == 1, "REPAIR_PROVENANCE_MISSING:" + oid)
        require(exact_target[0] == parent["accepted_repair_target"], "REPAIR_TARGET_DRIFT:" + oid)
        require(exact_change[0] == o["accepted_repair_observation_change"], "REPAIR_CHANGE_DRIFT:" + oid)
        require(oid in exact_target[0]["contributing_observation_ids"], "REPAIR_CONTRIBUTOR_MISSING:" + oid)
        require(supported_time(exact_change[0]["new_temporal_binding"], target), "REPAIR_TEMPORAL_NOT_TARGET:" + oid)
        context = exact_change[0]["new_temporal_binding"]
        mechanism = "ACCEPTED_REPAIR_CONTRIBUTOR"
        a = "VALID_DISTINCT_FIELD_RELATIONSHIP"
        authority = "ACCEPTED_REPAIR_OVERLAY"
        witness = {"repair_commit": REPAIR, "repair_path": REPAIR_PATH,
                   "repair_blob": blob(REPAIR, REPAIR_PATH),
                   "accepted_target_record_sha256": sha(canonical(exact_target[0])),
                   "accepted_observation_change_sha256": sha(canonical(exact_change[0])),
                   "frozen_outcome": exact_target[0]["frozen_outcome"],
                   "repaired_outcome": exact_target[0]["repaired_outcome"]}
        rationale = ("This target is an explicitly accepted repair contributor and was not present in "
                     "the original episode membership. A new accepted episode-specific temporal binding "
                     "supports the repaired target; native publication-window matching is not the repair contract.")
        temporal_origin = "ACCEPTED_REPAIR"
    else:
        require(m["original_batch_member"], "ORIGINAL_NOT_MATERIALIZED:" + oid)
        require(oid in parent_original.get("source_observation_ids", []), "ORIGINAL_MEMBERSHIP_MISSING:" + oid)
        if target_observations:
            require(len(target_observations) == 1, "DUPLICATE_TARGET_OBSERVATION:" + oid)
            target_record = target_observations[0]
            require(target in refs(target_record), "FROZEN_UNION_MISMATCH:" + oid)
            context = target_record.get("temporal_binding")
            if target == target_record.get("classification_episode_id"):
                mechanism = "ORIGINAL_CLASSIFICATION_EPISODE_REF"
                a = "VERIFIER_SEMANTIC_OVERREACH" if m["provisional_discrepancy_flag"] else "VALID_DISTINCT_FIELD_RELATIONSHIP"
                rationale = ("The exact original batch materializes the membership through classification_episode_id. "
                             "Its separately stored candidate matched_episode_id is a publication-time relationship "
                             "and is not required to equal classifier binding.")
                temporal_origin = "ORIGINAL_CLASSIFIER"
            elif target == (target_record.get("candidate_matching") or {}).get("matched_episode_id"):
                mechanism = "ORIGINAL_SINGULAR_CANDIDATE_MATCH_REF"
                a = "VALID_DISTINCT_FIELD_RELATIONSHIP"
                rationale = ("Original materialized membership is admitted through singular candidate matching. "
                             "That publication-time discovery relationship is distinct from the original "
                             "classifier-selected episode and does not prove attack-time attribution.")
                temporal_origin = "ORIGINAL_CLASSIFIER"
            else:
                require(target in ((target_record.get("candidate_matching") or {}).get("matched_episode_ids") or []),
                        "PLURAL_MATCHING_MISSING:" + oid)
                mechanism = "ORIGINAL_PLURAL_CANDIDATE_MATCH_REF"
                a = "VALID_DISTINCT_FIELD_RELATIONSHIP"
                rationale = ("Original batch membership is admitted by plural matched_episode_ids without a singular match. "
                             "Dropping plural discovery links creates a false discrepancy; a publication candidate "
                             "is not itself physical event-time evidence.")
                temporal_origin = "ORIGINAL_CLASSIFIER"
            witness = {"target_batch_native_observation_sha256": sha(canonical(target_record)),
                       "direct_field_union_contains_target": True}
        else:
            duplicate = [z for z in (batch.get("campaign_observation_dedupe") or {}).get("duplicates", []) if z.get("observation_id") == oid]
            require(len(duplicate) == 1, "DEDUP_MISSING:" + oid)
            d = duplicate[0]
            require(d["equivalence"] == "EQUIVALENT_DETERMINISTIC_DUPLICATE", "DEDUP_NOT_EQUIVALENT:" + oid)
            require(target in d.get("episode_reference_ids", []), "DEDUP_EPISODE_REF_MISSING:" + oid)
            regenerated = d["regenerated_context"]
            v = regenerated.get("candidate_matching") or {}
            regenerated_refs = {t for t in [regenerated.get("classification_episode_id"), v.get("matched_episode_id"), *(v.get("matched_episode_ids") or [])] if t}
            require(target in regenerated_refs, "DEDUP_REGENERATED_REF_MISSING:" + oid)
            require(d.get("original_batch_path") == src_loc["path"], "DEDUP_ORIGINAL_PATH_DRIFT:" + oid)
            require(d["original_context"]["classification_episode_id"] == native.get("classification_episode_id"),
                    "DEDUP_ORIGINAL_CONTEXT_DRIFT:" + oid)
            context = regenerated["temporal_binding"]
            mechanism = "ACCEPTED_CROSS_BATCH_DEDUP_REGENERATED_CONTEXT"
            a = "VERIFIER_SEMANTIC_OVERREACH"
            witness = {"dedupe_semantics": batch["campaign_observation_dedupe"]["semantics"],
                       "dedupe_entry_sha256": sha(canonical(d)),
                       "dedupe_equivalence": d["equivalence"],
                       "original_batch_path": d["original_batch_path"],
                       "regenerated_classification_episode_id": regenerated.get("classification_episode_id"),
                       "regenerated_matching_episode_id": v.get("matched_episode_id"),
                       "regenerated_matching_episode_ids": v.get("matched_episode_ids") or [],
                       "original_context_classification_episode_id": d["original_context"].get("classification_episode_id")}
            rationale = ("The target batch explicitly records an equivalent deterministic cross-batch duplicate and "
                         "the target-specific regenerated classification/matching context before canonical observation "
                         "deduplication. The earlier canonical native record belongs to another episode context and "
                         "cannot be used as a global equality constraint.")
            temporal_origin = "ORIGINAL_REGENERATED_CONTEXT"
        authority = "ORIGINAL_ACCEPTED"
    t = time_summary(context, target, temporal_origin)
    if mechanism in ("ORIGINAL_SINGULAR_CANDIDATE_MATCH_REF", "ORIGINAL_PLURAL_CANDIDATE_MATCH_REF"):
        require(not t["episode_specific"], "PUBLICATION_MATCH_MISCLASSIFIED_AS_EVENTTIME:" + oid)
    return {
        "case_id": None,
        "source_observation_id": oid, "city_key": city, "historical_episode_id": target,
        "original_verifier_label": "CONTRADICTION",
        "original_verifier_reason": m["exact_original_proof_member"]["authority_reason"],
        "original_provenance": "ACCEPTED_REPAIR_OVERLAY" if m["accepted_repair_member"] else "ORIGINAL_FROZEN_BATCH",
        "original_discrepancy_mechanism_verdict": a,
        "exact_membership_historical_authority_verdict": authority,
        "attack_evidence_inference_boundary": t, "admission_mechanism": mechanism,
        "native_classification_episode_id": native.get("classification_episode_id"),
        "native_matched_episode_id": nmatch.get("matched_episode_id"),
        "native_matched_episode_ids": nmatch.get("matched_episode_ids") or [],
        "native_matching_outcome": nmatch.get("outcome"),
        "native_temporal_binding_code": (native.get("temporal_binding") or {}).get("code"),
        "source_timestamp_as_recorded": native.get("source_timestamp"),
        "other_effective_memberships_of_same_observation": sorted([x["episode_id"] for x in o["all_frozen_effective_memberships"] if x["episode_id"] != target]),
        "recorded_source_content_hash_not_independent_publisher_body": native.get("content_hash"),
        "source_git_evidence": source_provenance, "episode_git_evidence": parent_provenance,
        "original_verifier_row_sha256": sha(canonical(m["exact_original_proof_member"])),
        "original_batch_or_repair_witness": witness, "rationale": rationale,
        "limitations": ["Materialized source membership is not proof of a distinct physical attack",
                        "No original publisher-article availability or independent physical incident identity is established",
                        "Full deterministic source-link/classification key-input historical authority remains separately partial"],
    }

def run():
    assert blob(CAP_COMMIT, CAP_PATH) == CAP_BLOB
    cap_bytes = raw(CAP_COMMIT, CAP_PATH)
    require(len(cap_bytes) == CAP_BYTES and sha(cap_bytes) == CAP_SHA, "CAPSULE_BYTES_HASH_FAILURE")
    c = json.loads(cap_bytes)
    inputs = c["input_git_objects"]
    for name in ["frozen_original_6863_audit", "historical_repair", "historical_october_4_git_derived_export"]:
        b = inputs[name]
        require(blob(b["commit"], b["path"]) == b["git_blob"], "PREDECESSOR_BLOB_DRIFT:" + name)
    require(inputs["frozen_original_6863_audit"]["commit"] == ORIGINAL_PROOF, "WRONG_ORIGINAL_PROOF")
    require(inputs["original_139_batches_commit"] == CAMP or
            isinstance(inputs["original_139_batches_commit"], dict), "WRONG_ORIGINAL_CAMPAIGN")
    assert blob(CAMP, WORKER) == inputs["original_historical_worker"]["git_blob"]
    assert blob(CAMP, MONITOR) == inputs["original_historical_classifier"]["git_blob"]
    worker = raw(CAMP, WORKER).decode()
    excerpt = c["historical_field_contract_inventory"]["episode_results[].source_observation_ids"]["original_implementation_locations"][0]["exact_excerpt"]
    union_excerpt = next(y["exact_excerpt"] for y in c["historical_field_contract_inventory"]["episode_results[].source_observation_ids"]["original_implementation_locations"] if "def observation_episode_refs" in y["exact_excerpt"])
    require(excerpt in worker and union_excerpt in worker, "HISTORICAL_WORKER_CONTRACT_MISMATCH")
    require("related = [obs for obs in observations if eid in observation_episode_refs(obs)]" in worker, "UNION_NOT_USED")
    monitor = raw(CAMP, MONITOR).decode()
    require("Publication time may identify alert windows" in monitor and
            "but it is not evidence of the event time" in monitor, "PUBLICATION_TIME_GUARD_MISSING")
    repair_info = inputs["historical_repair"]
    require(blob(REPAIR, REPAIR_PATH) == repair_info["git_blob"], "REPAIR_BLOB_DRIFT")
    repair_bytes = raw(REPAIR, REPAIR_PATH)
    require(len(repair_bytes) == repair_info["bytes"] and sha(repair_bytes) == repair_info["sha256"], "REPAIR_BYTES_DRIFT")
    repair_art = json.loads(repair_bytes)

    all_paths = sorted(set(c["selected_historical_batch_paths"]["associated_episode_records"]) |
                       set(c["selected_historical_batch_paths"]["observation_records"]))
    manifests = {p["path"]: p for p in inputs["original_139_batch_manifest"]}
    batches = {}
    for p in all_paths:
        manifest = manifests[p]
        b = raw(CAMP, p)
        require(len(b) == manifest["bytes"] and sha(b) == manifest["sha256"] and
                blob(CAMP, p) == manifest["git_blob"], "RAW_BATCH_IDENTITY_FAIL:" + p)
        batches[p] = json.loads(b)
    require(len(batches) == 23, "WRONG_BATCH_COUNT")
    observations = c["observations_with_all_memberships_and_native_evidence"]
    parents = c["original_episode_records_for_selected_memberships"]
    flags = c["original_47_row_discrepancy_ledger_exact"]
    require(len(observations) == 27 and len(parents) == 51 and len(flags) == 47, "POPULATION_CHANGED")
    seen_o = set()
    observed_members = {}
    raw_record_verified = 0
    for o in observations:
        oid, city = o["observation_id"], o["city_key"]
        require((city, oid) not in seen_o, "DUPLICATE_OBSERVATION")
        seen_o.add((city, oid))
        file = batches[o["record_git_identity"]["path"]]
        obs = [x for x in file.get("observations") or [] if x["observation_id"] == oid]
        require(len(obs) == 1 and obs[0] == o["original_native_observation_record"], "ORIGINAL_OBSERVATION_RECORD_MISMATCH:" + oid)
        require(sha(canonical(obs[0])) == o["record_git_identity"]["record_canonical_sha256"], "NATIVE_RECORD_HASH_MISMATCH")
        raw_record_verified += 1
        require(len(o["all_frozen_effective_memberships"]) == o["member_total"], "MEMBER_TOTAL_DRIFT")
        for m in o["all_frozen_effective_memberships"]:
            key = (city, m["episode_id"], oid)
            require(key not in observed_members, "DUPLICATE_EFFECTIVE_MEMBER")
            require(m["city_key"] == city and m["original_episode_record_key"] == city+":"+m["episode_id"], "MEMBER_PARENT_KEY_DRIFT")
            require(sha(canonical(m["exact_original_proof_member"])) == m["proof_ledger_record_sha256"], "ORIGINAL_VERIFIER_RECORD_HASH_DRIFT")
            observed_members[key] = (o, m)
    require(len(observed_members) == 55, "ALL_55_MEMBERSHIP_COUNT_FAIL")
    episode_ver = 0
    for key, p in parents.items():
        require(key == p["city_key"]+":"+p["episode_id"], "EPISODE_KEY_DRIFT")
        batch = batches[p["record_git_identity"]["path"]]
        ep = [x for x in batch["episode_results"] if x["episode_id"] == p["episode_id"]]
        require(len(ep) == 1 and ep[0] == p["original_record"], "ORIGINAL_EPISODE_RECORD_MISMATCH:" + key)
        require(sha(canonical(ep[0])) == p["record_git_identity"]["record_canonical_sha256"], "EPISODE_RECORD_SHA_DRIFT")
        episode_ver += 1
    require(episode_ver == 51, "51_ASSOCIATED_EPISODES_FAIL")
    flag_keys = {(x["city_key"], x["historical_episode_id"], x["observation_id"]) for x in flags}
    require(len(flag_keys) == 47, "FLAG_NOT_UNIQUE")
    require(flag_keys == {key for key, (_, m) in observed_members.items() if m["provisional_discrepancy_flag"]}, "EXACT_47_FLAG_SET_DRIFT")
    ledger, controls = [], []
    for idx, orig in enumerate(flags, start=1):
        key = (orig["city_key"], orig["historical_episode_id"], orig["observation_id"])
        require(key in observed_members, "CASE_NOT_IN_NATIVE_MEMBERSHIPS:" + str(idx))
        o, m = observed_members[key]
        require(orig == m["exact_original_proof_member"], "FLAG_ORIGINAL_PROOF_ROW_DRIFT:" + str(idx))
        record = decision_for(o, m, parents[m["original_episode_record_key"]], batches, repair_art)
        record["case_id"] = "H1-47-%03d" % idx
        ledger.append(record)
    for key in sorted(set(observed_members) - flag_keys):
        o, m = observed_members[key]
        require(m["original_batch_member"] and not m["accepted_repair_member"], "CONTROL_ORIGIN_DRIFT")
        parent = parents[m["original_episode_record_key"]]
        a = decision_for(o, m, parent, batches, repair_art)
        controls.append({"city_key": key[0], "episode_id": key[1], "observation_id": key[2],
                         "classification": a["admission_mechanism"],
                         "historical_authority": a["exact_membership_historical_authority_verdict"],
                         "original_verifier_label": m["exact_original_proof_member"]["authority_category"],
                         "source_git_evidence": a["source_git_evidence"],
                         "episode_git_evidence": a["episode_git_evidence"]})
    require(len(controls) == 8, "EIGHT_CONTROLS_FAIL")
    def counts(key):
        return dict(sorted(collections.Counter(x[key] for x in ledger).items()))
    mechanism_counts = counts("admission_mechanism")
    require(mechanism_counts == {
        "ORIGINAL_CLASSIFICATION_EPISODE_REF":19,
        "ORIGINAL_SINGULAR_CANDIDATE_MATCH_REF":19,
        "ORIGINAL_PLURAL_CANDIDATE_MATCH_REF":2,
        "ACCEPTED_CROSS_BATCH_DEDUP_REGENERATED_CONTEXT":3,
        "ACCEPTED_REPAIR_CONTRIBUTOR":4}, "MECHANISM_POPULATION_UNEXPECTED:" + str(mechanism_counts))
    require(counts("exact_membership_historical_authority_verdict") == {"ORIGINAL_ACCEPTED":43,"ACCEPTED_REPAIR_OVERLAY":4}, "AUTHORITY_POPULATION_UNEXPECTED")
    require(not any(x["original_discrepancy_mechanism_verdict"] in ("MATERIAL_HISTORICAL_CONTRADICTION","UNRESOLVED_FIELD_CONTRACT") for x in ledger), "UNEXPECTED_CONTRADICTION")
    temporal_count = sum(bool(x["attack_evidence_inference_boundary"]["episode_specific"]) for x in ledger)
    require(temporal_count >= 19, "TEMPORAL_SUPPORT_TOO_LOW")
    event_clock_count = sum(bool(x["attack_evidence_inference_boundary"]["explicit_event_time"]) for x in ledger)
    require(event_clock_count <= temporal_count, "EVENT_CLOCK_IMPOSSIBLE")
    agg_city = {k: sum(x["city_key"] == k for x in ledger) for k in ("cherkasy","sumy","zaporizhzhia")}
    require(agg_city == {"cherkasy":4, "sumy":39, "zaporizhzhia":4}, "CITY_COUNTS_WRONG")
    proof = {
        "schema_version":"neon_h1_47_semantic_adjudication_v1",
        "result":"PASS_CASE_BY_CASE_HISTORICAL_SEMANTIC_ADJUDICATION_PENDING_INDEPENDENT_ACCEPTANCE",
        "scope":"Exact 47 H1 provisional membership flags in 2340 source memberships; no classification replay, DB, Neon, source retrieval or production",
        "predecessor_evidence":{
            "capsule_commit":CAP_COMMIT,"capsule_path":CAP_PATH,"capsule_git_blob":CAP_BLOB,
            "capsule_bytes":CAP_BYTES,"capsule_sha256":CAP_SHA,
            "original_h1_field_proof_commit":ORIGINAL_PROOF,
            "original_h1_field_proof_git_blob":inputs["frozen_original_6863_audit"]["git_blob"],
            "original_h1_field_proof_sha256":inputs["frozen_original_6863_audit"]["sha256"],
            "historical_campaign_commit":CAMP, "original_worker_git_blob":inputs["original_historical_worker"]["git_blob"],
            "original_classifier_git_blob":inputs["original_historical_classifier"]["git_blob"],
            "repair_commit":REPAIR,"repair_proof_blob":repair_info["git_blob"],
            "repair_proof_sha256":repair_info["sha256"],
            "base_main_commit_at_preflight":BASE,
            "original_verifier_labels_unmodified":True},
        "governing_contracts":{
            k:{"definition":v["definition_and_computation"],
               "requires_global_cross_field_equality":v.get("cross_field_equality_required_by_cited_contract"),
               "original_implementation_locations":[{"commit":loc["commit"],"path":loc["path"],
                    "blob":loc.get("git_blob"),"excerpt_sha256":loc.get("excerpt_sha256")} for loc in v.get("original_implementation_locations",[])]}
            for k,v in c["historical_field_contract_inventory"].items()},
        "methodology":{
            "historical_union":"classification_episode_id OR candidate_matching.matched_episode_id OR candidate_matching.matched_episode_ids",
            "source_membership_does_not_imply_event_time_support":True,
            "cross_batch_dedup_requires_explicit_regenerated_context":True,
            "repair_contributor_requires_exact_accepted_scan_target_and_observation":True,
            "unflagged_memberships_are_controls_not_new_cases":True,
            "physical_attack_identity_out_of_scope":True},
        "47_case_decision_ledger":ledger,
        "8_unflagged_control_assessments":controls,
        "population_and_integrity":{
            "flagged":len(ledger),"source_observations":len(observations),"all_effective_memberships":len(observed_members),
            "unflagged_controls":len(controls),"associated_episodes":len(parents),
            "original_batch_flagged":43,"accepted_repair_flagged":4,
            "raw_git_batches_independently_checked":len(batches),
            "native_records_byte_semantically_checked":raw_record_verified,
            "episode_records_byte_semantically_checked":episode_ver,
            "all_original_batches_manifest_unmodified":True},
        "aggregate":{
            "flagged_by_city":agg_city,
            "discrepancy_verdicts":counts("original_discrepancy_mechanism_verdict"),
            "historical_membership_authority":counts("exact_membership_historical_authority_verdict"),
            "mechanisms":mechanism_counts,
            "episode_specific_temporal_support_cases":temporal_count,
            "explicit_event_time_cases":event_clock_count,
            "membership_without_episode_specific_temporal_support":47-temporal_count,
            "original_verifier_contradictions_initial":47,
            "confirmed_material_historical_contradictions":0,
            "remaining_field_contract_unresolved_cases":0},
        "revised_full_2340_membership_distribution":{
            "original_predecessor_original_accepted":2283,
            "newly_adjudicated_original_accepted":43,
            "total_original_accepted":2326,
            "original_predecessor_independently_derivable":10,
            "separately_accepted_repair_overlay":4,
            "total":2340,
            "scope":"Historical membership relationships only; original source-link key-input authority remains separate"},
        "proposed_h1_scope_statuses":{
            "H1_SOURCE_MEMBERSHIP_HISTORICAL_AUTHORITY":"PROVEN_FOR_EXACT_FROZEN_2340_MEMBERSHIP_RELATIONSHIPS_WITH_10_INDEPENDENTLY_DERIVABLE",
            "H1_SOURCE_LINK_KEY_INPUT_AUTHORITY":"PARTIAL",
            "H1_CLASSIFICATION_KEY_INPUT_AUTHORITY":"PARTIAL",
            "H1_6863_FIELD_AUTHORITY_AUDIT":"PARTIAL",
            "H1_FULL_SOURCE_EVENT_KEY_FIELD_AUTHORITY":"NOT_PROVEN",
            "C4":"NOT_PROVEN","C5":"NOT_PROVEN","NEON_AUTHORITY_ACTIVE":"NO",
            "PRODUCTION_CUTOVER_EXECUTED":"NO"},
        "remaining_authority_limitations":[
            "Ten predecessor source memberships are independently derivable, not directly original recorded",
            "Historical membership does not independently establish physical attack or exact attack-time for all 2340 memberships",
            "Full source-link key-input field authority remains partial despite computational key equality",
            "Full classification key-input field authority remains partial despite 6863/6863 computational equality",
            "Full modeled-event key-input/provenance and remaining H1 field authority require separately scoped independent acceptance",
            "The 25 historical UNBOUND parent admissions and global frozen-vs-Neon parity are separate unresolved tracks",
            "No original publisher-page retrieval, Neon read-back, current-state query or production change occurred"],
        "independent_verification_results":"TO_BE_POPULATED_BY_SEPARATE_VERIFIER_IN_ACTIONS",
        "safety_counters":{"neon_queries":0,"neon_writes":0,"production_mutations":0,
                           "site_prod_mutations":0,"classifier_reruns_for_truth":0,
                           "campaign_reruns":0,"unit_a_a5_reexecutions":0}
    }
    return proof

if __name__ == "__main__":
    proof = run()
    out = Path(sys.argv[1])
    out.write_bytes(canonical(proof)+b"\n")
    print(json.dumps({"47_cases":len(proof["47_case_decision_ledger"]),
        "city":proof["aggregate"]["flagged_by_city"],"mechanisms":proof["aggregate"]["mechanisms"],
        "sha256":sha(out.read_bytes())},sort_keys=True))
