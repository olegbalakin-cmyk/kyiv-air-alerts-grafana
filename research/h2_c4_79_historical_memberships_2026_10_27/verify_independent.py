#!/usr/bin/env python3
"""Independent, offline-only H2 C4 79-link historical authority verification.

Uses immutable Git objects; no HTTP, database connection or classifier.
Fails closed on any unproven status promotion or source/identity mismatch.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "registry.json"
ACCEPTED_PROOF_COMMIT = "c23387942a6b3effafa612195582b1e56afe618f"
ACCEPTED_PROOF_PATH = "research/neon_h2_19542_field_authority_containment_revalidation_2026-10-12.json"
ACCEPTED_PROOF_BLOB = "2abd72d10bdac896d3c4ed10c582c38aafb162af"
ACCEPTED_PROOF_SHA256 = "c3827de8c0574c0305e5da1efe619da678faaa2e8a201150ac8fe5fa7f57bd8c"
UTC = dt.timezone.utc
ISO_AWARE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)")
EXPECTED_REASONS = {
    "UNIQUE_EXACT_ORIGINAL_ALERT_START",
    "UNIQUE_CONTAINMENT_ALL_EXPLICIT_EVENT_TIMES",
    "SOURCE_SPECIFIC_TIMEZONE_CONTRACT_MISSING",
    "EXACT_UNIQUE_ORIGINAL_EVENT_OR_ALERT_CLOCK_UNAVAILABLE",
    "SPLIT_EVENT_CLOCK_REQUIRES_UNPROVEN_HISTORICAL_TIME_INTERPRETATION",
    "EXPLICIT_CLOCK_NOT_EQUAL_TO_CANONICAL_ALERT_BOUNDARY",
}
ALLOWED_STATUSES = {
    "REPLAY_DERIVED_ONLY",
    "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT",
}


class EvidenceError(Exception):
    pass


def ensure(test, message):
    if not test:
        raise EvidenceError(message)


def git(*arguments):
    out = subprocess.run(["git", *arguments], check=True, capture_output=True)
    return out.stdout


def show(commit, path):
    return git("show", commit + ":" + path)


def blob_at(commit, path):
    return git("rev-parse", commit + ":" + path).decode().strip()


def hexsha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def moment(string):
    ensure(isinstance(string, str) and ISO_AWARE.fullmatch(string) is not None,
           "A supposedly exact instant lacks an explicit UTC offset: " + str(string))
    return dt.datetime.fromisoformat(string.replace("Z", "+00:00")).astimezone(UTC)


def readable_git_json(commit, path, blob_sha=None, digest=None):
    raw = show(commit, path)
    if blob_sha is not None:
        ensure(blob_at(commit, path) == blob_sha, "Git blob mismatch: " + commit + ":" + path)
    if digest is not None:
        ensure(hexsha(raw) == digest, "Raw SHA256 mismatch: " + commit + ":" + path)
    return json.loads(raw)


def load_immutable_sources(registry):
    proof = readable_git_json(ACCEPTED_PROOF_COMMIT, ACCEPTED_PROOF_PATH,
                              ACCEPTED_PROOF_BLOB, ACCEPTED_PROOF_SHA256)
    ensure(registry["source_of_population"]["git_blob"] == ACCEPTED_PROOF_BLOB,
           "Proof blob changed")
    ensure(registry["source_of_population"]["sha256"] == ACCEPTED_PROOF_SHA256,
           "Proof digest changed")
    ensure(registry["source_of_population"]["commit"] == ACCEPTED_PROOF_COMMIT,
           "Proof commit changed")
    ensure(registry["source_of_population"]["path"] == ACCEPTED_PROOF_PATH,
           "Proof path changed")
    originals = {}
    source_index = {x["city"]: x for x in proof["immutable_inputs"]["original_city_worker_evidence"]}
    for city, pin in registry["governing_source_files"].items():
        ensure(city in source_index, "City not in accepted proof")
        accepted = source_index[city]
        ensure(pin["commit"] == accepted["tested_head"], "Original city tested HEAD mismatch: " + city)
        ensure(pin["blob_sha"] == accepted["original_evidence_blob"], "City source blob mismatch: " + city)
        ensure(pin["path"] == accepted["original_evidence_path"], "City source path mismatch: " + city)
        ensure(pin["sha256"] == accepted["original_evidence_sha256"], "City source digest mismatch: " + city)
        originals[city] = readable_git_json(pin["commit"], pin["path"],
                                            pin["blob_sha"], pin["sha256"])
        ensure(originals[city]["city_key"] == city, "Wrong historical city source")
    episodes = {}
    for city, manifest in registry["historical_city_episodes"].items():
        ensure(city in originals, "Unrelated chronology city")
        ep = {}
        count = 0
        for part in manifest["source_slices"]:
            src = readable_git_json(manifest["commit"], part["path"],
                                    part["blob_sha"], part["sha256"])
            ensure(src["city_key"] == city, "Wrong city in original source slice")
            ensure(src["episode_count"] == len(src["episodes"]) == part["episodes"],
                   "Unexpected original episode slice count")
            for e in src["episodes"]:
                ensure(e["episode_id"] not in ep, "Duplicate immutable historical episode")
                ensure(moment(e["alert_start"]) < moment(e["alert_end"]), "Invalid original interval")
                ep[e["episode_id"]] = (moment(e["alert_start"]), moment(e["alert_end"]))
            count += len(src["episodes"])
        ensure(count == manifest["episodes"], "Original city chronology count mismatch: " + city)
        episodes[city] = ep
    ensure(set(originals) == set(episodes) ==
           {r["city"] for r in registry["records"]}, "Unexpected city source set")
    return proof, originals, episodes


def key_of_original(x):
    return (x["city"], x["bucket"], x["observation_id"],
            x["exported_historical_episode_id"], x["original_record_sha256"],
            x["original_row_index"], x["original_evidence_blob"])


def key_of_reg(x):
    return (x["city"], x["bucket"], x["observation_id"],
            x["exported_historical_episode_id"], x["original_git"]["row_sha256"],
            x["original_git"]["row_index"], x["original_git"]["blob_sha"])


def explicit_instants(fields):
    return [moment(x) for value in fields.values() if isinstance(value, str)
            for x in ISO_AWARE.findall(value)]


def validate(registry, proof, originals, episodes):
    rows = registry["records"]
    accepted = proof["unresolved_bound_source_memberships"]
    ensure(len(rows) == len(accepted) == 79, "Population is not exactly 79")
    ensure(len({x["source_link_key"] for x in rows}) == 79, "Duplicate source-link identity")
    ensure(len({x["source_link_key"] for x in accepted}) == 79, "Accepted identity duplicates")
    ensure({x["source_link_key"] for x in accepted} ==
           {x["source_link_key"] for x in rows}, "Added/dropped original source-link identity")

    full = [x for x in proof["full_membership_regression"]
            if x["corrected_authority"] == "REPLAY_DERIVED_ONLY"]
    ensure(len(full) == 79, "Accepted full membership ledger disagrees")
    fidx = Counter((x["city"], x["bucket"], x["observation_id"],
                    x["exported_episode_id"], x["original_record_sha256"],
                    x["original_row_index"], x["original_source_blob"]) for x in full)
    ensure(fidx == Counter(key_of_reg(x) for x in rows),
           "Not a complete exact 79-subset of accepted 1,429-row audit")
    ensure(proof["membership_authority_totals"]["ORIGINAL_ACCEPTED"] == 286 and
           proof["membership_authority_totals"]["INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"] == 1064 and
           proof["membership_authority_totals"]["REPLAY_DERIVED_ONLY"] == 79,
           "Accepted original population categories unexpectedly differ")
    ensure(len(proof["full_membership_regression"]) == 1429, "Original 1429 count altered")

    accepted_by_link = {x["source_link_key"]: x for x in accepted}
    reasons = Counter()
    city = Counter()
    promoted = []
    timezone = Counter()
    exact_source_hashes = set()
    for r in rows:
        ident = r["source_link_key"]
        a = accepted_by_link[ident]
        ensure(r["accepted_before"] == a["authority"] == "REPLAY_DERIVED_ONLY",
               "Non-replay original entered audit: " + ident)
        ensure(r["classification_key"] == a["classification_key"] and
               r["observation_id"] == a["observation_id"] and
               r["parent_record_id"] == a["parent_record_id"] and
               r["exported_historical_episode_id"] == a["exported_historical_episode_id"] and
               key_of_reg(r) == key_of_original(a), "Changed accepted key or parent: " + ident)
        ensure(r["proposed_after"] in ALLOWED_STATUSES, "Unpermitted status")
        ensure(r["historical_rule"] in EXPECTED_REASONS, "Unknown or missing rule")
        orig_ref = r["original_git"]
        pin = registry["governing_source_files"][r["city"]]
        ensure(orig_ref["commit"] == a["tested_head"] == pin["commit"] and
               orig_ref["path"] == pin["path"] and
               orig_ref["blob_sha"] == pin["blob_sha"],
               "Historical source ref diverged: " + ident)
        src = originals[r["city"]]
        subset = src[r["bucket"]]
        ensure(0 <= orig_ref["row_index"] < len(subset), "Out of bounds original source row")
        source_row = subset[orig_ref["row_index"]]
        ensure(hexsha(canonical_json(source_row)) == orig_ref["row_sha256"],
               "Original source record SHA256 mismatch: " + ident)
        for field_name, val in dict(r["clock_fields"], **r["event_clock_fields"]).items():
            ensure(source_row.get(field_name) == val,
                   "Original source clock was rewritten: " + ident + "/" + field_name)
        exact_source_hashes.add((orig_ref["blob_sha"], orig_ref["row_index"]))

        target = r["exported_historical_episode_id"]
        city_ep = episodes[r["city"]]
        ensure(target in city_ep, "Target not found in immutable chronological source")
        expected = r["expected_original_target_interval"]
        ensure(city_ep[target] == (moment(expected["start"]), moment(expected["end"])),
               "Target UTC interval differs from frozen original chronological slices")

        aware_starts = explicit_instants(r["clock_fields"])
        aware_events = explicit_instants(r["event_clock_fields"])
        matching_starts = [eid for eid, (start, end) in city_ep.items()
                           if any(t == start for t in aware_starts)]
        per_event = [[eid for eid, (start, end) in city_ep.items() if start <= t < end]
                     for t in aware_events]
        unique_aware_start = len(aware_starts) == 1 and matching_starts == [target]
        unique_aware_events = bool(aware_events) and all(m == [target] for m in per_event)
        is_upgrade = r["proposed_after"] == "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"
        if is_upgrade:
            ensure(not r["source_specific_timezone_case"], "Naive-time promotion is forbidden")
            ensure(r["missing_evidence"] == [], "Promotion has an unresolved evidence requirement")
            if r["historical_rule"] == "UNIQUE_EXACT_ORIGINAL_ALERT_START":
                ensure(r["method"] == "EXACT_AWARE_ORIGINAL_ALERT_START" and unique_aware_start,
                       "Original aware clock does not uniquely bind target alert")
            elif r["historical_rule"] == "UNIQUE_CONTAINMENT_ALL_EXPLICIT_EVENT_TIMES":
                ensure(r["method"] == "EXACT_AWARE_EVENT_CLOCK_CONTAINMENT" and unique_aware_events and
                       len(aware_events) >= 2,
                       "Original event times not all uniquely inside target interval")
            else:
                raise EvidenceError("Attempted status promotion without an accepted rule")
            promoted.append(ident)
        else:
            ensure(r["historical_rule"] not in {
                   "UNIQUE_EXACT_ORIGINAL_ALERT_START",
                   "UNIQUE_CONTAINMENT_ALL_EXPLICIT_EVENT_TIMES"},
                   "Evidence-supported case arbitrarily left unresolved")
            ensure(bool(r["missing_evidence"]), "Missing individualized unresolved reason")
            ensure(r["method"] is None, "Unproven case carries a promoted method")
        if r["source_specific_timezone_case"]:
            timezone[r["city"]] += 1
            ensure(r["city"] in ("dnipro", "mykolaiv"), "Unexpected city with timezone block")
            ensure(r["historical_rule"] == "SOURCE_SPECIFIC_TIMEZONE_CONTRACT_MISSING" and
                   r["source_timezone_contract"] == "NOT_FOUND_IN_FROZEN_SOURCE_OR_WORKER_PROOF" and
                   not aware_starts and not is_upgrade,
                   "Source-specific timezone has not been historically proven")
        else:
            ensure(r["source_timezone_contract"] == "EXPLICIT_OFFSET_WHERE_PRESENT",
                   "Timezone-independent case without governing clock rule")
        if r["historical_rule"] == "SPLIT_EVENT_CLOCK_REQUIRES_UNPROVEN_HISTORICAL_TIME_INTERPRETATION":
            ensure(isinstance(r["split_child"], dict) and
                   r["split_child"]["parent_record_id"] == r["parent_record_id"] and
                   r["split_child"]["original_row_index"] == orig_ref["row_index"],
                   "Split child attribution not retained")
        else:
            ensure(r["split_child"] is None, "Unexpected split child")
        reasons[r["historical_rule"]] += 1
        city[r["city"]] += 1

    ensure(timezone == {"dnipro": 37, "mykolaiv": 26}, "Timezone cases no longer 37+26")
    ensure(sum(timezone.values()) == 63, "Expected 63 timezone cases")
    ensure(len(rows)-sum(timezone.values()) == 16, "Expected 16 non-timezone cases")
    ensure(len(promoted) == 3 and len(rows)-len(promoted) == 76,
           "Three immutable evidence-backed promotions/76 residual expected")
    ensure(reasons == {
        "UNIQUE_EXACT_ORIGINAL_ALERT_START": 2,
        "UNIQUE_CONTAINMENT_ALL_EXPLICIT_EVENT_TIMES": 1,
        "SOURCE_SPECIFIC_TIMEZONE_CONTRACT_MISSING": 63,
        "EXACT_UNIQUE_ORIGINAL_EVENT_OR_ALERT_CLOCK_UNAVAILABLE": 9,
        "SPLIT_EVENT_CLOCK_REQUIRES_UNPROVEN_HISTORICAL_TIME_INTERPRETATION": 2,
        "EXPLICIT_CLOCK_NOT_EQUAL_TO_CANONICAL_ALERT_BOUNDARY": 2,
    }, "Changed per-case cause accounting")
    ensure(city == {"dnipro": 45, "mykolaiv": 29, "chernihiv": 1, "kharkiv": 1,
                    "kherson": 1, "odesa": 2}, "Changed original source-link city distribution")
    return {
        "status": "PASS_OFFLINE_RESEARCH_ONLY",
        "input_case_count": 79,
        "original_source_memberships_unmodified": 1429,
        "original_unbound_not_adjudicated": 25,
        "original_git_source_record_identifications": len(exact_source_hashes),
        "newly_independently_derivable": len(promoted),
        "still_replay_only": 76,
        "confirmed_original_source_memberships": 0,
        "affirmative_historical_contradictions": 0,
        "timezone_case_count": 63,
        "timezone_by_city": dict(sorted(timezone.items())),
        "non_timezone_case_count": 16,
        "reason_counts": dict(sorted(reasons.items())),
        "city_counts": dict(sorted(city.items())),
        "promoted_link_keys": sorted(promoted),
        "gate_C4": "NOT_PROVEN",
        "no_neon_no_classifier_no_source_changes": True,
    }


def negative_controls(registry, proof, originals, episodes):
    def mutate_remove(r):
        r["records"].pop()
    def mutate_duplicate(r):
        r["records"].append(copy.deepcopy(r["records"][0]))
    def mutate_link(r):
        r["records"][0]["source_link_key"] = "0" * 64
    def mutate_classification(r):
        r["records"][0]["classification_key"] = "0" * 64
    def mutate_parent(r):
        r["records"][0]["parent_record_id"] = "bad_parent"
    def mutate_source_blob(r):
        r["records"][0]["original_git"]["blob_sha"] = "0" * 40
    def mutate_source_row_hash(r):
        r["records"][0]["original_git"]["row_sha256"] = "0" * 64
    def mutate_target_interval(r):
        r["records"][0]["expected_original_target_interval"]["start"] = "2020-01-01T00:00:00Z"
    def mutate_naive_promotion(r):
        x = next(x for x in r["records"] if x["source_specific_timezone_case"])
        x["proposed_after"] = "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"
    def mutate_missing_timezone_flag(r):
        x = next(x for x in r["records"] if x["source_specific_timezone_case"])
        x["source_specific_timezone_case"] = False
    def mutate_clock(r):
        x = next(x for x in r["records"] if x["proposed_after"] != "REPLAY_DERIVED_ONLY")
        key = next(iter(x["clock_fields"]))
        x["clock_fields"][key] = "2020-01-01T00:00:00+00:00"
    def mutate_fake_explicit_clock(r):
        x = next(x for x in r["records"] if x["historical_rule"] == "EXPLICIT_CLOCK_NOT_EQUAL_TO_CANONICAL_ALERT_BOUNDARY")
        x["proposed_after"] = "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"
    def mutate_split(r):
        x = next(x for x in r["records"] if x["split_child"])
        x["split_child"]["parent_record_id"] = "fake"
    tests = {
        "deleted_membership": mutate_remove,
        "duplicated_membership": mutate_duplicate,
        "invented_link_key": mutate_link,
        "changed_classification_key": mutate_classification,
        "changed_parent": mutate_parent,
        "changed_git_blob": mutate_source_blob,
        "changed_record_digest": mutate_source_row_hash,
        "changed_accepted_interval": mutate_target_interval,
        "naive_clock_promoted": mutate_naive_promotion,
        "missing_timezone_flag": mutate_missing_timezone_flag,
        "forged_original_clock": mutate_clock,
        "promoted_nonmatching_explicit_clock": mutate_fake_explicit_clock,
        "corrupted_split_attribution": mutate_split,
    }
    rejected = []
    for name, transform in tests.items():
        altered = copy.deepcopy(registry)
        transform(altered)
        try:
            validate(altered, proof, originals, episodes)
        except EvidenceError:
            rejected.append(name)
        else:
            raise EvidenceError("Negative mutation was accepted: " + name)
    ensure(len(rejected) == len(tests), "Incomplete negative mutation suite")
    return rejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    proof, originals, episodes = load_immutable_sources(registry)
    result = validate(registry, proof, originals, episodes)
    negative = negative_controls(registry, proof, originals, episodes)
    result["negative_controls_rejected"] = len(negative)
    result["negative_control_names"] = negative
    result["registry_sha256"] = hexsha(args.registry.read_bytes())
    result["accepted_proof_blob"] = ACCEPTED_PROOF_BLOB
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
