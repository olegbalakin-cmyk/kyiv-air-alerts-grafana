#!/usr/bin/env python3
"""Offline Unit A frozen membership lineage and impact diagnostic.

Reads only pinned local Git objects. Classifier, composition, database and
discovery modules are never imported or invoked. No external evidence requests.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any

BASE = "387f5ff5550d5ab5164e8f10fd776d9d6e7ec6cc"
BRANCH = "attack-event-unit-a-membership-semantics-diagnostic-2026-10-09"
OUT = Path("research/attack_event_execution_unit_a_membership_semantics_diagnostic_2026-10-09.json")
A3_PATH = "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
A3_COMMIT = "1422e8482303ec9262647ca55fef753a9aa2b3ea"
A3_BLOB = "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640"
A3_SHA = "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"
A4_PATH = "research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume_2026-10-09.json"
A4_BLOB = "d7c938f2ee9b16e491ec53cbcb5781efa6bcff27"
A4_SHA = "191bd60bda0e3d7d73f254229d0de08b285e96d053bd275c597712512251f00c"
PROOF_PATH = "research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json"
PROOF_COMMIT = "a0eb594dd4240d1d923ca5262725fc42f4807338"
PROOF_BLOB = "a7e6b992180bfef3dd640fcd9ef8eec8a6436af7"
PROOF_SHA = "568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891"
HELPER_PATH = ".github/proof/attack_event_unit_a_source_identity_adapter_proof.py"
HELPER_BLOB = "83dd5279f4aeb17c8e06fe5bfaf143c07059efc2"
A3_HARNESS_PATH = ".github/proof/attack_event_unit_a_bounded_classification_replay.py"
A3_HARNESS_COMMIT = "2c9f48febd00ef11d81cff06248e65ab4b769203"
A3_HARNESS_BLOB = "f72f08336f1ebebcc766841f7baf73d196ed092a"
HIST_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
HIST_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
HIST_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
PROD_COMMIT = "51adc76b715669e46e8c2c936906022d4d96ed44"
PROD_PATH = "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py"
PROD_BLOB = "0118ca9e5f1308173e657257f1b49fe91cc19fe1"
PARITY_BLOB = "e4df7ada4f15042a8d3de106379acc42f1b398e5"
PIN_MON_COMMIT = HIST_COMMIT
PIN_MON_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
PIN_MON_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
EXPECT_A3 = {"STRICT_EVENT_POSITIVE":9, "SENSITIVITY_EVENT_POSITIVE":1,
             "NO_CONFIRMED_EVENT":1260, "NEEDS_REVIEW":443}
VERDICTS = ("STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE",
            "NEEDS_REVIEW", "NO_CONFIRMED_EVENT")
POSITIVE = set(VERDICTS[:2])
CHANNELS = ("MATCHING_MATCHED_EPISODE_ID","MATCHING_MATCHED_EPISODE_IDS",
            "PROPOSED_MATCHED_EPISODE_ID","TEMPORAL_BINDING_EPISODE_ID",
            "TEMPORAL_BINDING_SUPPORTED_EPISODE_IDS","REVIEW_PROVENANCE_TARGET_EPISODE_ID")
BROADER = CHANNELS[3:]


class DiagnosticStop(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise DiagnosticStop(message)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def git(*args):
    p = subprocess.run(["git", *args], capture_output=True,
                       env=dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"))
    require(p.returncode == 0,
            "LOCAL_FROZEN_OBJECT_MISSING:" + " ".join(args[:2]) + ":" +
            p.stderr.decode("utf-8", "replace")[-180:])
    return p.stdout


def pinned(commit, path, blob, expected_sha=None):
    observed = git("rev-parse", f"{commit}:{path}").decode().strip()
    require(observed == blob, "PINNED_BLOB_DRIFT:" + path)
    raw = git("show", f"{commit}:{path}")
    if expected_sha:
        require(sha(raw) == expected_sha, "PINNED_SHA_DRIFT:" + path)
    return raw


def extract(source, names, label, extra=None):
    tree = ast.parse(source.decode("utf-8"))
    defs = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
    require(all(n in defs for n in names), "PINNED_FUNCTION_NOT_FOUND:" + label + ": available=" + ",".join(sorted(defs)))
    module = ast.fix_missing_locations(ast.Module(
        body=[copy.deepcopy(defs[n]) for n in names], type_ignores=[]))
    env = {"__builtins__":__builtins__, "Any":Any, "json":json,
           "hashlib":hashlib, "Counter":Counter}
    env.update(extra or {})
    exec(compile(module, label, "exec"), env)
    return env


def channels(dec, eid):
    match = dec.get("matching") or {}
    temporal = dec.get("temporal_binding") or {}
    review = dec.get("review_provenance_adapter") or {}
    return tuple(name for name, present in (
        (CHANNELS[0], str(match.get("matched_episode_id") or "") == eid),
        (CHANNELS[1], eid in {str(x) for x in match.get("matched_episode_ids") or [] if x}),
        (CHANNELS[2], str(dec.get("proposed_matched_episode_id") or "") == eid),
        (CHANNELS[3], str(temporal.get("episode_id") or "") == eid),
        (CHANNELS[4], eid in {str(x) for x in temporal.get("supported_episode_ids") or [] if x}),
        (CHANNELS[5], str(review.get("target_episode_id") or "") == eid),
    ) if present)


def lineage_contract():
    a3raw = pinned(A3_HARNESS_COMMIT, A3_HARNESS_PATH, A3_HARNESS_BLOB)
    hist = pinned(HIST_COMMIT, HIST_PATH, HIST_BLOB)
    prod = pinned(PROD_COMMIT, PROD_PATH, PROD_BLOB)
    monitor = pinned(PIN_MON_COMMIT, PIN_MON_PATH, PIN_MON_BLOB)
    require(sha(git("cat-file", "blob", PARITY_BLOB)) != "", "PARITY_BLOB_MISSING")
    parity = git("cat-file", "blob", PARITY_BLOB)

    ae = extract(a3raw, ["related", "qa_for"], "frozen_A3_related")
    he = extract(hist, ["observation_episode_refs"], "historical_episode_membership")
    pe = extract(prod, ["_episode_refs"], "production_episode_membership")
    parity_tree = ast.parse(parity.decode("utf-8"))
    workers = [n.value.value for n in parity_tree.body
               if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant)
               and isinstance(n.value.value,str)
               and any(isinstance(t,ast.Name) and t.id=="REPLAY_WORKER" for t in n.targets)]
    require(len(workers)==1, "PARITY_WORKER_CONTRACT_MISSING")
    py = extract(workers[0].encode("utf-8"), ["residual_qa"], "accepted_parity_relation")
    me = extract(monitor, ["apply_matching_result"], "pinned_matching")
    adapter = extract(prod, ["canonical_json_bytes", "canonical_sha256",
                             "_normalized_source_content", "_review_provenance"],
                      "pinned_persistence_identity")

    for field in CHANNELS:
        d = {"matching":{"matched_episode_id":None,"matched_episode_ids":[]},
             "proposed_matched_episode_id":None,
             "temporal_binding":{"episode_id":None,"supported_episode_ids":[]},
             "review_provenance_adapter":{"target_episode_id":None},
             "proposed_outcome":"needs_review","reason_codes":["MATCH_AMBIGUOUS"],
             "exact_city_classification_evidence":{"present":True}}
        if field == CHANNELS[0]: d["matching"]["matched_episode_id"] = "target"
        if field == CHANNELS[1]: d["matching"]["matched_episode_ids"] = ["target"]
        if field == CHANNELS[2]: d["proposed_matched_episode_id"] = "target"
        if field == CHANNELS[3]: d["temporal_binding"]["episode_id"] = "target"
        if field == CHANNELS[4]: d["temporal_binding"]["supported_episode_ids"] = ["target"]
        if field == CHANNELS[5]: d["review_provenance_adapter"]["target_episode_id"] = "target"
        target = "target"
        obs = {"classification_episode_id":d["proposed_matched_episode_id"],
               "candidate_matching":d["matching"]}
        item = {"classification_evidence":{"classification_episode_id":d["proposed_matched_episode_id"]},
                "matched_episode_id":d["matching"]["matched_episode_id"],
                "matched_episode_ids":d["matching"]["matched_episode_ids"]}
        a3_hit = ae["related"](d, target)
        hist_hit = target in he["observation_episode_refs"](obs)
        prod_hit = target in pe["_episode_refs"](item)
        parity_hit = bool(py["residual_qa"]([(d,{"source_url":"https://example.invalid"})],target))
        should_persist = field not in BROADER
        require(a3_hit is True, "A3_RELATION_CONTRACT_DRIFT:" + field)
        require(hist_hit == should_persist, "HISTORICAL_RELATION_CONTRACT_DRIFT:" + field)
        require(prod_hit == should_persist, "PRODUCTION_RELATION_CONTRACT_DRIFT:" + field)
        require(parity_hit == should_persist, "PARITY_RELATION_CONTRACT_DRIFT:" + field)

    return {
       "authority_blobs":{
          "a3_harness":A3_HARNESS_BLOB, "historical_builder":HIST_BLOB,
          "production_persistence":PROD_BLOB, "multicity_parity":PARITY_BLOB,
          "pinned_monitor_matching":PIN_MON_BLOB
       },
       "a3_independent_channels":list(CHANNELS),
       "historical_and_production_independent_channels":list(CHANNELS[:3]),
       "multicity_parity_independent_channels":list(CHANNELS[:3]),
       "synthetic_executable_semantic_cases_passed":len(CHANNELS),
       "first_executable_semantic_point_in_pinned_chain":{
           "artifact":"A3 execution harness",
           "commit":A3_HARNESS_COMMIT,
           "blob":A3_HARNESS_BLOB,
           "broad_channels_first_admitted":list(BROADER),
           "scope":"the four pinned executable authorities; not a claim about all repo history"
       },
       "conclusion":"A3_AGGREGATION_MEMBERSHIP_DRIFT = PROVEN",
       "rationale":"Historical builder, multicity parity, and production persistence exclude temporal/review target IDs as independent membership channels; A3 related() admits them. Executable pinned functions pass each six-channel control."
    }, ae, pe, me, adapter


def diagnostic():
    # All inputs and caches are reconstructed on every invocation.
    lineage, ae, pe, me, adapter = lineage_contract()
    helper_raw = pinned(PROOF_COMMIT, HELPER_PATH, HELPER_BLOB)
    helper = {"__name__":"unit_a_frozen_helper_no_main"}
    exec(compile(helper_raw, HELPER_PATH, "exec"), helper)
    checked, docs = helper["verify_inputs"]()
    a1 = json.loads(docs["A1"])
    corpus, a1episodes, store, refs_total = helper["decode_a1"](a1)
    a3 = json.loads(docs["A3"])
    eps, decision_store, a1_by_uid = helper["verify_a3"](a3, a1episodes)
    require(sha(docs["A3"]) == A3_SHA, "FROZEN_A3_SHA_DRIFT")
    a4raw = pinned(BASE, A4_PATH, A4_BLOB, A4_SHA)
    blocked = json.loads(a4raw)
    require(blocked.get("first_failing_gate") == "UNIT_A_SOURCE_MEMBERSHIP_SEMANTICS_DIVERGENCE",
            "A4_RESUME_GATE_DRIFT")
    proofraw = pinned(PROOF_COMMIT, PROOF_PATH, PROOF_BLOB, PROOF_SHA)
    proof = json.loads(proofraw)
    require(proof.get("verdict") == "ATTACK-EVENT EXECUTION UNIT A SOURCE IDENTITY ADAPTER = PROVEN" and
            proof.get("run_a_mapping_sha256") == proof.get("run_b_mapping_sha256") and
            proof.get("run_a_run_b_semantic_mismatches") == 0, "SOURCE_IDENTITY_PROOF_DRIFT")
    require(refs_total == 99663, "A1_SOURCE_OCCURRENCE_DRIFT")

    snapshot = {(x["commit"],x["path"]):x for x in proof["frozen_queue_inputs"]}
    require(len(snapshot) == 89, "QUEUE_PIN_COUNT_DRIFT")
    norm = adapter["_normalized_source_content"]
    content_hash = adapter["canonical_sha256"]
    queue_cache = {}
    observed_queue_pairs = set()
    a3_members, persisted_members, a3_only, persisted_only = 0,0,0,0
    affected = set()
    taxonomy = Counter()
    per_channel, by_outcome, by_temporal, by_matching, by_city, by_a3verdict = (Counter() for _ in range(6))
    review_effect = 0
    qa_effect = 0
    pos_contributor_effect = 0
    event_type_effect = 0
    composition_effect = 0
    final_verdict_effect = 0
    membership_only = 0
    qa_only = 0
    evid_impact = 0
    review_prov_impact = 0
    key_impact = 0
    positive_ref_hits = set()
    positive_occurrence_hits = 0
    direct_strict_impacts = 0
    sensitivity_impacts = 0
    composed_contrib_hits = 0
    per_qa = defaultdict(Counter)
    transitions = {old:{new:0 for new in VERDICTS} for old in VERDICTS}
    counterfactual_distribution = Counter()
    examples = []
    old_positive_refs = 0
    candidate_occs = 0
    composed_count = 0
    positive_disposition_differences = 0
    positive_to_negative = 0
    negative_or_review_to_positive = 0
    review_to_negative = 0
    positive_tier_differences = 0
    city_representability_failures = 0

    for ep in eps:
        uid = ep["alert_episode_uid"]
        eid = str(ep["episode_id"])
        city = str(ep["city_key"])
        a1_ep = a1_by_uid[uid]
        refs, drefs = ep["candidate_input_refs"], ep["candidate_decision_refs"]
        require(len(refs) == len(drefs), "A1_A3_ROW_ALIGNMENT_DRIFT:" + uid)
        rows = []
        if refs:
            qi = (a1_ep.get("evidence_provenance") or {}).get("collection_queue_identity") or {}
            pair = (str(qi.get("commit") or ""), str(qi.get("path") or ""))
            pin = snapshot.get(pair)
            require(pin is not None, "QUEUE_PIN_UNKNOWN:" + uid)
            if pair not in queue_cache:
                raw = pinned(pair[0], pair[1], pin["blob"], pin["sha256"])
                queue = json.loads(raw)
                require(isinstance(queue,list) and len(queue) == pin["rows"],
                        "QUEUE_ROW_COUNT_DRIFT:" + uid)
                queue_cache[pair] = queue
            observed_queue_pairs.add(pair)
            chosen = helper["selected_queue_rows"](
                queue_cache[pair],eid,
                (a1_ep.get("evidence_provenance") or {}).get("followup_72h_checked_at"))
            provenance = (a1_ep.get("evidence_provenance") or {}).get("candidate_selection_provenance") or []
            require(len(chosen) == len(refs) == len(provenance), "QUEUE_ALIGNMENT_DRIFT:" + uid)
            for i,(ref,dr,original,prov) in enumerate(zip(refs,drefs,chosen,provenance)):
                cand,dec = store[ref],decision_store[dr]
                require(original.get("candidate_id") == cand.get("candidate_id") == prov.get("candidate_id")
                        and prov.get("candidate_input_sha256") == ref
                        and norm(original) == norm(cand), "SOURCE_PARITY_DRIFT:" + uid)
                row = copy.deepcopy(original)
                me["apply_matching_result"](row, dec.get("matching") or {})
                row["status"] = dec.get("proposed_outcome")
                row["classification_reason_codes"] = list(dec.get("reason_codes") or [])
                row["event_types"] = list(dec.get("event_types") or [])
                row["classification_evidence"] = {
                   "classification_episode_id": dec.get("proposed_matched_episode_id")}
                if row["status"] in {"approved_strict","approved_sensitivity"}:
                    row["matched_episode_id"] = dec.get("proposed_matched_episode_id")
                rows.append((row,dr,ref,dec,cand))
            candidate_occs += len(rows)

        comp = ep.get("composition_provenance")
        comp_ok = (isinstance(comp,dict)
                   and comp.get("final_composed_verdict") == "approved_strict"
                   and str(comp.get("target_episode_id") or "") == eid)
        if comp is not None:
            composed_count += 1
            require(comp_ok and ep["verdict"] == "STRICT_EVENT_POSITIVE" and
                    not ep.get("direct_strict_contributor_refs"),
                    "COMPOSITION_FROZEN_SHAPE_DRIFT:" + uid)
            anchor = str(comp.get("anchor_candidate_id") or "")
            anchors = [x for x in rows if str(x[0].get("candidate_id") or "") == anchor]
            require(len(anchors) == 1 and bool(anchor), "COMPOSITION_ANCHOR_UNRESOLVED:" + uid)
            ar = anchors[0][0]
            ar["status"] = "approved_strict"
            ar["matched_episode_id"] = eid
            ar["composition_provenance"] = copy.deepcopy(comp)
            ar["classification_evidence"]["episode_level_composition"] = copy.deepcopy(comp)

        a3_positions = [i for i,x in enumerate(rows) if ae["related"](x[3],eid)]
        persist_positions = [i for i,x in enumerate(rows)
                             if str(x[0].get("city_key") or "") == city
                             and eid in pe["_episode_refs"](x[0])]
        a3_drefs = [rows[i][1] for i in a3_positions]
        prod_drefs = [rows[i][1] for i in persist_positions]
        require(a3_drefs == list(ep.get("target_related_candidate_decision_refs") or []),
                "A3_RELATED_REF_REPLAY_DRIFT:" + uid)
        a3_members += len(a3_positions)
        persisted_members += len(persist_positions)
        left, right = set(a3_positions), set(persist_positions)
        missing_idxs, extra_idxs = sorted(left-right), sorted(right-left)
        a3_only += len(missing_idxs)
        persisted_only += len(extra_idxs)
        if missing_idxs or extra_idxs: affected.add(uid)
        if extra_idxs: city_representability_failures += len(extra_idxs)
        for i in missing_idxs:
            row,dr,ref,dec,cand = rows[i]
            basis = channels(dec,eid)
            require(basis and not any(c in basis for c in CHANNELS[:3]),
                    "UNEXPLAINED_MEMBERSHIP_BASIS:" + uid)
            taxonomy["+".join(c for c in BROADER if c in basis)] += 1
            for ch in basis: per_channel[ch] += 1
            by_outcome[str(dec.get("proposed_outcome") or "NULL")] += 1
            by_temporal[str((dec.get("temporal_binding") or {}).get("code") or "NULL")] += 1
            by_matching[str((dec.get("matching") or {}).get("outcome") or "NULL")] += 1
            by_city[city] += 1
            by_a3verdict[ep["verdict"]] += 1
            if dr in (ep.get("final_contributor_refs") or []):
                positive_ref_hits.add((uid,dr))
                positive_occurrence_hits += 1
            if len(examples) < 12:
                examples.append({
                   "alert_episode_uid":uid, "episode_id":eid, "city_key":city,
                   "decision_ref":dr, "candidate_input_ref":ref,
                   "proposed_outcome":dec.get("proposed_outcome"),
                   "matching_outcome":(dec.get("matching") or {}).get("outcome"),
                   "temporal_code":(dec.get("temporal_binding") or {}).get("code"),
                   "relation_basis":list(basis),"frozen_a3_verdict":ep["verdict"]
                })

        # Execute only frozen A3 aggregation primitives, not classifier/composition.
        qa_orig = sorted({q for i in a3_positions
                          for q in ae["qa_for"](rows[i][3],eid,rows[i][4])})
        qa_new = sorted({q for i in persist_positions
                         for q in ae["qa_for"](rows[i][3],eid,rows[i][4])})
        require(qa_orig == sorted(ep.get("qa_reasons") or []),
                "A3_FROZEN_QA_REPLAY_DRIFT:" + uid)
        strict_idxs = [i for i in persist_positions
                       if rows[i][3].get("proposed_outcome") == "approved_strict"
                       and str(rows[i][3].get("proposed_matched_episode_id") or "") == eid]
        sens_idxs = [i for i in persist_positions
                     if rows[i][3].get("proposed_outcome") == "approved_sensitivity"
                     and str(rows[i][3].get("proposed_matched_episode_id") or "") == eid]
        new_review = [rows[i][1] for i in persist_positions
                      if rows[i][3].get("proposed_outcome") == "needs_review"]
        old_review = list(ep.get("review_contributor_refs") or [])
        old_positive_refs += len(ep.get("final_contributor_refs") or [])
        if strict_idxs or comp_ok:
            new_verdict = "STRICT_EVENT_POSITIVE"
        elif sens_idxs:
            new_verdict = "SENSITIVITY_EVENT_POSITIVE"
        elif new_review or qa_new:
            new_verdict = "NEEDS_REVIEW"
        else:
            new_verdict = "NO_CONFIRMED_EVENT"
        # Frozen composition is held fixed; no new composed result is computed.
        if strict_idxs:
            new_contrib = [rows[i][1] for i in strict_idxs]
            new_events = list(dict.fromkeys(et for i in strict_idxs
                         for et in rows[i][3].get("event_types") or []))
        elif comp_ok:
            new_contrib = list(ep.get("final_contributor_refs") or [])
            new_events = list(ep.get("event_types") or [])
        elif sens_idxs:
            new_contrib = [rows[i][1] for i in sens_idxs]
            new_events = list(dict.fromkeys(et for i in sens_idxs
                         for et in rows[i][3].get("event_types") or []))
        else:
            new_contrib, new_events = [], []
        require(new_verdict in VERDICTS, "UNEXPECTED_COUNTERFACTUAL_VERDICT:" + uid)
        counterfactual_distribution[new_verdict] += 1
        transitions[ep["verdict"]][new_verdict] += 1

        if uid not in affected:
            require(new_verdict == ep["verdict"] and
                    qa_new == sorted(ep.get("qa_reasons") or []),
                    "UNAFFECTED_VERDICT_QA_DRIFT:" + uid)
            continue

        qa_changed = qa_orig != qa_new
        review_changed = Counter(new_review) != Counter(old_review)
        positive_changed = (Counter(new_contrib) !=
                            Counter(ep.get("final_contributor_refs") or []))
        event_changed = sorted(set(new_events)) != sorted(set(ep.get("event_types") or []))
        comp_ids = {str(x) for x in (comp or {}).get("contributing_candidate_ids") or []}
        comp_changed = bool(comp_ok and any(
           str(rows[i][4].get("candidate_id") or "") in comp_ids for i in missing_idxs))
        verdict_changed = new_verdict != ep["verdict"]
        broad_rows = [rows[i][0] for i in a3_positions]
        narrow_rows = [rows[i][0] for i in persist_positions]
        broad_membership = sorted((str(row.get("candidate_id") or ""),
                           content_hash(norm(row))) for row in broad_rows)
        narrow_membership = sorted((str(row.get("candidate_id") or ""),
                           content_hash(norm(row))) for row in narrow_rows)
        evidence_changed = broad_membership != narrow_membership
        broad_review = adapter["_review_provenance"](broad_rows)
        narrow_review = adapter["_review_provenance"](narrow_rows)
        review_provenance_changed = broad_review != narrow_review
        identity_changed = (evidence_changed or qa_changed or review_provenance_changed
                            or verdict_changed or event_changed)
        require(evidence_changed, "AFFECTED_EVIDENCE_SET_NOT_CHANGED:" + uid)
        if qa_changed: qa_effect += 1
        if review_changed: review_effect += 1
        if positive_changed: pos_contributor_effect += 1
        if event_changed: event_type_effect += 1
        if comp_changed: composition_effect += 1
        if verdict_changed: final_verdict_effect += 1
        if evidence_changed: evid_impact += 1
        if review_provenance_changed: review_prov_impact += 1
        if identity_changed: key_impact += 1
        if not any((qa_changed,review_changed,positive_changed,event_changed,
                    comp_changed,verdict_changed)): membership_only += 1
        if qa_changed and not any((review_changed,positive_changed,event_changed,
                                   comp_changed,verdict_changed)): qa_only += 1
        if bool(ep["verdict"] in POSITIVE) != bool(new_verdict in POSITIVE):
            positive_disposition_differences += 1
            if ep["verdict"] in POSITIVE: positive_to_negative += 1
            else: negative_or_review_to_positive += 1
        if (ep["verdict"] in POSITIVE and new_verdict in POSITIVE
                and ep["verdict"] != new_verdict):
            positive_tier_differences += 1
        if ep["verdict"] == "NEEDS_REVIEW" and new_verdict == "NO_CONFIRMED_EVENT":
            review_to_negative += 1
        if set(ep.get("direct_strict_contributor_refs") or []) & {
            rows[i][1] for i in missing_idxs}:
            direct_strict_impacts += 1
        if set(ep.get("sensitivity_contributor_refs") or []) & {
            rows[i][1] for i in missing_idxs}:
            sensitivity_impacts += 1
        if comp_changed: composed_contrib_hits += sum(
            str(rows[i][4].get("candidate_id") or "") in comp_ids for i in missing_idxs)
        for code in set(qa_orig) | set(qa_new):
            if code in qa_orig and code in qa_new: per_qa[code]["preserved"] += 1
            elif code in qa_orig: per_qa[code]["removed"] += 1
            else: per_qa[code]["newly_added"] += 1

    require((a3_members,persisted_members,a3_only,persisted_only,len(affected),
             candidate_occs,len(observed_queue_pairs),composed_count,old_positive_refs)
            == (1741,1559,182,0,130,99663,89,3,18),
            "UNIT_A_MEMBERSHIP_DIVERGENCE_NOT_REPRODUCIBLE:"+
            json.dumps({"a3":a3_members,"production":persisted_members,
               "a3_only":a3_only,"production_only":persisted_only,
               "affected":len(affected),"occurrences":candidate_occs,
               "queue_count":len(observed_queue_pairs),"composed":composed_count,
               "positive_refs":old_positive_refs},sort_keys=True))
    require(dict(Counter(ep["verdict"] for ep in eps)) == EXPECT_A3,
            "FROZEN_A3_DISTRIBUTION_DRIFT")
    require(not any(v["newly_added"] for v in per_qa.values()),
            "QA_NEWLY_ADDED_AFTER_NARROWING")
    require(sum(counterfactual_distribution.values()) == 1713,
            "COUNTERFACTUAL_DISTRIBUTION_SUM_DRIFT")
    require(sum(v for a in transitions.values() for v in a.values()) == 1713,
            "TRANSITION_MATRIX_SUM_DRIFT")
    require(key_impact >= evid_impact, "CLASSIFICATION_IDENTITY_IMPACT_DRIFT")

    return {
        "schema_version":1,
        "kind":"attack_event_execution_unit_a_membership_semantics_diagnostic",
        "diagnostic_conclusion":lineage["conclusion"],
        "frozen_authorities":{
           "a3":{"commit":A3_COMMIT,"path":A3_PATH,"blob":A3_BLOB,"sha256":A3_SHA},
           "blocked_a4_resume":{"commit":BASE,"path":A4_PATH,"blob":A4_BLOB,"sha256":A4_SHA},
           "a1_corpus_sha256":helper["A1_CORPUS_SHA"],
           "source_identity_proof":{"commit":PROOF_COMMIT,"blob":PROOF_BLOB,"sha256":PROOF_SHA},
           **lineage["authority_blobs"]
        },
        "lineage":{k:v for k,v in lineage.items() if k!="authority_blobs"},
        "counts":{
           "unit_a_targets":1713,"candidate_occurrences":candidate_occs,
           "a3_membership_occurrences":a3_members,
           "historical_production_membership_occurrences":persisted_members,
           "a3_only_occurrences":a3_only,"production_only_occurrences":persisted_only,
           "affected_episodes":len(affected),"positive_contributor_refs_total":old_positive_refs,
           "positive_contributor_intersecting_refs":len(positive_ref_hits),
           "positive_contributor_intersecting_occurrences":positive_occurrence_hits,
           "composed_strict_episodes":composed_count,"queue_snapshots":len(observed_queue_pairs),
           "city_representability_failures":city_representability_failures
        },
        "mismatch_taxonomy":{
           "exclusive_relation_basis":dict(sorted(taxonomy.items())),
           "by_all_relating_channels":dict(sorted(per_channel.items())),
           "by_proposed_outcome":dict(sorted(by_outcome.items())),
           "by_temporal_binding_code":dict(sorted(by_temporal.items())),
           "by_matching_outcome":dict(sorted(by_matching.items())),
           "by_city":dict(sorted(by_city.items())),
           "by_frozen_a3_episode_verdict":dict(sorted(by_a3verdict.items()))
        },
        "effects":{
           "MEMBERSHIP_ONLY_NO_VERDICT_EFFECT":membership_only,
           "QA_EFFECT_ONLY":qa_only,
           "QA_EFFECT_ANY":qa_effect,
           "REVIEW_EFFECT":review_effect,
           "POSITIVE_CONTRIBUTOR_EFFECT":pos_contributor_effect,
           "EVENT_TYPE_EFFECT":event_type_effect,
           "COMPOSITION_EFFECT":composition_effect,
           "FINAL_VERDICT_EFFECT":final_verdict_effect,
           "direct_strict_contributor_episodes_affected":direct_strict_impacts,
           "sensitivity_contributor_episodes_affected":sensitivity_impacts,
           "frozen_composed_contributor_occurrences_intersecting_mismatches":composed_contrib_hits,
           "categories_overlap":True,
           "definitions":{
              "MEMBERSHIP_ONLY_NO_VERDICT_EFFECT":"No QA, review, positive-contributor, event-type, composition, or verdict change",
              "QA_EFFECT_ONLY":"QA differs but no review, positive-contributor, event-type, composition, or verdict change",
              "REVIEW_EFFECT":"review_contributor_refs multiset changed",
              "COMPOSITION_EFFECT":"Frozen composed-strict contributing candidate ID intersects an A3-only membership occurrence"
           }
        },
        "qa_impact":{"affected_episode_count":qa_effect,
                     "per_code":{k:dict(per_qa[k]) for k in sorted(per_qa)},
                     "newly_added_total":sum(c["newly_added"] for c in per_qa.values()),
                     "materialized_a3_qa_is_unchanged":True},
        "diagnostic_counterfactual":{
           "label":"HISTORICAL_BUILDER_EQUIVALENT_FROZEN_AGGREGATION_NOT_NEW_CLASSIFICATION",
           "frozen_a3_distribution":EXPECT_A3,
           "narrowed_membership_distribution":{k:counterfactual_distribution[k] for k in VERDICTS},
           "full_transition_matrix":transitions,
           "total_final_verdict_differences":final_verdict_effect,
           "positive_disposition_differences":positive_disposition_differences,
           "positive_to_nonpositive":positive_to_negative,
           "nonpositive_to_positive":negative_or_review_to_positive,
           "positive_tier_differences":positive_tier_differences,
           "needs_review_to_no_confirmed_event":review_to_negative
        },
        "classification_identity_impact":{
           "evidence_set_sha256_impacted_episodes":evid_impact,
           "qa_impacted_episodes":qa_effect,
           "verdict_impacted_episodes":final_verdict_effect,
           "event_types_impacted_episodes":event_type_effect,
           "review_provenance_sha_impacted_episodes":review_prov_impact,
           "classification_key_necessarily_differs":key_impact,
           "replacement_keys_created":0,
           "evidence_comparison":"sorted multiset of production-normalized [candidate_id,content_sha256], via pinned pure production functions"
        },
        "bounded_examples":examples,
        "safety":{
           "classifier_executions":0,"composition_executions":0,
           "discovery_executions":0,"external_evidence_requests":0,
           "neon_queries":0,"db_connections":0,"db_queries":0,
           "db_writes":0,"ddl":0,"a3_mutations":0,"production_mutation":"NO",
           "a5_runs":0,"unit_b_runs":0,"unit_c_runs":0
        }
    }


def disable_network():
    def fail(*_args, **_kwargs):
        raise RuntimeError("NETWORK_DISABLED")
    socket.socket.connect = fail
    socket.create_connection = fail
    socket.getaddrinfo = fail


def main():
    require(git("rev-parse","HEAD").decode().strip() != BASE, "ISOLATED_BRANCH_NOT_PREPARED")
    require(git("merge-base","HEAD",BASE).decode().strip() == BASE,
            "BASE_ANCESTRY_DRIFT")
    disable_network()
    first = diagnostic()
    second = diagnostic()
    h1,h2 = sha(jbytes(first)),sha(jbytes(second))
    mismatches = int(first != second)
    require(mismatches == 0 and h1 == h2, "RUN_A_RUN_B_DETERMINISM_DRIFT")
    first["verdict"] = "ATTACK-EVENT EXECUTION UNIT A MEMBERSHIP SEMANTICS DIAGNOSTIC = PROVEN"
    first["base_commit"] = BASE
    first["branch"] = BRANCH
    first["actions_run_id"] = os.environ.get("GITHUB_RUN_ID")
    first["determinism"] = {
        "run_a_diagnostic_sha256":h1,
        "run_b_diagnostic_sha256":h2,
        "semantic_mismatches":mismatches
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(first,ensure_ascii=False,sort_keys=True,indent=2) + "\n"
    OUT.write_text(payload,encoding="utf-8")
    print("VERDICT="+first["verdict"])
    print("DIAGNOSTIC_CONCLUSION="+first["diagnostic_conclusion"])
    print("COUNTS="+json.dumps(first["counts"],sort_keys=True))
    print("MISMATCH_EXCLUSIVE_BASIS="+json.dumps(first["mismatch_taxonomy"]["exclusive_relation_basis"],sort_keys=True))
    print("MISMATCH_MATCHING_OUTCOME="+json.dumps(first["mismatch_taxonomy"]["by_matching_outcome"],sort_keys=True))
    print("MISMATCH_TEMPORAL_CODES="+json.dumps(first["mismatch_taxonomy"]["by_temporal_binding_code"],sort_keys=True))
    print("MISMATCH_A3_VERDICT="+json.dumps(first["mismatch_taxonomy"]["by_frozen_a3_episode_verdict"],sort_keys=True))
    print("EFFECTS="+json.dumps(first["effects"],sort_keys=True))
    print("QA_IMPACT="+json.dumps(first["qa_impact"],sort_keys=True))
    print("COUNTERFACTUAL="+json.dumps(first["diagnostic_counterfactual"],sort_keys=True))
    print("IDENTITY_IMPACT="+json.dumps(first["classification_identity_impact"],sort_keys=True))
    print("RUN_A_DIAGNOSTIC_SHA256="+h1)
    print("RUN_B_DIAGNOSTIC_SHA256="+h2)
    print("SEMANTIC_MISMATCHES="+str(mismatches))
    print("CLASSIFIER_EXECUTIONS=0 COMPOSITION_EXECUTIONS=0 NEON_QUERIES=0 DB_CONNECTIONS=0 DB_WRITES=0")
    print("ARTIFACT_SHA256="+sha(payload.encode("utf-8")))


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("UNIT_A_MEMBERSHIP_DIAGNOSTIC_BLOCKED="+type(exc).__name__+":"+str(exc),file=sys.stderr)
        raise
