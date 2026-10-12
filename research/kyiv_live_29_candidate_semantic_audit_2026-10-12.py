#!/usr/bin/env python3
"""Git-only, field-aware historical semantic ledger. Does not import or execute classifier."""
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PIN = "92d57bbbfad60e6c09bb92372b1e84f38fa6ced4"
CUTOFF = "2026-10-07T19:05:00Z"
FINISHED = "2026-10-11T05:56:28.255150Z"
PREFIX = "kyiv-air-alerts-grafana/data/"
OBJECTS = {
    "state": ("explosion_candidate_monitor_state.json", "b255f516a8598bbd28faaa1a651249f4064b5620", "439fdc640603210a8aa1ffb72543b2837cc729a5618b809ede82b18b8b632a8c", 4100971),
    "queue": ("explosion_review_queue.json", "e7777b88bf1912572df10eb252f991ea6456feba", "48db2aef4daab57a14fae3c533d1c0c2b6a5d81f0790fb09a86bc749e4de3573", 54234970),
    "run": ("explosion_candidate_monitor_last_run.json", "19d27d7b72afb52a235e6dfc0914f5aee7082ce2", "b1e0fa30a72d72a29dfc02db0328351551878ad53a4004a201a9a653bed0e074", 184821),
}
MONITOR = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER = "kyiv-air-alerts-grafana/scripts/authoritative_classifier_71cb6f6f.py"
EXPECTED_MONITOR_BLOB = "95e0eb313c6c68016601f681ab5186bf147d6dd1"
EXPECTED_CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
TYPES = (
    "EXPLICIT_CLASSIFIER_STORED_BINDING",
    "STORED_MATCHED_EPISODE",
    "STORED_MATCHED_EPISODES",
    "DISCOVERY_TRIGGER_ONLY",
    "UNSUPPORTED_OR_AMBIGUOUS_REFERENCE",
    "CONFLICTING_EXPLICIT_BINDINGS",
)
OUTPUT = Path(os.environ.get("KYIV_SEMANTIC_OUT", "research/kyiv_live_29_semantic_outputs"))
OLD = {"original_candidates": 4442, "related_candidates": 417, "candidate_episode_links": 6846, "unresolved_candidates": 413}

