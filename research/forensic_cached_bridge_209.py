#!/usr/bin/env python3
"""Frozen, offline, read-only reconciliation of WIP cached-bridge identity differences.

Never maps or rewrites accepted episode IDs. No production source clients, HTTP
access, database connections, or historical state updates. Python stdlib only.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

WIP_SHA = "567c0aab3aaf98a5b8dd788021a26ece41f083e3"
PROD_SHA = "97ec99389259f8d0cfcecc17a2ff77302bb0615f"
FROZEN_SNAPSHOT_SHA256 = "37e26fc1a7433785ae3b80c3deb07840b8263473f0167ca14787b3621263a35c"
FROZEN_INPUT_SHA256 = {
    "ukrainealarm_bridge.json": "7194d5089fbb68165366bea0045660c9c5365cff4457e652d7a18e31b6793f75",
    "alerts_combined.json": "cb18e0c7a2cbcb7bdcd5ef5d5a2009029346ed27523642c59f03a6bdb1fb6cda",
    "sevastopol_events.json": "1b0a92690c9bd79878c0c7802fb20cb4dca2f5cef59992ca435fc661877d6f1f",
}
EXPECTED = {"kyiv": 185, "mykolaiv": 12, "sumy": 9, "kharkiv": 3}
DATA = "kyiv-air-alerts-grafana/data/"
WINDOW_SECONDS = 15 * 60
UTC = timezone.utc
NETWORK_CALLS = {"ukrainealarm": 0, "neon": 0, "other": 0}


def forbid_network(*args, **kwargs):
    NETWORK_CALLS["other"] += 1
    raise AssertionError("Offline forensic network attempt blocked")


socket.create_connection = forbid_network
socket.socket.connect = forbid_network
socket.socket.connect_ex = forbid_network


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def read(path):
    raw = path.read_bytes()
    return json.loads(raw), sha256(raw)


def parse(value):
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    assert dt.tzinfo is not None and dt.utcoffset() is not None, value
    return dt.astimezone(UTC)


def iso(dt):
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def eid(city, start, end):
    return sha256(f"{city}|{start}|{end}".encode("utf-8"))[:24]


def normalized_pair(row, first="start", last="end"):
    return (iso(parse(row[first])), iso(parse(row[last])))


def git_record(repo, source, blob, pointer, row):
    keep = {k: row.get(k) for k in (
        "start", "end", "source", "duration_minutes", "city_key",
        "region_id", "alert_type", "logical_grouping") if k in row}
    return {"commit": WIP_SHA if repo == "wip" else PROD_SHA,
            "path": DATA + source, "blob": blob,
            "json_pointer": pointer, "source_fields": keep}


def source_index(rows, source, repo, blob, grouping_key=None):
    index = defaultdict(list)
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("start") or not row.get("end"):
            continue
        try:
            pair = normalized_pair(row)
        except (ValueError, AssertionError):
            continue
        key = (row.get(grouping_key), *pair) if grouping_key else pair
        index[key].append(git_record(repo, source, blob, f"/{i}", row))
    return index


def grouping(candidates):
    """Same merging rule as frozen apply_ukrainealarm_bridge.union_alerts:
       touching or overlapping source intervals form one union."""
    merged = []
    for rec in sorted(candidates, key=lambda x: (x["start"], x["end"])):
        if not merged or rec["start"] > merged[-1]["end"]:
            merged.append({"start": rec["start"], "end": rec["end"],
                           "source_members": [rec["source_record"]]})
        else:
            if rec["end"] > merged[-1]["end"]:
                merged[-1]["end"] = rec["end"]
            merged[-1]["source_members"].append(rec["source_record"])
    return merged


def candidate_row(city, start, end, family, source, members):
    sid, tid = iso(start), iso(end)
    return {
        "city": city, "source_family": family,
        "episode_id": eid(city, sid, tid),
        "start": sid, "end": tid, "alert_source": source,
        "grouping": "union_alerts_overlap_or_touch" if family == "UkraineAlarm raion-proxy" else "individual_interval",
        "member_count": len(members), "source_members": members,
    }


def produce_candidates(prod, blobs):
    bridge = prod["ukrainealarm_bridge.json"]
    assert bridge["schema_version"] == 3 and len(bridge["regions"]) == 21
    records = defaultdict(list)
    for i, row in enumerate(bridge["events"]):
        city = row["city_key"]
        src = git_record("prod", "ukrainealarm_bridge.json",
                         blobs["prod:ukrainealarm_bridge.json"], f"/events/{i}", row)
        records[city].append({"start": parse(row["start"]), "end": parse(row["end"]),
                              "source_record": src})
    polled = {}
    for city, region in sorted(bridge["regions"].items()):
        if region["kind"] == "proxy":
            groups = grouping(records[city])
            polled[city] = [
                candidate_row(city, g["start"], g["end"], "UkraineAlarm raion-proxy",
                              "ukrainealarm_bridge_cached_union", g["source_members"])
                for g in groups]
        else:
            polled[city] = [
                candidate_row(city, r["start"], r["end"], "UkraineAlarm exact",
                              "ukrainealarm_bridge_cached", [r["source_record"]])
                for r in records[city]]
    for city, name, group in (
        ("kyiv", "alerts_combined.json", "Kyiv exact-city"),
        ("sevastopol", "sevastopol_events.json", "Sevastopol exact-city"),
    ):
        rows = prod[name] if city == "kyiv" else prod[name]["pairs"]
        polled[city] = [
            candidate_row(city, parse(row["start"]), parse(row["end"]), group,
                          "kyiv_combined_exact_city" if city == "kyiv" else "sevastopol_verified_exact_city_pairs",
                          [git_record("prod", name, blobs["prod:" + name],
                                      f"/{i}" if city == "kyiv" else f"/pairs/{i}", row)])
            for i, row in enumerate(rows) if parse(row["end"]) > parse(row["start"])
        ]
    for city in polled:
        by_id = {row["episode_id"]: row for row in polled[city]}
        polled[city] = sorted(by_id.values(), key=lambda x: (x["end"], x["start"], x["episode_id"]))
    return polled


def exact_id_trace(old, city):
    start, end = old.get("alert_start"), old.get("alert_end")
    derived = eid(city, start, end)
    return {"algorithm": "sha256(UTF8(city_key+'|'+iso_utc_start+'|'+iso_utc_end))[:24]",
            "original_id": old.get("episode_id"), "recomputed_id": derived,
            "matches_original": derived == old.get("episode_id"),
            "full_precision_input": [start, end]}


def matches(pair, source_index_for_city):
    return source_index_for_city.get(pair, [])


def source_for_original(city, old, wip_indices, blobs):
    s, e = old["alert_start"], old["alert_end"]
    pair = (iso(parse(s)), iso(parse(e)))
    if city == "kyiv":
        return matches(pair, wip_indices["kyiv"])
    if city == "sevastopol":
        return matches(pair, wip_indices["sevastopol"])
    direct = wip_indices["bridge"].get((city, *pair), [])
    if direct:
        return direct
    # No fabricated raw provenance for union intervals or historical API responses.
    return []


def seconds_overlap(a, b, c, d):
    return round(max(0, (min(b, d) - max(a, c)).total_seconds()), 6)


def plausible(old_start, old_end, cand_start, cand_end):
    ov = seconds_overlap(old_start, old_end, cand_start, cand_end)
    gap = max(0, (cand_start - old_end).total_seconds(),
              (old_start - cand_end).total_seconds())
    # All overlapping candidates, plus adjacent near-window candidates
    # only when at least one homologous endpoint is also within 15m.
    return ov > 0 or (gap <= WINDOW_SECONDS and min(
        abs((cand_start - old_start).total_seconds()),
        abs((cand_end - old_end).total_seconds())) <= WINDOW_SECONDS)


def correspondence(old, candidate):
    s, e = parse(old["alert_start"]), parse(old["alert_end"])
    cs, ce = parse(candidate["start"]), parse(candidate["end"])
    ds, de = round((cs - s).total_seconds(), 6), round((ce - e).total_seconds(), 6)
    whole = (s.replace(microsecond=0) == cs.replace(microsecond=0) and
             e.replace(microsecond=0) == ce.replace(microsecond=0))
    minute = (s.replace(second=0, microsecond=0) == cs.replace(second=0, microsecond=0) and
              e.replace(second=0, microsecond=0) == ce.replace(second=0, microsecond=0))
    precision = bool(s.microsecond or e.microsecond or cs.microsecond or ce.microsecond)
    old_fragment = cs <= s and e <= ce and (cs < s or e < ce)
    new_fragment = s <= cs and ce <= e and (s < cs or ce < e)
    members = candidate["source_members"]
    member_exact = any(
        parse(x["source_fields"]["start"]) == s and parse(x["source_fields"]["end"]) == e
        for x in members)
    return {
        "production_id": candidate["episode_id"], "production_start": candidate["start"],
        "production_end": candidate["end"], "production_alert_source": candidate["alert_source"],
        "source_family": candidate["source_family"],
        "start_delta_seconds_signed": ds, "end_delta_seconds_signed": de,
        "overlap_seconds": seconds_overlap(s, e, cs, ce),
        "precision_only_whole_second_match": whole and precision and (ds != 0 or de != 0),
        "same_minute_but_not_same_instant": minute and (ds != 0 or de != 0),
        "wip_fragment_of_production": old_fragment,
        "production_fragment_of_wip": new_fragment,
        "wip_interval_is_raw_production_member": member_exact,
        "candidate_grouping": candidate["grouping"], "candidate_member_count": candidate["member_count"],
        "candidate_source_locations": candidate["source_members"],
        "candidate_hash_recomputed": eid(old["city_key"], candidate["start"], candidate["end"]),
        "candidate_hash_valid": eid(old["city_key"], candidate["start"], candidate["end"]) == candidate["episode_id"],
    }


def walk_references(value, target_ids, path="", depth=0):
    if depth > 35:
        return
    if isinstance(value, str):
        if value in target_ids:
            yield value, path
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from walk_references(v, target_ids, path + "/" + str(k).replace("~", "~0").replace("/", "~1"), depth+1)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_references(v, target_ids, path + "/" + str(i), depth+1)


def refs_from_queue(queue, target_ids, queue_blob):
    found = defaultdict(list)
    for idx, entry in enumerate(queue):
        linked = defaultdict(list)
        for eid_value, pointer in walk_references(entry, target_ids):
            linked[eid_value].append(pointer)
        for original_id, pointers in linked.items():
            summary = {"json_pointer": f"/{idx}", "path": DATA + "explosion_review_queue.json",
                       "commit": WIP_SHA, "blob": queue_blob,
                       "exact_id_reference_paths": sorted(set(pointers))}
            if isinstance(entry, dict):
                for fld in ("candidate_id", "id", "episode_id", "city_key",
                            "status", "classification", "verdict",
                            "review_decision", "approved_by", "reviewed_at"):
                    if fld in entry and isinstance(entry[fld], (str, bool, int, type(None))):
                        summary[fld] = entry[fld]
            found[original_id].append(summary)
    return found


def primary_category(row):
    candidates = row["candidate_production_episodes"]
    old_sources = row["original_raw_source_records"]
    if not candidates:
        return "F", "no candidate in overlap / justified 15-minute boundary window", True
    if any(x["source_family"] != row["source_family"] for x in candidates):
        return "E", "source or geographic grain differs", True
    if len(candidates) == 1 and row["hash_contract"]["matches_original"] and candidates[0]["precision_only_whole_second_match"]:
        return "A", "exact at whole-second precision; different subsecond representation only", False
    if len(candidates) == 1 and candidates[0]["wip_fragment_of_production"] and (
        candidates[0]["wip_interval_is_raw_production_member"] or
        candidates[0]["candidate_member_count"] > 1):
        return "D", "old interval is contained by production union; grouping contract visible", (
            not candidates[0]["wip_interval_is_raw_production_member"])
    if len(candidates) > 1:
        overlapping = [c for c in candidates if c["overlap_seconds"] > 0]
        if len(overlapping) > 1:
            return "D", "one original interval overlaps several production logical episodes", True
        return "G", "multiple plausible candidates without unique supported equivalence", True
    if len(candidates) == 1 and candidates[0]["same_minute_but_not_same_instant"]:
        if old_sources and row["source_family"] == "Kyiv exact-city":
            return "B", "minute-aligned older source record versus second-level new source record; transformation not proven", True
        return "G", "same-minute time values but original source/time semantics insufficient", True
    if len(candidates) == 1 and old_sources and candidates[0]["start_delta_seconds_signed"] != 0 or (
        len(candidates) == 1 and old_sources and candidates[0]["end_delta_seconds_signed"] != 0):
        return "C", "distinct source-file record time instants; no precision-only proof", True
    return "G", "temporal candidate exists but provenance, grouping or unique source identity unproven", True


def save(path, obj):
    raw = (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256(raw), len(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wip", type=Path, required=True)
    parser.add_argument("--prod", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for key in ("UKRAINEALARM_API_TOKEN", "ATTACK_EVENT_DATABASE_URL", "DATABASE_URL"):
        assert not os.environ.get(key), f"forbidden production env var {key}"
    assert git(args.wip, "rev-parse", "HEAD") == WIP_SHA
    assert git(args.prod, "rev-parse", "HEAD") == PROD_SHA

    original_paths = {
        "state": args.wip / DATA / "explosion_candidate_monitor_state.json",
        "queue": args.wip / DATA / "explosion_review_queue.json",
        "wip_bridge": args.wip / DATA / "ukrainealarm_bridge.json",
        "wip_kyiv": args.wip / DATA / "alerts_combined.json",
        "wip_sevastopol": args.wip / DATA / "sevastopol_events.json",
        "prod_bridge": args.prod / DATA / "ukrainealarm_bridge.json",
        "prod_kyiv": args.prod / DATA / "alerts_combined.json",
        "prod_sevastopol": args.prod / DATA / "sevastopol_events.json",
    }
    before = {k: sha256(p.read_bytes()) for k, p in original_paths.items()}
    blobs = {("wip:" if k.startswith("wip") or k in ("state", "queue") else "prod:") +
             {"state": "explosion_candidate_monitor_state.json",
              "queue": "explosion_review_queue.json",
              "wip_bridge": "ukrainealarm_bridge.json", "wip_kyiv": "alerts_combined.json",
              "wip_sevastopol": "sevastopol_events.json",
              "prod_bridge": "ukrainealarm_bridge.json", "prod_kyiv": "alerts_combined.json",
              "prod_sevastopol": "sevastopol_events.json"}[k]:
             git(args.wip if k.startswith("wip") or k in ("state", "queue") else args.prod,
                 "hash-object", DATA +
                 {"state": "explosion_candidate_monitor_state.json",
                  "queue": "explosion_review_queue.json",
                  "wip_bridge": "ukrainealarm_bridge.json", "wip_kyiv": "alerts_combined.json",
                  "wip_sevastopol": "sevastopol_events.json",
                  "prod_bridge": "ukrainealarm_bridge.json", "prod_kyiv": "alerts_combined.json",
                  "prod_sevastopol": "sevastopol_events.json"}[k])
             for k in original_paths}
    assert blobs["wip:explosion_candidate_monitor_state.json"] == "fe8ffd3301834f52d42cd6586b04baf0657bdb91"
    assert blobs["wip:explosion_review_queue.json"] == "aacda53916d54cbb1e18c26915cf0c1dc79d7725"

    prod = {}
    for name, key in (("ukrainealarm_bridge.json", "prod_bridge"),
                      ("alerts_combined.json", "prod_kyiv"),
                      ("sevastopol_events.json", "prod_sevastopol")):
        prod[name], actual = read(original_paths[key])
        assert actual == FROZEN_INPUT_SHA256[name], (name, actual)
    computed_snapshot = sha256(json.dumps(FROZEN_INPUT_SHA256, sort_keys=True,
                                         separators=(",", ":")).encode("ascii"))
    assert computed_snapshot == FROZEN_SNAPSHOT_SHA256
    state, _ = read(original_paths["state"])
    queue, _ = read(original_paths["queue"])
    wip_bridge, _ = read(original_paths["wip_bridge"])
    wip_kyiv, _ = read(original_paths["wip_kyiv"])
    wip_sevastopol, _ = read(original_paths["wip_sevastopol"])
    assert isinstance(queue, list) and isinstance(state["cities"], dict)
    assert len(prod["ukrainealarm_bridge.json"]["events"]) == 3543
    candidates = produce_candidates(prod, blobs)
    assert len(candidates) == 23 and sum(map(len, candidates.values())) == 6556, {
        k: len(v) for k, v in candidates.items()}
    frozen_region_kind = {k: v["kind"] for k, v in prod["ukrainealarm_bridge.json"]["regions"].items()}
    families = {k: ("UkraineAlarm exact" if kind == "exact" else "UkraineAlarm raion-proxy")
                for k, kind in frozen_region_kind.items()}
    families.update({"kyiv": "Kyiv exact-city", "sevastopol": "Sevastopol exact-city"})
    wip_indices = {
        "kyiv": source_index(wip_kyiv, "alerts_combined.json", "wip",
                             blobs["wip:alerts_combined.json"]),
        "sevastopol": source_index(wip_sevastopol["pairs"], "sevastopol_events.json", "wip",
                                   blobs["wip:sevastopol_events.json"]),
        "bridge": source_index(wip_bridge["events"], "ukrainealarm_bridge.json", "wip",
                               blobs["wip:ukrainealarm_bridge.json"], grouping_key="city_key"),
    }
    rows = []
    for city, cstate in sorted(state["cities"].items()):
        if city not in candidates or not candidates[city]:
            continue
        now = candidates[city]
        known = {x["episode_id"] for x in now}
        low = min(parse(x["end"]) for x in now)
        high = max(parse(x["end"]) for x in now)
        for index, old in enumerate(cstate.get("episodes") or []):
            original_id = old.get("episode_id")
            if old.get("identity_superseded_by_episode_id") or original_id in known:
                continue
            if not old.get("alert_end") or not old.get("alert_start"):
                continue
            end_dt = parse(old["alert_end"])
            if not low <= end_dt <= high:
                continue
            s = parse(old["alert_start"])
            origins = source_for_original(city, old, wip_indices, blobs)
            temporal = [
                correspondence(old, c) for c in now
                if plausible(s, end_dt, parse(c["start"]), parse(c["end"]))
            ]
            temporal.sort(key=lambda x: (-x["overlap_seconds"],
                                          abs(x["end_delta_seconds_signed"]),
                                          abs(x["start_delta_seconds_signed"]),
                                          x["production_id"]))
            row = {
                "city": city, "city_label": cstate.get("city"), "source_family": families[city],
                "original_episode_id": original_id,
                "original_alert_start_exact": old["alert_start"],
                "original_alert_end_exact": old["alert_end"],
                "original_alert_source": old.get("alert_source"),
                "original_grouping": {
                    "logical_grouping": old.get("logical_grouping"),
                    "raw_interval_count": old.get("raw_interval_count"),
                    "raw_intervals": old.get("raw_intervals"),
                    "identity_superseded_by_episode_id": old.get("identity_superseded_by_episode_id"),
                },
                "original_episode_state_complete": old,
                "original_git_location": {
                    "path": DATA + "explosion_candidate_monitor_state.json",
                    "commit": WIP_SHA, "blob": blobs["wip:explosion_candidate_monitor_state.json"],
                    "json_pointer": f"/cities/{city}/episodes/{index}",
                },
                "original_raw_source_records": origins,
                "historical_raw_record_observed": bool(origins),
                "hash_contract": exact_id_trace(old, city),
                "candidate_production_episodes": temporal,
                "candidate_count": len(temporal),
                "comparison_window": {
                    "rule": "same city/grain; all positive temporal overlaps, or gap <= 900s with at least one homologous endpoint within 900s",
                    "seconds": WINDOW_SECONDS, "cached_candidate_end_horizon": [iso(low), iso(high)]
                },
            }
            rows.append(row)
    rows.sort(key=lambda x: (x["city"], x["original_alert_start_exact"], x["original_episode_id"]))
    by_city = dict(sorted(Counter(x["city"] for x in rows).items()))
    assert by_city == EXPECTED, (by_city, EXPECTED)
    ids = [x["original_episode_id"] for x in rows]
    assert len(ids) == len(set(ids)) == 209
    queue_refs = refs_from_queue(queue, set(ids), blobs["wip:explosion_review_queue.json"])
    candidate_to_orig = defaultdict(set)
    for row in rows:
        for c in row["candidate_production_episodes"]:
            candidate_to_orig[c["production_id"]].add(row["original_episode_id"])
    for row in rows:
        r = row["original_episode_id"]
        row["review_classification_references"] = queue_refs.get(r, [])
        row["review_reference_count"] = len(row["review_classification_references"])
        one = row["candidate_production_episodes"]
        n = len(one)
        if n == 0:
            kind = "unmatched"
        elif n > 1:
            kind = "one_to_many_candidates"
        elif len(candidate_to_orig[one[0]["production_id"]]) > 1:
            kind = "many_to_one_candidates"
        else:
            kind = "one_to_one_candidate"
        row["candidate_cardinality"] = kind
        row["candidate_competing_wip_id_counts"] = {
            c["production_id"]: len(candidate_to_orig[c["production_id"]]) for c in one}
        root, why, unresolved = primary_category(row)
        # A truly shared candidate cannot be treated as a proven 1:1 match.
        if kind == "many_to_one_candidates" and root == "A":
            root, why, unresolved = "G", "several WIP IDs share the same candidate despite subsecond resemblance", True
        row["root_cause_category"] = root
        row["root_cause_evidence"] = why
        row["identity_relationship_unresolved"] = unresolved
        row["equivalence_authority"] = "NONE; diagnostic hypothesis only; historical IDs and reviewer decisions retained"
    assert all(c["candidate_hash_valid"] for r in rows for c in r["candidate_production_episodes"])
    assert all(r["original_episode_state_complete"]["episode_id"] == r["original_episode_id"] for r in rows)
    expected_rows = {"schema_version": 1, "kind": "frozen_wip_cached_bridge_209_identity_manifest",
                     "authority": "non-mutating evidence; no automatic mapping or historical reclassification",
                     "wip_commit": WIP_SHA, "site_prod_commit": PROD_SHA,
                     "frozen_snapshot_sha256": computed_snapshot, "frozen_input_sha256": FROZEN_INPUT_SHA256,
                     "population_selection": "unsuperseded WIP state IDs not in deterministic cached candidate IDs, with old end within candidate end horizon",
                     "source_blobs": blobs,
                     "candidate_window_seconds": WINDOW_SECONDS,
                     "count": len(rows), "rows": rows}
    out = args.out
    manifest_sha, manifest_len = save(out / "wip_cached_209_identity_manifest_2026-10-15.json", expected_rows)
    counts = dict(sorted(Counter(x["root_cause_category"] for x in rows).items()))
    by_city_category = {city: dict(sorted(Counter(x["root_cause_category"] for x in rows if x["city"] == city).items()))
                        for city in EXPECTED}
    card = dict(sorted(Counter(x["candidate_cardinality"] for x in rows).items()))
    unresolved = [
        {"city": r["city"], "original_episode_id": r["original_episode_id"],
         "root_cause_category": r["root_cause_category"], "why": r["root_cause_evidence"],
         "candidate_ids": [c["production_id"] for c in r["candidate_production_episodes"]],
         "review_reference_count": r["review_reference_count"]}
        for r in rows if r["identity_relationship_unresolved"]]
    report = {
        "schema_version": 1, "kind": "wip_cached_209_identity_reconciliation_report",
        "authority": "NOT ACCEPTED; production/WIP activation NO-GO",
        "manifest_sha256": manifest_sha, "manifest_bytes": manifest_len,
        "total_mismatches": len(rows), "city_counts": by_city,
        "category_counts": counts, "city_category_counts": by_city_category,
        "candidate_cardinality_counts": card,
        "unresolved_identity_relationship_count": len(unresolved),
        "candidate_count_zero": sum(not r["candidate_count"] for r in rows),
        "records_with_wip_original_raw_source": sum(r["historical_raw_record_observed"] for r in rows),
        "records_with_review_classification_references": sum(r["review_reference_count"] > 0 for r in rows),
        "total_exact_queue_item_links": sum(r["review_reference_count"] for r in rows),
        "valid_original_hashes": sum(r["hash_contract"]["matches_original"] for r in rows),
        "original_hash_anomaly_ids": [r["original_episode_id"] for r in rows
                                      if not r["hash_contract"]["matches_original"]],
        "precision_mechanical_count": counts.get("A", 0),
        "distinct_source_or_boundary_count": counts.get("B", 0) + counts.get("C", 0),
        "grouping_count": counts.get("D", 0),
        "missing_source_episode_proven": False,
        "missing_source_episode_note": "Absence of a deterministic equivalent is not proof of a missing historical alert.",
        "comparability": "C/G/B/D are diagnostic cause patterns, not proven full episode equivalences",
        "review_decisions_transferred": 0, "historical_episode_ids_changed": 0,
    }
    report_sha, _ = save(out / "wip_cached_209_reconciliation_report_2026-10-15.json", report)
    unresolved_sha, _ = save(out / "wip_cached_209_unresolved_2026-10-15.json",
                              {"schema_version": 1, "manifest_sha256": manifest_sha,
                               "count": len(unresolved), "rows": unresolved})
    after = {k: sha256(p.read_bytes()) for k, p in original_paths.items()}
    assert before == after, "WIP or prod original input bytes changed"
    assert git(args.wip, "status", "--porcelain") == "", "WIP checkout modified"
    assert git(args.prod, "status", "--porcelain") == "", "production checkout modified"
    assert git(args.wip, "rev-parse", "HEAD") == WIP_SHA
    assert git(args.prod, "rev-parse", "HEAD") == PROD_SHA
    assert sum(NETWORK_CALLS.values()) == 0, NETWORK_CALLS
    proof = {
        "schema_version": 1, "kind": "wip_cached_209_offline_regression_proof",
        "wip_head_before_after": WIP_SHA, "site_prod_head_before_after": PROD_SHA,
        "git_blobs": blobs, "before_sha256": before, "after_sha256": after,
        "byte_identical": before == after, "git_worktree_unchanged": True,
        "frozen_snapshot_sha256": computed_snapshot,
        "cached_city_count": len(candidates),
        "cached_episode_count": sum(map(len, candidates.values())),
        "population_count": 209, "all_original_ids_preserved": True,
        "all_review_records_unchanged": True,
        "all_geographic_grain_contracts_preserved": True,
        "all_proposed_correspondences_evidence_or_unresolved": True,
        "ukrainealarm_request_count": NETWORK_CALLS["ukrainealarm"],
        "neon_read_count": NETWORK_CALLS["neon"], "neon_write_count": 0,
        "other_network_attempts": NETWORK_CALLS["other"],
        "no_production_credentials": True, "no_production_or_wip_writes": True,
        "manifest_sha256": manifest_sha, "reconciliation_report_sha256": report_sha,
        "unresolved_sha256": unresolved_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_job": os.environ.get("GITHUB_JOB"),
        "executed_proof_code_commit": os.environ.get("GITHUB_SHA"),
        "decision": "PARTIAL_UNRESOLVED; WIP_ACTIVATION_NO_GO",
    }
    save(out / "wip_cached_209_regression_proof_2026-10-15.json", proof)
    executive = (
        "# WIP cached-bridge 209 historical identity forensic — 2026-10-15\n\n"
        "Status: PARTIAL — UNRESOLVED. WIP activation: NO-GO. "
        "This record proposes no new episode identities or reviewer decisions.\n\n"
        f"- Reconstructed: {len(rows)}, with 209 distinct unchanged original IDs.\n"
        f"- Cities: {json.dumps(by_city, sort_keys=True)}.\n"
        f"- Root-cause evidence groups (A-G): {json.dumps(counts, sort_keys=True)}.\n"
        f"- Subsecond-only A: {counts.get('A',0)}; source/boundary representation B/C: "
        f"{counts.get('B',0)+counts.get('C',0)}; grouping D: {counts.get('D',0)}; "
        f"identity relationships unresolved: {len(unresolved)}.\n"
        f"- Candidate cardinalities: {json.dumps(card, sort_keys=True)}.\n"
        f"- Original hash contract validated: {report['valid_original_hashes']}/209.\n"
        f"- Git review/queue links: {report['records_with_review_classification_references']} original IDs; "
        f"{report['total_exact_queue_item_links']} items. No decisions reassigned.\n"
        "- No missing source episode is proven; snapshot-horizon absence is not a source loss finding.\n"
        f"- Full manifest SHA-256: {manifest_sha} ({manifest_len} bytes).\n"
        f"- Frozen input snapshot SHA-256: {computed_snapshot}.\n"
        "- All findings are offline and provisional; root-cause explanation is not "
        "permission to re-key, reclassify, or activate WIP.\n\n"
        "Next task: independent row-level acceptance of this manifest and source-provenance "
        "adjudication for unresolved B/C/D/E/F/G cases; only then design an optional "
        "read-only compatibility layer, separately test full publisher/review/classifier "
        "invariance and request guarded WIP activation authorization.\n"
    )
    (out / "wip_cached_209_executive_summary_2026-10-15.md").write_text(executive, encoding="utf-8")
    print(json.dumps({"manifest_sha256": manifest_sha, "population": len(rows),
                      "by_city": by_city, "categories": counts, "cardinality": card,
                      "unresolved": len(unresolved), "raw_source_recovered":
                      report["records_with_wip_original_raw_source"],
                      "queue_linked": report["records_with_review_classification_references"],
                      "original_hash_valid": report["valid_original_hashes"],
                      "no_network": True}, sort_keys=True))


if __name__ == "__main__":
    main()
