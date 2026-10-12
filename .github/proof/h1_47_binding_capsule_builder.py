#!/usr/bin/env python3
"""Git-only extraction of the original H1 47 source-membership flags.
No classifier replay, database, web evidence, or historical state modifications.
"""
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PROOF_COMMIT = "cbce9910a1a6b79753c06b0fe2cb2dffd84653dc"
PROOF_PATH = "research/neon_h1_6863_field_authority_audit_2026-10-12.json"
PROOF_BLOB = "ff6aa9d2de6d34f8d6c4334394829dfe2e8c9c3d"
PROOF_BYTES = 16876238
PROOF_SHA256 = "6c6232d201fb7cf010cae2afcad922733531640a7b3064d8d2fb71b75bd70dfd"
CAMPAIGN = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
BATCH_PREFIX = "research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27"
REPAIR_COMMIT = "5d18ef85a66384f189ede5ca5654d750f60f088b"
REPAIR_PATH = "research/historical_offline_repair_recovery_scan_2026-10-02.json"
REPAIR_BLOB = "26db43c2bd7fbd9e16a53e8ccefea080636bbb73"
EXPORT_COMMIT = "02ad2e8fadee78442753567bc2d3a540345d8e8a"
EXPORT_PATH = "research/attack_event_5city_persistence_identity_export_v2_2026-10-04.json"
EXPORT_BLOB = "a2e34c4a114ad335d35068d6c6a3a4606b09db7f"
EXPORT_BYTES = 29774541
EXPORT_SHA256 = "71ab9ac4f8dbeefcdb074ab60d485ac0546086ce4bd9db755af797398895d544"
HIST_WORKER = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
HIST_WORKER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
HIST_CLASSIFIER = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
HIST_CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
SOURCE_RE = re.compile(re.escape(BATCH_PREFIX) + r"/(lviv|sevastopol|cherkasy|sumy|zaporizhzhia)/batch_[0-9]{6}\.json$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")

def call(*args):
    return subprocess.check_output(("git",) + args, stderr=subprocess.PIPE)

def h256(raw):
    return hashlib.sha256(raw).hexdigest()