def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def iso(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")

def verify_source_file(path, expected):
    actual = git("rev-parse", PIN + ":" + path).decode().strip()
    assert actual == expected, ("frozen-code-identity", path, actual)
    return {"path": path, "git_blob": actual,
            "sha256": hashlib.sha256(git("cat-file", "blob", actual)).hexdigest()}

def load_objects():
    assert git("rev-parse", PIN + "^{commit}").decode().strip() == PIN
    inputs = {}
    proof = {}
    for name, (filename, expected_git, expected_sha256, expected_size) in OBJECTS.items():
        oid = git("rev-parse", PIN + ":" + PREFIX + filename).decode().strip()
        assert oid == expected_git, ("wrong-source-object", name, oid)
        payload = git("cat-file", "blob", oid)
        sha = hashlib.sha256(payload).hexdigest()
        githash = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        assert sha == expected_sha256 and len(payload) == expected_size and oid == githash
        inputs[name] = json.loads(payload)
        proof[name] = {"path": PREFIX + filename, "git_blob": oid,
                       "sha256": sha, "bytes": len(payload)}
    assert isinstance(inputs["queue"], list)
    assert isinstance(inputs["state"], dict)
    return inputs, proof

def walk_ids(obj, idset, path="$"):
    """Find all exact cohort IDs in every original JSON leaf, including unexpected paths."""
    if isinstance(obj, dict):
        for key in sorted(obj):
            yield from walk_ids(obj[key], idset, path + "." + key)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from walk_ids(value, idset, path + "[" + str(i) + "]")
    elif isinstance(obj, str) and obj in idset:
        yield (path, obj)

def category(path):
    if path == "$.classification_evidence.classification_episode_id":
        return TYPES[0]
    if path.startswith("$.composition_provenance.") and path == "$.composition_provenance.target_episode_id":
        return TYPES[0]
    if path == "$.classification_evidence.episode_level_composition.target_episode_id":
        return TYPES[0]
    if path == "$.matched_episode_id" or path.endswith(".candidate_matching.matched_episode_id"):
        return TYPES[1]
    if path.startswith("$.matched_episode_ids[") or path.startswith("$.matching_logical_episode_groups["):
        return TYPES[2]
    if ".candidate_matching.matched_episode_ids[" in path:
        return TYPES[2]
    if path.startswith("$.trigger_episode_ids["):
        return TYPES[3]
    return TYPES[4]

def field_root(path):
    if path.startswith("$."):
        return path[2:].split(".", 1)[0].split("[", 1)[0]
    return "UNKNOWN"

def normalized_decision(value):
    if not isinstance(value, dict):
        return None
    for k in ("decision", "disposition", "action", "outcome", "review_decision"):
        v = value.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    return None

def review_info(c):
    disposition = c.get("review_disposition")
    history = c.get("review_history")
    human = c.get("review_provenance")
    explicit = []
    if isinstance(disposition, dict):
        decision = normalized_decision(disposition)
        if decision:
            explicit.append({"path": "$.review_disposition", "decision": decision})
    if isinstance(history, list):
        for i, row in enumerate(history):
            if isinstance(row, dict):
                decision = normalized_decision(row)
                if decision:
                    explicit.append({"path": "$.review_history[" + str(i) + "]",
                                     "decision": decision})
    approved = {"APPROVE", "APPROVED", "PROMOTE", "PROMOTED", "ACCEPT", "ACCEPTED", "CONFIRMED"}
    held = {"HOLD", "HELD", "NEEDS_REVIEW", "DEFER", "DEFERRED", "PENDING"}
    rejected = {"REJECT", "REJECTED", "DISMISS", "DISMISSED"}
    vals = [x["decision"] for x in explicit]
    if not vals:
        label = "NO_EXPLICIT_REVIEW_DECISION"
    elif vals[-1] in approved:
        label = "REVIEW_APPROVED"
    elif vals[-1] in held:
        label = "REVIEW_HELD"
    elif vals[-1] in rejected:
        label = "REVIEW_REJECTED"
    else:
        label = "REVIEW_DECISION_UNSUPPORTED"
    temporal = human.get("temporal") if isinstance(human, dict) else None
    validated_temporal = isinstance(temporal, dict) and temporal.get("validated_by_review") is True
    return {
        "disposition": disposition if disposition is not None else "NOT_OBSERVABLE",
        "history": history if history is not None else "NOT_OBSERVABLE",
        "review_provenance": human if human is not None else "NOT_OBSERVABLE",
        "explicit_decisions": explicit,
        "review_verdict": label,
        "reviewed_temporal_validated": validated_temporal,
        "review_provenance_present": isinstance(human, dict),
        "explicit_review_approval": label == "REVIEW_APPROVED",
        "explicit_review_hold": label == "REVIEW_HELD",
        "explicit_review_rejection": label == "REVIEW_REJECTED",
    }

def conflicts_for(c, refs, epids):
    """Only compare bindings that actually purport to be a final classifier target."""
    classifier_values = sorted(set(x["episode_id"] for x in refs
        if x["evidence_type"] == TYPES[0]))
    cls = (c.get("classification_evidence") or {})
    if not isinstance(cls, dict):
        cls = {}
    raw_classifier = cls.get("classification_episode_id")
    composition = c.get("composition_provenance")
    comp = composition.get("target_episode_id") if isinstance(composition, dict) else None
    nested_comp = cls.get("episode_level_composition")
    nested_target = nested_comp.get("target_episode_id") if isinstance(nested_comp, dict) else None
    final_target_values = sorted(set(str(v) for v in (raw_classifier, comp, nested_target) if isinstance(v, str) and v))
    status = str(c.get("status") or "")
    matched = c.get("matched_episode_id")
    violations = []
    if len(final_target_values) > 1:
        violations.append({"kind": "CONFLICTING_CLASSIFIER_FINAL_TARGETS",
                           "targets": final_target_values,
                           "paths": ["$.classification_evidence.classification_episode_id",
                                     "$.composition_provenance.target_episode_id",
                                     "$.classification_evidence.episode_level_composition.target_episode_id"]})
    if status in ("approved_strict", "approved_sensitivity") and final_target_values and matched:
        if str(matched) not in final_target_values:
            violations.append({"kind": "POSITIVE_STATUS_MATCHED_ID_DIFFERS_FROM_CLASSIFIER_TARGET",
                               "classifier_targets": final_target_values,
                               "matched_episode_id": matched})
    human = c.get("review_provenance")
    adapter = cls.get("review_provenance_adapter")
    if isinstance(human, dict) and isinstance(adapter, dict) and adapter.get("usable") is True:
        target = human.get("target_episode_id")
        if final_target_values and target and str(target) not in final_target_values:
            violations.append({"kind": "USABLE_REVIEW_TARGET_DIFFERS_FROM_CLASSIFIER_TARGET",
                               "review_target": target, "classifier_targets": final_target_values})
    # A publication-window match can differ from an event-time classifier target.
    # Never flag mere differences between temporal sets and classifier binding.
    return violations

def main():
    data, sources = load_objects()
    code = [verify_source_file(MONITOR, EXPECTED_MONITOR_BLOB),
            verify_source_file(CLASSIFIER, EXPECTED_CLASSIFIER_BLOB)]
    episodes = sorted((e for e in data["state"]["cities"]["kyiv"]["episodes"]
                       if iso(e["alert_end"]) >= iso(CUTOFF)),
                       key=lambda x: (x["alert_start"], x["episode_id"]))
    assert len(episodes) == 29
    episode_ids = {e["episode_id"] for e in episodes}
    assert len(episode_ids) == 29
    assert all(e.get("city_key") == "kyiv" and e.get("alert_source") == "kyiv_combined_exact_city" for e in episodes)

    contract = {
        "scope": "GIT_ONLY_FROZEN_SEMANTICS_NOT_PHYSICAL_ATTACK_ACCEPTANCE",
        "frozen_snapshot_commit": PIN, "frozen_snapshot_finished_at": FINISHED,
        "live_cutoff": CUTOFF, "immutable_original_git_objects": sources,
        "producer_code": code, "classifier_authority": "production-live pinned 71cb6f6f, NOT later development 9784473e",
        "references": [
            {"path": MONITOR, "lines": "3221-3290", "meaning": "Discovery due check identities are unioned into trigger_episode_ids; repeat discovery adds triggers."},
            {"path": CLASSIFIER, "lines": "1520-1610", "meaning": "Publication-time matching estimates candidate alert windows, not event occurrence."},
            {"path": CLASSIFIER, "lines": "2172-2395", "meaning": "Classification outcome and separate episode-specific event binding are generated from evidence."},
            {"path": MONITOR, "lines": "3140-3210", "meaning": "Episode composition can change anchor status and matched_episode_id; composition provenance must be assessed separately."},
            {"path": MONITOR, "lines": "5025-5200", "meaning": "Checked-at is updated when city due-work is attempted; last-run report records city searches, not full per-source retrieval logs."}
        ],
        "field_semantics": {
            "trigger_episode_ids": "DISCOVERY_ONLY: all due episodes causing a city search / repeat encounter; not source confirmation",
            "matched_episode_id": "STORED_TEMPORAL_SINGLETON, except may be overridden to classified episode target on approved status or composed strict; never human approval by itself",
            "matched_episode_ids": "PUBLICATION_WINDOW_MATCH_CANDIDATE_SET, may include multiple episodes, not confirmed events",
            "matching_logical_episode_groups": "Grouping of source representations within temporal match candidates",
            "matching_outcome": "unique_match / ambiguous_match / no_match for publication-window grouping, independent of event confirmation",
            "classification_evidence.classification_episode_id": "Stored classifier proposed event-episode target, only meaningful with candidate verdict and evidence",
            "classification_evidence.temporal_binding": "Supporting temporal evidence, not automatically a final binding",
            "classification_evidence.candidate_evidence": "Evidence component decisions and support references; do not promote inferred support IDs to approved links",
            "candidate_matching": "Not a known root producer field here; if present, record exact nested paths as temporal matching evidence only",
            "classification_reason_codes": "Diagnostic classifier reasons, not human-review acceptance",
            "review_disposition": "Explicit human review decision only if structured decision exists; absence is NOT_OBSERVABLE",
            "review_history": "Historical review decisions only when explicitly stored",
            "review_provenance": "Reviewed evidence adapter; validation of a temporal fact is distinct from a final approved candidate",
            "status": "Classifier or composition status can be automatic; not proof of human approval",
            "review_note": "Explanatory often auto-generated text; never counted as human approval"
        },
        "categories": list(TYPES),
        "precedence": "NONE_IMPOSED: retain independent stored field semantics and overlap",
        "conflict_policy": "Flag contradictory final classifier/approved-target assertions; publication-window versus event-time differences alone are NOT conflicts",
        "unavailable": "Original source observations for earlier checked_at times may not survive in last-run state; no retrospective retrieval performed",
        "db_queries": 0, "db_writes": 0, "classifier_executions": 0, "source_fetches": 0
    }

    all_refs = []
    by_candidate = {}
    by_episode = defaultdict(list)
    candidate_records = []
    semantic_conflicts = []
    row_id_counts = Counter()
    all_paths = Counter()
    for index, row in enumerate(data["queue"]):
        assert isinstance(row, dict), ("unexpected-queue-entry", index)
        candidate_id = row.get("candidate_id") or "MISSING_ID_ROW_" + str(index)
        row_id_counts[candidate_id] += 1
        raw_refs = [(p, eid, category(p)) for p, eid in walk_ids(row, episode_ids)]
        if not raw_refs:
            continue
        review = review_info(row)
        row_hash = digest(row)
        typed = Counter(t for _, _, t in raw_refs)
        ep_refs = sorted({e for _, e, _ in raw_refs})
        record = {
            "candidate_id": candidate_id, "observation_id": row.get("observation_id") or "NOT_OBSERVABLE",
            "queue_index": index, "original_row_sha256_canonical_json": row_hash,
            "original_queue_git_blob": sources["queue"]["git_blob"],
            "city_key": row.get("city_key"), "status": row.get("status"),
            "matching_outcome": row.get("matching_outcome", "NOT_OBSERVABLE"),
            "matching_reason": row.get("matching_reason", "NOT_OBSERVABLE"),
            "matching_logical_episode_groups": row.get("matching_logical_episode_groups", "NOT_OBSERVABLE"),
            "classification_reason_codes": row.get("classification_reason_codes", "NOT_OBSERVABLE"),
            "classification_evidence_sha256": digest(row.get("classification_evidence")) if row.get("classification_evidence") is not None else "NOT_OBSERVABLE",
            "classification_episode_id": (row.get("classification_evidence") or {}).get("classification_episode_id") if isinstance(row.get("classification_evidence"), dict) else None,
            "matched_episode_id": row.get("matched_episode_id"),
            "matched_episode_ids": row.get("matched_episode_ids", "NOT_OBSERVABLE"),
            "trigger_episode_ids": row.get("trigger_episode_ids", "NOT_OBSERVABLE"),
            "source": row.get("source"), "publisher": row.get("publisher"),
            "publisher_url": row.get("publisher_url"), "source_url": row.get("url"),
            "resolved_url": row.get("resolved_url"), "published_at": row.get("published_at"),
            "first_discovered_at": row.get("first_discovered_at"),
            "last_seen_at": row.get("last_seen_at"), "review_note": row.get("review_note", "NOT_OBSERVABLE"),
            "review": review, "relation_types": dict(sorted(typed.items())),
            "related_episode_ids": ep_refs,
        }
        candidate_records.append(record)
        by_candidate[candidate_id] = record
        conflicts = conflicts_for(row, [{"episode_id": e, "evidence_type": t} for _, e, t in raw_refs], episode_ids)
        for violation in conflicts:
            semantic_conflicts.append({
                "candidate_id": candidate_id, "queue_index": index, "row_sha256": row_hash,
                "violation": violation, "original_queue_git_blob": sources["queue"]["git_blob"]
            })
        for field_path, episode_id, typ in raw_refs:
            all_paths[field_root(field_path)] += 1
            relation = {
                "candidate_id": candidate_id, "observation_id": record["observation_id"],
                "queue_index": index, "original_row_sha256_canonical_json": row_hash,
                "original_queue_git_blob": sources["queue"]["git_blob"],
                "episode_id": episode_id,
                "episode_start": next(x["alert_start"] for x in episodes if x["episode_id"] == episode_id),
                "episode_end": next(x["alert_end"] for x in episodes if x["episode_id"] == episode_id),
                "city_key": row.get("city_key"), "field_path": field_path,
                "field_root": field_root(field_path),
                "original_stored_value": episode_id,
                "evidence_type": typ, "status": row.get("status"),
                "matching_outcome": row.get("matching_outcome", "NOT_OBSERVABLE"),
                "review_verdict": review["review_verdict"],
                "review_provenance_sha256": digest(review),
                "classification_evidence_sha256": record["classification_evidence_sha256"],
                "source": row.get("source"), "publisher": row.get("publisher"),
                "source_url": row.get("url"),
                "conflict_ids": [x["kind"] for x in conflicts],
            }
            all_refs.append(relation)
            by_episode[episode_id].append(relation)

    assert len(candidate_records) == len(by_candidate), "nonunique-related-candidate-id"
    all_refs.sort(key=lambda x: (x["queue_index"], x["field_path"], x["episode_id"]))
    candidate_records.sort(key=lambda x: (x["queue_index"], x["candidate_id"]))
    semantic_conflicts.sort(key=lambda x: (x["queue_index"], x["violation"]["kind"]))
    pairs = {(r["candidate_id"], r["episode_id"]) for r in all_refs}
    explicit_types = {TYPES[0], TYPES[1], TYPES[2]}
    explicit_candidates = {r["candidate_id"] for r in all_refs if r["evidence_type"] in explicit_types}
    trigger_candidates = {r["candidate_id"] for r in all_refs if r["evidence_type"] == TYPES[3]}
    only_trigger = {r["candidate_id"] for r in all_refs if all(
        x["evidence_type"] == TYPES[3] for x in all_refs if x["candidate_id"] == r["candidate_id"])}
    # Also retain an independent count of final classifier targets versus merely temporal bindings.
    classifier_candidates = {r["candidate_id"] for r in all_refs if r["evidence_type"] == TYPES[0]}
    conflict_candidates = {x["candidate_id"] for x in semantic_conflicts}
    review_counter = Counter(x["review"]["review_verdict"] for x in candidate_records)
    by_type = Counter(r["evidence_type"] for r in all_refs)
    by_root = Counter(r["field_root"] for r in all_refs)
    paths = Counter(r["field_path"].split("[", 1)[0] for r in all_refs)
    # Precisely reconstruct the previous implementation, without assuming it was authoritative.
    old_refs = []
    for row in data["queue"]:
        trigger = row.get("trigger_episode_ids") or []
        if not isinstance(trigger, list):
            trigger = [trigger] if isinstance(trigger, str) else []
        matched = row.get("matched_episode_id")
        refs = sorted({x for x in trigger + ([matched] if isinstance(matched, str) else []) if x in episode_ids})
        if not refs:
            continue
        disposition = ("EXACT_MATCHED" if matched in refs and len(refs) == 1 else
                       "AMBIGUOUS" if len(refs) > 1 else "TRIGGER_ONLY")
        old_refs.append({"candidate_id": row.get("candidate_id"), "refs": refs, "disposition": disposition})
    old_computed = {
        "original_candidates": len(data["queue"]),
        "related_candidates": len(old_refs),
        "candidate_episode_links": sum(len(x["refs"]) for x in old_refs),
        "unresolved_candidates": sum(x["disposition"] != "EXACT_MATCHED" for x in old_refs)
    }

    report = data["run"]
    city_search = (report.get("searches") or {}).get("kyiv")
    city_search_recorded = isinstance(city_search, dict) and "kyiv" in (report.get("cities_searched") or [])
    search_metadata = city_search if city_search_recorded else "NOT_OBSERVABLE"
    followup_rows = []
    summary_rows = []
    for ep in episodes:
        due = checked = search_recorded = 0
        erefs = by_episode.get(ep["episode_id"], [])
        for j, check in enumerate(ep["checks"]):
            is_due = iso(check["due_at"]) <= iso(FINISHED)
            was_checked = bool(check.get("checked_at"))
            due += is_due
            checked += was_checked
            linked_to_last_run = (
                city_search_recorded and was_checked
                and check.get("checked_at") == report.get("followup_cutoff_at")
            )
            search_recorded += bool(linked_to_last_run and (
                city_search.get("query_url") or city_search.get("query_urls")
                or city_search.get("google_error") is not None
            ))
            followup_rows.append({
                "episode_id": ep["episode_id"], "check_index": j,
                "check_label": check.get("label"), "due_at": check.get("due_at"),
                "checked_at": check.get("checked_at") or "NOT_OBSERVABLE",
                "new_candidates": check.get("new_candidates", "NOT_OBSERVABLE"),
                "due_at_frozen": is_due, "marked_completed": was_checked,
                "last_run_city_search_temporally_correlated": bool(linked_to_last_run),
                "specific_search_execution_evidence": (
                    "CITY_LEVEL_SEARCH_RECORD_FOR_THIS_RUN"
                    if linked_to_last_run and search_recorded else "NOT_OBSERVABLE"
                ),
                "required_source_coverage": "NOT_OBSERVABLE" if is_due else "NOT_DUE",
                "missing_or_unverifiable_coverage": is_due,
                "proven_all_sources": False,
            })
        typ = Counter(x["evidence_type"] for x in erefs)
        distinct = {r["candidate_id"] for r in erefs}
        explicit = {r["candidate_id"] for r in erefs if r["evidence_type"] in explicit_types}
        cls = {r["candidate_id"] for r in erefs if r["evidence_type"] == TYPES[0]}
        rev = {c for c in distinct if by_candidate[c]["review"]["explicit_review_approval"]}
        holds = {c for c in distinct if by_candidate[c]["review"]["explicit_review_hold"]}
        summary_rows.append({
            "episode_id": ep["episode_id"], "city_key": ep["city_key"],
            "alert_start": ep["alert_start"], "alert_end": ep["alert_end"],
            "alert_source": ep["alert_source"],
            "unique_candidates_any": len(distinct),
            "unique_candidates_with_stored_match_or_classifier": len(explicit),
            "unique_candidates_with_final_classifier_binding": len(cls),
            "distinct_candidate_episode_pairs": len(distinct),
            "raw_references": len(erefs),
            "by_evidence_type": {k: typ.get(k, 0) for k in TYPES},
            "review_approved_candidates": len(rev),
            "review_hold_candidates": len(holds),
            "conflicting_candidates": len(conflict_candidates.intersection(distinct)),
            "followups_scheduled": len(ep["checks"]), "followups_due": due,
            "followups_marked_checked": checked,
            "followups_with_correlated_city_search_record": search_recorded,
            "all_required_source_coverage": "NOT_OBSERVABLE",
        })
    assert sum(r["followups_scheduled"] for r in summary_rows) == 116
    assert sum(r["followups_marked_checked"] for r in summary_rows) == 55
    assert sum(r["followups_due"] for r in summary_rows) == 55
    count = {
        "original_candidate_records": len(data["queue"]),
        "candidate_rows_with_any_cohort_reference": len(candidate_records),
        "candidate_rows_with_explicit_stored_relationship": len(explicit_candidates),
        "candidate_rows_with_final_classifier_binding": len(classifier_candidates),
        "candidate_rows_trigger_references_only": len(only_trigger),
        "candidate_rows_with_conflicting_final_bindings": len(conflict_candidates),
        "candidate_rows_review_approved": review_counter["REVIEW_APPROVED"],
        "candidate_rows_review_held": review_counter["REVIEW_HELD"],
        "candidate_rows_review_rejected": review_counter["REVIEW_REJECTED"],
        "candidate_rows_review_unresolved_or_not_observable": sum(
            v for k,v in review_counter.items() if k not in ("REVIEW_APPROVED","REVIEW_HELD","REVIEW_REJECTED")),
        "candidate_rows_with_validated_review_temporal_evidence": sum(
            x["review"]["reviewed_temporal_validated"] for x in candidate_records),
        "candidate_rows_status_needs_review_not_human_hold": sum(
            x["status"] == "needs_review" and not x["review"]["explicit_review_hold"] for x in candidate_records),
        "raw_references_all_fields": len(all_refs),
        "raw_references_by_type": {t: by_type[t] for t in TYPES},
        "raw_references_by_top_level_root": dict(sorted(by_root.items())),
        "raw_references_by_field_path_pre_index": dict(sorted(paths.items())),
        "distinct_candidate_episode_pairs_any": len(pairs),
        "distinct_candidate_episode_pairs_explicit": len({(x["candidate_id"], x["episode_id"]) for x in all_refs if x["evidence_type"] in explicit_types}),
        "episodes_without_explicit_stored_candidate_binding": [x["episode_id"] for x in summary_rows if not x["unique_candidates_with_stored_match_or_classifier"]],
        "episodes_without_final_classifier_binding": [x["episode_id"] for x in summary_rows if not x["unique_candidates_with_final_classifier_binding"]],
        "unique_related_candidate_ids": len(by_candidate),
        "duplicate_candidate_ids_across_original_queue": {k:v for k,v in row_id_counts.items() if v>1},
        "city_key_mismatch_candidates": [x["candidate_id"] for x in candidate_records if x["city_key"] != "kyiv"],
    }
    recon = {
        "previous_provisional_reported": OLD,
        "previous_algorithm_independently_reproduced": old_computed,
        "previous_counts_reproduced": old_computed == OLD,
        "corrected": count,
        "interpretation": {
            "old_417": "Old algorithm selected only candidates whose top-level triggers or matched_episode_id referred to cohort; revised census scans all stored fields.",
            "old_6846": "Old count was distinct per-candidate episode IDs, not physical events, independent sources, or raw field occurrences.",
            "old_413": "Old unresolved definition treated any candidate with multiple trigger episode IDs as AMBIGUOUS regardless of explicit classified episode evidence. Not a semantic conflict count.",
            "new_count_differences": "Use corrected by-field counts, raw occurrences, and unique pairs. Candidate bindings and trigger context are separate overlapping sets.",
            "no_forced_agreement": True,
        }
    }
    contract["original_queue_field_population"] = {
        "field_roots_containing_cohort_ids": dict(sorted(all_paths.items())),
        "candidate_population": len(candidate_records),
        "review_decision_population": dict(sorted(review_counter.items()))
    }
    summary_coverage = {
        "frozen_last_run": {
            "started_at": report.get("started_at"), "finished_at": report.get("finished_at"),
            "followup_cutoff_at": report.get("followup_cutoff_at"),
            "kyiv_present_in_cities_searched": city_search_recorded,
            "kyiv_search_metadata": search_metadata,
            "errors": report.get("errors") or {},
            "report_only_latest_run": True,
        },
        "counts": {
            "scheduled": sum(e["followups_scheduled"] for e in summary_rows),
            "due": sum(e["followups_due"] for e in summary_rows),
            "checked": sum(e["followups_marked_checked"] for e in summary_rows),
            "last_run_city_search_record_correlated": sum(e["followups_with_correlated_city_search_record"] for e in summary_rows),
            "full_required_source_coverage_proven": 0,
            "coverage_not_observable_at_due": sum(e["followups_due"] for e in summary_rows),
        },
        "checking_rules": "City-level last-run report proves at most a correlated city-search invocation for exact checked_at; it is not per-query/per-source completeness or proof for previous runs.",
        "checks": followup_rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dump(OUTPUT / "01_source_contract.json", contract)
    dump(OUTPUT / "02_candidate_binding_ledger.json", all_refs)
    dump(OUTPUT / "03_candidate_dispositions.json", candidate_records)
    dump(OUTPUT / "04_kyiv_29_episodes.json", summary_rows)
    csv_path = OUTPUT / "05_kyiv_29_episodes.csv"
    cols = ("episode_id","alert_start","alert_end","unique_candidates_any",
            "unique_candidates_with_stored_match_or_classifier","unique_candidates_with_final_classifier_binding",
            "raw_references","review_approved_candidates","review_hold_candidates",
            "conflicting_candidates","followups_scheduled","followups_due",
            "followups_marked_checked","followups_with_correlated_city_search_record",
            "all_required_source_coverage")
    with csv_path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=cols,lineterminator="\n")
        writer.writeheader()
        for s in summary_rows:
            writer.writerow({k:s[k] for k in cols})
    dump(OUTPUT / "06_followup_coverage.json", summary_coverage)
    dump(OUTPUT / "07_semantic_conflicts.json", {
        "conflicting_final_binding_candidates": len(conflict_candidates),
        "conflicts": semantic_conflicts,
        "nonbinding_unsupported_raw_references": by_type[TYPES[4]],
        "unsupported_reference_note": "Nested supporting episode IDs do not establish final event binding; raw paths remain available in ledger.",
        "not_a_conflict": "Multiple triggers or difference between publication-window set and event-time binding."
    })
    dump(OUTPUT / "08_count_reconciliation.json", recon)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUTPUT.iterdir())}
    print("SEMANTIC_COUNTS",json.dumps(count,sort_keys=True,ensure_ascii=False))
    print("OLD_ALGORITHM",json.dumps(old_computed,sort_keys=True))
    print("FOLLOWUP_COUNTS",json.dumps(summary_coverage["counts"],sort_keys=True))
    print("SEMANTIC_OUTPUT_SHA256",json.dumps(hashes,sort_keys=True))
    print("SEMANTIC_CSV_29_ROWS_BEGIN")
    print(csv_path.read_text(encoding="utf-8").strip())
    print("SEMANTIC_CSV_29_ROWS_END")

if __name__ == "__main__":
    main()