def canon(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def ensure(test, message):
    if not test:
        raise AssertionError(message)

def read_git(commit, path, blob=None, length=None, digest=None):
    resolved = call("rev-parse", commit + ":" + path).decode().strip()
    if blob is not None:
        ensure(resolved == blob, "WRONG_GIT_BLOB:" + path + ":" + resolved)
    raw = call("cat-file", "blob", resolved)
    computed = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    ensure(computed == resolved, "GIT_OBJECT_CONTENT_ID_MISMATCH:" + path)
    if length is not None:
        ensure(len(raw) == length, "WRONG_LENGTH:" + path)
    if digest is not None:
        ensure(h256(raw) == digest, "WRONG_SHA256:" + path)
    return raw, {"commit": commit, "path": path, "git_blob": resolved,
                 "bytes": len(raw), "sha256": h256(raw)}

def record_location(meta, value):
    return {**meta, "record_canonical_sha256": h256(canon(value))}

def field_contracts(worker_raw, monitor_raw, repair_meta):
    lines = {HIST_WORKER: worker_raw.decode("utf-8").splitlines(),
             HIST_CLASSIFIER: monitor_raw.decode("utf-8").splitlines()}
    blobs = {HIST_WORKER: HIST_WORKER_BLOB, HIST_CLASSIFIER: HIST_CLASSIFIER_BLOB}
    def cite(path, start, end):
        raw_lines = lines[path]
        ensure(len(raw_lines) >= end, "MISSING_FIELD_CONTRACT_LINES")
        excerpt = "\n".join(raw_lines[start-1:end])
        return {"commit": CAMPAIGN, "path": path, "git_blob": blobs[path],
                "line_start": start, "line_end": end,
                "exact_excerpt": excerpt, "excerpt_sha256": h256(excerpt.encode("utf-8"))}
    w = lambda a,b: cite(HIST_WORKER, a,b)
    m = lambda a,b: cite(HIST_CLASSIFIER,a,b)
    fields = {
        "classification_episode_id": (
            "Proposed classifier-selected singular episode from proposed_matched_episode_id, stored on the native historical observation.",
            "proposed_classification", [w(333,374),m(2294,2327)]),
        "classification_evidence": (
            "Structured candidate decision evidence payload, including a proposed classification episode; the live candidate object may store it. The historical batch instead stores selected component evidence.",
            "proposed_classification_evidence", [m(2352,2385),w(350,374)]),
        "candidate_matching": (
            "Publication-timestamp search against eligible alert windows; match results are not evidence that the event occurred inside an alert.",
            "search_context_temporal_candidate_set", [m(1520,1584),w(333,370)]),
        "matched_episode_id": (
            "Singular matching result when publication-window search yields a unique representation; candidate queue can later overwrite it with an approved proposed classification episode.",
            "context_dependent_search_or_approved_candidate_assignment", [m(1520,1584),m(2372,2385),w(333,342)]),
        "matched_episode_ids": (
            "Plural candidate set from publication-window temporal matching, not the final persisted membership list.",
            "search_context", [m(1537,1584),w(567,575)]),
        "trigger_episode_ids": (
            "Due-alert scheduler/queue discovery triggers recorded on candidate queue items, accumulated on rediscovery.",
            "retrieval_trigger_context", [m(2785,2803),m(2805,2829)]),
        "temporal_binding": (
            "Classifier temporal-evidence structure; may carry event time and supported episode IDs, distinct from publication-time matching and final H1 source-membership union.",
            "proposed_temporal_classification_evidence", [m(1976,2009),m(2172,2199),w(333,370)]),
        "episode_results[].source_observation_ids": (
            "Frozen historical batch episode membership list built from the union of observation_episode_refs: proposed classification episode and candidate-matching singular/plural IDs.",
            "original_frozen_episode_membership", [w(567,575),w(597,640)]),
        "frozen_source_memberships": (
            "Episode membership materialized in original accepted H1 batch; the repair overlay can add separately accepted contributors. This is not a guarantee of unique native classifier binding.",
            "frozen_historical_membership_decision", [w(597,640),w(567,575)]),
        "accepted_repair_contributors": (
            "Separately accepted first-persistence repair proof changed_targets[].contributing_observation_ids, with observation-level repair evidence; not the original batch membership.",
            "accepted_repair_overlay", [w(597,640)]),
    }
    ans = {}
    for field,(definition,role,citations) in fields.items():
        ans[field] = {"definition_and_computation": definition, "semantic_role": role,
                      "original_implementation_locations": citations,
                      "cross_field_equality_required_by_cited_contract": False if field in
                         {"candidate_matching","matched_episode_ids","trigger_episode_ids",
                          "episode_results[].source_observation_ids","frozen_source_memberships"} else
                         "NOT_ESTABLISHED_AS_GLOBAL_INVARIANT",
                      "role_determinable_from_cited_code": True,
                      "semantic_adjudication_of_47_cases": "NOT_PERFORMED"}
    ans["accepted_repair_contributors"]["accepted_contract_record"] = repair_meta
    ans["classification_evidence"]["availability_note"] = (
       "Inventoried because the original classifier emits this candidate-queue payload; do not assume that the native H1 observation contains a literal classification_evidence field.")
    return ans

def extract():
    raw_proof, proof_meta = read_git(PROOF_COMMIT, PROOF_PATH, PROOF_BLOB, PROOF_BYTES, PROOF_SHA256)
    proof = json.loads(raw_proof)
    ensure(isinstance(proof,dict) and proof.get("schema_version") ==
           "h1_6863_historical_field_authority_independent_reconstruction_v1", "PROOF_SCHEMA_UNEXPECTED")
    membership = proof["source_membership_ledger"]
    ensure(isinstance(membership,list) and len(membership) == 2340, "PROOF_SOURCE_MEMBERSHIP_COUNT_NOT_2340")
    flagged = [x for x in membership if x.get("authority_category") == "CONTRADICTION"]
    ids = sorted({x["observation_id"] for x in flagged})
    ensure(len(flagged) == 47, "FROZEN_PROOF_DISCREPANCY_COUNT_CHANGED:" + str(len(flagged)))
    ensure(len(ids) > 0, "FROZEN_PROOF_OBSERVATIONS_EMPTY")
    selected = set(ids)
    raw_repair, repair_meta = read_git(REPAIR_COMMIT,REPAIR_PATH,REPAIR_BLOB)
    repair = json.loads(raw_repair)
    raw_export, export_meta = read_git(EXPORT_COMMIT,EXPORT_PATH,EXPORT_BLOB,EXPORT_BYTES,EXPORT_SHA256)
    export = json.loads(raw_export)
    worker_raw, worker_meta = read_git(CAMPAIGN,HIST_WORKER,HIST_WORKER_BLOB)
    monitor_raw, monitor_meta = read_git(CAMPAIGN,HIST_CLASSIFIER,HIST_CLASSIFIER_BLOB)
    paths = sorted(p for p in call("ls-tree","-r","--name-only",CAMPAIGN,"--",BATCH_PREFIX).decode().splitlines()
                   if SOURCE_RE.fullmatch(p))
    ensure(len(paths) == 139,"NOT_ALL_139_ORIGINAL_BATCHES_AVAILABLE")
    obs = {}
    obs_meta = {}
    ep = {}
    ep_meta = {}
    original_set = set()
    original_counts = collections.Counter()
    batch_inventory = []
    selected_raw_records = {}
    selected_parent_records = {}
    for path in paths:
        raw, meta = read_git(CAMPAIGN,path)
        doc = json.loads(raw)
        city = doc["city_key"]
        ensure(city == path.split("/")[-2],"BATCH_CITY_MISMATCH")
        meta["city_key"] = city
        meta["batch_number"] = doc["batch_number"]
        meta["episode_rows"] = len(doc.get("episode_results") or [])
        meta["source_observations"] = len(doc.get("observations") or [])
        batch_inventory.append(meta)
        for row in doc.get("observations") or []:
            oid = row["observation_id"]
            ensure(oid not in obs,"DUPLICATE_ORIGINAL_OBSERVATION:" + oid)
            obs[oid] = row
            obs_meta[oid] = meta
            if oid in selected:
                selected_raw_records[oid] = record_location(meta,row)
        for row in doc.get("episode_results") or []:
            key = (city,row["episode_id"])
            ensure(key not in ep,"DUPLICATE_EPISODE:" + str(key))
            ep[key] = row
            ep_meta[key] = meta
            for oid in row.get("source_observation_ids") or []:
                pair = (city,row["episode_id"],oid)
                original_counts[pair] += 1
                ensure(original_counts[pair] == 1,"DUPLICATE_ORIGINAL_MEMBERSHIP:" + str(pair))
                original_set.add(pair)
                if oid in selected:
                    selected_parent_records[key] = record_location(meta,row)
    ensure(len(ep) == 6863,"ORIGINAL_EPISODE_POPULATION_CHANGED")
    ensure(set(ids) == set(selected_raw_records),"MISSING_SELECTED_SOURCE_RECORD")
    ensure(all(x in obs for (_,_,x) in original_set),"ORIGINAL_LINK_REFERENCES_MISSING_SOURCE")
    repair_targets = {}
    repair_members = set()
    changed_obs = {}
    for record in (repair.get("targets") or {}).get("changed_targets") or []:
        key=(record["city"],record["episode_id"])
        ensure(key in ep and key not in repair_targets,"INVALID_OR_DUPLICATE_REPAIR_TARGET")
        repair_targets[key] = record
        for oid in record.get("contributing_observation_ids") or []:
            ensure(oid in obs,"MISSING_REPAIR_CONTRIBUTOR")
            repair_members.add((key[0],key[1],oid))
            if oid in selected:
                selected_parent_records[key] = record_location(ep_meta[key],ep[key])
    ensure(len(repair_targets) == 25,"REPAIR_TARGET_COUNT_NOT_25")
    for record in (repair.get("observations") or {}).get("changed_observations") or []:
        oid = record["observation_id"]
        ensure(oid not in changed_obs and oid in obs,"INVALID_DUPLICATE_REPAIR_OBS")
        changed_obs[oid] = record
    effective_set = original_set | repair_members
    ensure(len(effective_set) == 2340,"NATIVE_EFFECTIVE_MEMBERSHIPS_NOT_2340")
    ledger_keys = [(m["city_key"],m["historical_episode_id"],m["observation_id"]) for m in membership]
    ensure(len(set(ledger_keys)) == 2340,"DUPLICATE_PROOF_MEMBERSHIP")
    ensure(set(ledger_keys) == effective_set,"PROOF_VS_HISTORICAL_MEMBERSHIP_SET_MISMATCH")
    proof_manifest = {(x["path"],x["git_blob"],x["bytes"],x["sha256"]) for x in proof["immutable_batch_manifest"]}
    our_manifest = {(x["path"],x["git_blob"],x["bytes"],x["sha256"]) for x in batch_inventory}
    ensure(proof_manifest == our_manifest,"ORIGINAL_139_BATCH_INVENTORY_DISAGREES_WITH_PROOF")
    selected_rows = [m for m in membership if m["observation_id"] in selected]
    frozen_selected = {(m["city_key"],m["historical_episode_id"],m["observation_id"]) for m in selected_rows}
    actual_selected = {t for t in effective_set if t[2] in selected}
    ensure(frozen_selected == actual_selected,"INCOMPLETE_SELECTED_OBSERVATION_MEMBERSHIP")
    by_oid = collections.defaultdict(list)
    classified_links = {(c["city_key"],c["historical_episode_id"]):c for c in export["classifications"]}
    link_by_native = collections.defaultdict(list)
    for row in export["source_links"]:
        link_by_native[(row["classification_key_v2"],row["observation_id"],row["content_sha256"])].append(row)
    associated_episode_rows = {}
    for key in sorted({(c,e) for c,e,oid in actual_selected}):
        row = ep[key]
        r = repair_targets.get(key)
        associated_episode_rows[key[0] + ":" + key[1]] = {
            "city_key":key[0], "episode_id":key[1],
            "original_record":row, "record_git_identity":selected_parent_records[key],
            "accepted_repair_target":r,
            "accepted_repair_target_record_sha256":h256(canon(r)) if r else None,
            "repaired_classifier_result":(r["repaired_outcome"] if r else row["classifier_result"]),
            "october_4_export_classification_replay_derived_not_original_authority": classified_links.get(key),
        }
    full_ledger_by_key = {k:row for k,row in zip(ledger_keys,membership)}
    for oid in ids:
        row = obs[oid]
        members = []
        for city,eid,o in sorted(actual_selected):
            if o != oid:
                continue
            key=(city,eid)
            source_key = (classified_links[key]["classification_key"], oid, row["content_hash"])
            links = link_by_native.get(source_key,[])
            ensure(len(links)==1,"EXPORT_NATIVE_LINK_MULTIPLICITY_CHANGED:" + str(source_key))
            native_matching = row.get("candidate_matching") or {}
            singular = row.get("classification_episode_id")
            match_eid = native_matching.get("matched_episode_id")
            native_foreign = bool(singular and singular != eid) or bool(
                native_matching.get("outcome") == "unique_match"
                and match_eid and match_eid != eid
                and eid not in (native_matching.get("matched_episode_ids") or []))
            proof_member = full_ledger_by_key[(city,eid,oid)]
            ensure((proof_member.get("authority_category")=="CONTRADICTION") == native_foreign,
                   "ORIGINAL_NATIVE_FLAG_RECONSTRUCTION_MISMATCH:"+str((city,eid,oid)))
            ensure(proof_member["frozen_original_member"] == ((city,eid,oid) in original_set),
                   "ORIGINAL_FROZEN_MEMBERSHIP_FLAG_MISMATCH")
            ensure(proof_member["accepted_repair_contributor"] == ((city,eid,oid) in repair_members),
                   "REPAIR_FROZEN_MEMBERSHIP_FLAG_MISMATCH")
            members.append({
                "city_key":city, "episode_id":eid,
                "original_batch_member": (city,eid,oid) in original_set,
                "accepted_repair_member": (city,eid,oid) in repair_members,
                "provisional_discrepancy_flag":native_foreign,
                "original_episode_record_key":city+":"+eid,
                "proof_ledger_record_sha256":h256(canon(proof_member)),
                "exact_original_proof_member":proof_member,
                "october_4_export_source_link_replay_derived_not_original_authority":links[0],
            })
        ensure(members,"SELECTED_SOURCE_HAS_NO_MEMBERS")
        by_oid[oid] = members
    selected_ledger_rows = [x for x in selected_rows if x.get("authority_category") == "CONTRADICTION"]
    ensure(selected_ledger_rows == flagged,"ORIGINAL_47_LEDGER_ORDER_CHANGED")
    original_flags_independent = sum(m["provisional_discrepancy_flag"] for rows in by_oid.values() for m in rows)
    ensure(original_flags_independent == 47,"INDEPENDENT_FLAGS_NOT_47")
    observation_capsule = []
    for oid in ids:
        o=obs[oid]
        selected_repair = changed_obs.get(oid)
        observation_capsule.append({
            "observation_id": oid,
            "city_key":obs_meta[oid]["city_key"],
            "source_family":o.get("source_family"),"source_type":o.get("source_type"),
            "source_url":o.get("source_url"),"source_timestamp":o.get("source_timestamp"),
            "content_hash_as_recorded_not_rehashed_article":o.get("content_hash"),
            "record_git_identity":selected_raw_records[oid],
            "original_native_observation_record":o,
            "accepted_repair_observation_change":selected_repair,
            "accepted_repair_observation_change_sha256":h256(canon(selected_repair)) if selected_repair else None,
            "all_frozen_effective_memberships":by_oid[oid],
            "member_total":len(by_oid[oid]),
            "flag_total":sum(x["provisional_discrepancy_flag"] for x in by_oid[oid]),
        })
    source_paths = sorted({x["record_git_identity"]["path"] for x in observation_capsule})
    episode_paths = sorted({x["record_git_identity"]["path"] for x in associated_episode_rows.values()})
    counts = {
        "complete_proof_membership_rows":len(membership),
        "original_campaign_batch_count":len(paths),
        "original_campaign_episode_count":len(ep),
        "original_campaign_source_observation_count":len(obs),
        "effective_historical_membership_count":len(effective_set),
        "exact_frozen_provisional_discrepancy_rows":len(flagged),
        "distinct_underlying_source_observations":len(ids),
        "expected_distinct_underlying_source_observations":27,
        "observation_count_differs_from_prior_report":len(ids)!=27,
        "all_membership_rows_for_selected_source_observations":len(selected_rows),
        "additional_unflagged_memberships_for_selected_observations":len(selected_rows)-len(flagged),
        "unique_associated_episode_rows":len(associated_episode_rows),
        "original_source_batch_paths_selected":len(source_paths),
        "associated_parent_batch_paths_selected":len(episode_paths),
        "all_original_139_batch_manifest_matches_frozen_proof":True,
        "all_selected_observations_exist_in_original_Git_batches":True,
        "selected_membership_pairs_equal_original_plus_accepted_repairs":True,
        "selected_provisional_flags_recomputed_directly_from_native_records":True,
        "export_is_separate_derived_evidence_not_accepted_native_truth":True
    }
    return {
        "schema_version":"h1_47_binding_evidence_capsule_v1",
        "status":"FROZEN_EVIDENCE_RECOVERY_ONLY_NO_SEMANTIC_ADJUDICATION",
        "scope_guards":{"neon_sql":0,"neon_writes":0,"classifier_reruns":0,
                        "historical_backfills":0,"source_rebinding":0,
                        "historical_repair_overlay_changes":0,"main_changes":0,
                        "site_prod_changes":0,"production_configuration_changes":0,
                        "all_47_historical_authority_decisions":"NOT_PERFORMED"},
        "input_git_objects":{"frozen_original_6863_audit":proof_meta,
                             "original_139_batches_commit":CAMPAIGN,
                             "original_139_batch_manifest":batch_inventory,
                             "historical_repair":repair_meta,
                             "historical_october_4_git_derived_export":export_meta,
                             "original_historical_worker":worker_meta,
                             "original_historical_classifier":monitor_meta},
        "population_and_integrity_checks":counts,
        "original_47_row_discrepancy_ledger_exact":flagged,
        "unique_underlying_observation_ids":ids,
        "observations_with_all_memberships_and_native_evidence":observation_capsule,
        "original_episode_records_for_selected_memberships":associated_episode_rows,
        "selected_historical_batch_paths":{"observation_records":source_paths,
                                            "associated_episode_records":episode_paths},
        "historical_field_contract_inventory":field_contracts(worker_raw,monitor_raw,repair_meta),
        "availability":{"frozen_full_proof":"EXACT_FULL_GIT_BLOB_VERIFIED",
                        "139_original_batches":"EXACT_FULL_GIT_OBJECTS_VERIFIED",
                        "historical_repair":"EXACT_GIT_BLOB_VERIFIED",
                        "october_4_export":"EXACT_FULL_GIT_BLOB_VERIFIED_DERIVED_INPUT_AUTHORITY_PARTIAL",
                        "historical_worker_and_classifier":"EXACT_GIT_OBJECTS_VERIFIED",
                        "original_external_publisher_versions":"NOT_ESTABLISHED_BY_GIT_CAPSULE",
                        "unavailable_required_git_objects":[],
                        "incomplete_selected_observation_records":[]},
        "authority_guard":"47 flags retained as provisional differences; no false-positive or erroneous-membership decisions made."
    }

if __name__ == "__main__":
    ensure(len(sys.argv)==2,"USAGE: builder.py OUTPUT.json")
    data=extract()
    raw=canon(data)+b"\n"
    Path(sys.argv[1]).write_bytes(raw)
    print(json.dumps({"builder_sha256":h256(raw),
                      "bytes":len(raw),"population":data["population_and_integrity_checks"]},
                     sort_keys=True))
