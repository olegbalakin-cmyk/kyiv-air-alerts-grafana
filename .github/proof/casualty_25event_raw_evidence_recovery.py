#!/usr/bin/env python3
"""Read-only, exact-object casualty queue recovery and deterministic offline proof.

This script never changes Git refs, monitor state, review decisions or published data.
Raw extraction is Git-only; all analysis operates on four saved local JSON files.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

FROZEN = "b4219a896193602fd93ef92fc231cd9bdb2fe2c0"
NEWER = "04823b17f60ac6fe23ecb74848a6ac7c618637df"
DATA = "kyiv-air-alerts-grafana/data/casualties"
OBJECTS = (
    ("frozen_queue", FROZEN, DATA + "/multicity_review_queue.json",
     "c6c073cb632c1b61d534b6d96ca17ce8bc86e637", "raw/frozen_queue.json"),
    ("newer_queue", NEWER, DATA + "/multicity_review_queue.json",
     "fc6ca1ed722f58b16647ed8b747d92a89ffc0e1f", "raw/newer_queue.json"),
    ("newer_monitor_state", NEWER, DATA + "/candidate_monitor_state.json",
     "784973dc2d82ce5f09feeb57ed53e3df659f5862", "raw/newer_monitor_state.json"),
    ("newer_monitor_last_run", NEWER, DATA + "/candidate_monitor_last_run.json",
     "7c1486de9a7cec2224b0b10544447ca33e673ded", "raw/newer_monitor_last_run.json"),
)
EXPECTED = {
    "frozen": {"candidates": 801, "pending": 800, "unique_city_url": 530,
               "duplicate_clusters": 245, "records_in_duplicate_clusters": 516,
               "excess_url_records": 271},
    "newer": {"candidates": 835, "pending": 834, "unique_city_url": 563,
              "duplicate_clusters": 246, "records_in_duplicate_clusters": 518,
              "excess_url_records": 272},
}
NORMALIZED = (
    "duplicate_clusters_complete.csv", "candidate_lookup_complete.csv",
    "candidate_transitions.csv", "if1008_followup.json",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git(repo, *args):
    process = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=False
    )
    if process.returncode:
        raise RuntimeError("Git command failed: " + " ".join(args) + " | " +
                           process.stderr.decode("utf-8", "replace")[:1200])
    return process.stdout.decode("utf-8", "strict").strip()


def extract(repo, out):
    if git(repo, "rev-parse", "--verify", "HEAD") != os.environ.get("GITHUB_SHA", git(repo, "rev-parse", "--verify", "HEAD")):
        raise RuntimeError("Runner checked-out HEAD does not match the workflow commit")
    git(repo, "merge-base", "--is-ancestor", FROZEN, NEWER)
    file_entries = []
    for role, commit, relative_path, expected_blob, destination in OBJECTS:
        tree_entry = git(repo, "ls-tree", commit, "--", relative_path)
        expected_entry = "100644 blob " + expected_blob + "\t" + relative_path
        if tree_entry != expected_entry:
            raise RuntimeError("Historical path/blob identity mismatch: " + role +
                               " observed=" + tree_entry[:250])
        if git(repo, "cat-file", "-t", expected_blob) != "blob":
            raise RuntimeError("Object is not a blob: " + role)
        raw_file = out / destination
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        with raw_file.open("wb") as handle:
            process = subprocess.run(["git", "cat-file", "blob", expected_blob],
                                     cwd=repo, stdout=handle, stderr=subprocess.PIPE,
                                     check=False)
        if process.returncode:
            raise RuntimeError("git cat-file blob failed: " + role)
        identity = git(repo, "hash-object", "--no-filters", str(raw_file))
        if identity != expected_blob:
            raise RuntimeError("Extracted raw-byte Git blob identity failure: " + role)
        raw_bytes = raw_file.read_bytes()
        try:
            parsed = json.loads(raw_bytes)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError("Raw blob is not valid JSON: " + role) from error
        wanted_type = list if role.endswith("queue") else dict
        if not isinstance(parsed, wanted_type):
            raise RuntimeError("Unexpected JSON root type: " + role)
        file_entries.append({
            "role": role, "historical_commit": commit, "historical_path": relative_path,
            "git_blob_expected": expected_blob, "ls_tree_blob": expected_blob,
            "git_hash_object_no_filters": identity, "raw_path": destination,
            "sha256": sha256_bytes(raw_bytes), "byte_length": len(raw_bytes),
            "json_root_type": "list" if isinstance(parsed, list) else "object",
            "valid_json": True,
        })
    manifest = {
        "purpose": "Exact raw Git evidence transfer; not a completed 25-event coverage audit",
        "frozen_wip_commit": FROZEN, "newer_wip_commit": NEWER,
        "frozen_is_ancestor_of_newer": True, "objects": file_entries,
    }
    write_json(out / "blob_manifest.json", manifest)
    return manifest


def write_json(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n").encode("utf-8"))


def write_csv(path, columns, records):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n",
                                extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in columns})


def queue_metrics(queue):
    if not isinstance(queue, list) or any(not isinstance(r, dict) for r in queue):
        raise RuntimeError("Queue is not a list of JSON objects")
    by_key = collections.defaultdict(list)
    candidate_ids = set()
    for item in queue:
        cid = item.get("candidate_id")
        city = item.get("city_key")
        url = item.get("url")
        if not isinstance(cid, str) or not cid or cid in candidate_ids:
            raise RuntimeError("Missing/repeated candidate ID")
        if not isinstance(city, str) or not city or not isinstance(url, str) or not url:
            raise RuntimeError("Missing city or original stored RSS URL")
        candidate_ids.add(cid)
        by_key[(city, url)].append(item)
    clusters = {key: rows for key, rows in by_key.items() if len(rows) > 1}
    metrics = {
        "candidates": len(queue),
        "pending": sum(r.get("status") == "needs_review" for r in queue),
        "unique_city_url": len(by_key),
        "duplicate_clusters": len(clusters),
        "records_in_duplicate_clusters": sum(len(rows) for rows in clusters.values()),
        "excess_url_records": sum(len(rows) - 1 for rows in clusters.values()),
    }
    if metrics["candidates"] - metrics["unique_city_url"] != metrics["excess_url_records"]:
        raise RuntimeError("Duplicate arithmetic invariant failed")
    return metrics, clusters


def candidate_lookup_rows(snapshots):
    result = []
    for snapshot in ("frozen", "newer"):
        for item in sorted(snapshots[snapshot], key=lambda r: r["candidate_id"]):
            result.append({
                "snapshot": snapshot,
                "candidate_id": item["candidate_id"],
                "city_key": item.get("city_key", ""),
                "city_label": item.get("city", ""),
                "status": item.get("status", ""),
                "source": item.get("source", ""),
                "publisher": item.get("publisher", ""),
                "publisher_url": item.get("publisher_url", ""),
                "stored_rss_url": item.get("url", ""),
                "title": item.get("title", ""),
                "published_at": item.get("published_at", ""),
                "first_discovered_at": item.get("first_discovered_at", ""),
                "last_seen_at": item.get("last_seen_at", ""),
                "alert_trigger_scope": item.get("alert_trigger_scope", ""),
                "trigger_episode_ids_json": canonical(item.get("trigger_episode_ids")),
                "trigger_check_labels_json": canonical(item.get("trigger_check_labels")),
                "review_disposition_json": canonical(item.get("review_disposition")),
                "review_history_json": canonical(item.get("review_history")),
                "candidate_record_sha256": sha256_bytes(canonical(item).encode("utf-8")),
            })
    return result


LOOKUP_FIELDS = (
    "snapshot", "candidate_id", "city_key", "city_label", "status", "source",
    "publisher", "publisher_url", "stored_rss_url", "title", "published_at",
    "first_discovered_at", "last_seen_at", "alert_trigger_scope",
    "trigger_episode_ids_json", "trigger_check_labels_json",
    "review_disposition_json", "review_history_json", "candidate_record_sha256",
)
CLUSTER_FIELDS = (
    "snapshot", "city_key", "stored_rss_url", "member_count", "excess_url_records",
    "candidate_ids_json", "publishers_json", "status_counts_json",
    "first_discovered_min", "last_seen_max",
)
TRANSITION_FIELDS = (
    "candidate_id", "transition", "changed_fields_json", "frozen_city_key",
    "newer_city_key", "frozen_status", "newer_status", "frozen_stored_rss_url",
    "newer_stored_rss_url", "frozen_first_discovered_at",
    "newer_first_discovered_at", "frozen_last_seen_at",
    "newer_last_seen_at", "frozen_trigger_episode_ids_json",
    "newer_trigger_episode_ids_json", "frozen_trigger_check_labels_json",
    "newer_trigger_check_labels_json", "frozen_candidate_json",
    "newer_candidate_json",
)


def duplicate_rows(all_clusters):
    result = []
    for snapshot in ("frozen", "newer"):
        for (city, url), members in sorted(all_clusters[snapshot].items()):
            first = [str(r["first_discovered_at"]) for r in members if r.get("first_discovered_at")]
            last = [str(r["last_seen_at"]) for r in members if r.get("last_seen_at")]
            result.append({
                "snapshot": snapshot, "city_key": city, "stored_rss_url": url,
                "member_count": len(members), "excess_url_records": len(members)-1,
                "candidate_ids_json": canonical(sorted(r["candidate_id"] for r in members)),
                "publishers_json": canonical(sorted({str(r.get("publisher") or "") for r in members})),
                "status_counts_json": canonical(dict(sorted(collections.Counter(
                    str(r.get("status") or "") for r in members).items()))),
                "first_discovered_min": min(first) if first else "",
                "last_seen_max": max(last) if last else "",
            })
    return result


def transitions(frozen, newer):
    left = {r["candidate_id"]: r for r in frozen}
    right = {r["candidate_id"]: r for r in newer}
    result = []
    transitions_count = collections.Counter()
    for cid in sorted(left.keys() | right.keys()):
        a = left.get(cid)
        b = right.get(cid)
        if a is not None and b is not None and canonical(a) == canonical(b):
            continue
        kind = "added" if a is None else "removed" if b is None else "modified"
        transitions_count[kind] += 1
        differences = sorted(k for k in set((a or {}).keys()) | set((b or {}).keys())
                             if (a or {}).get(k) != (b or {}).get(k))
        result.append({
            "candidate_id": cid, "transition": kind,
            "changed_fields_json": canonical(differences),
            "frozen_city_key": (a or {}).get("city_key", ""),
            "newer_city_key": (b or {}).get("city_key", ""),
            "frozen_status": (a or {}).get("status", ""),
            "newer_status": (b or {}).get("status", ""),
            "frozen_stored_rss_url": (a or {}).get("url", ""),
            "newer_stored_rss_url": (b or {}).get("url", ""),
            "frozen_first_discovered_at": (a or {}).get("first_discovered_at", ""),
            "newer_first_discovered_at": (b or {}).get("first_discovered_at", ""),
            "frozen_last_seen_at": (a or {}).get("last_seen_at", ""),
            "newer_last_seen_at": (b or {}).get("last_seen_at", ""),
            "frozen_trigger_episode_ids_json": canonical((a or {}).get("trigger_episode_ids")),
            "newer_trigger_episode_ids_json": canonical((b or {}).get("trigger_episode_ids")),
            "frozen_trigger_check_labels_json": canonical((a or {}).get("trigger_check_labels")),
            "newer_trigger_check_labels_json": canonical((b or {}).get("trigger_check_labels")),
            "frozen_candidate_json": canonical(a),
            "newer_candidate_json": canonical(b),
        })
    return result, dict(sorted(transitions_count.items()))


def if1008_chronology(state, newer_queue, raw_documents):
    """Preserve actual IF alert/check records; never invent an event-reference join."""
    city_state = (state.get("cities") or {}).get("ivano-frankivsk") or {}
    episodes = city_state.get("episodes") or []
    if not isinstance(episodes, list):
        raise RuntimeError("Invalid Ivano-Frankivsk episode list")
    reference = "IF-1008"
    serialized_matches = {role: reference in canonical(obj)
                          for role, obj in raw_documents.items()}
    history = []
    exact_links = []
    date_hint_ids = []
    for ep in sorted(episodes, key=lambda r: (str(r.get("alert_end") or ""),
                                              str(r.get("episode_id") or ""))):
        eid = str(ep.get("episode_id") or "")
        if reference in canonical(ep):
            exact_links.append(eid)
        matched_candidates = sorted(item["candidate_id"] for item in newer_queue
                                    if eid in (item.get("trigger_episode_ids") or []))
        if "2026-10-08" in (str(ep.get("alert_start") or "")[:10],
                            str(ep.get("alert_end") or "")[:10]):
            date_hint_ids.append(eid)
        history.append({
            "episode_id": eid, "alert_start": ep.get("alert_start"),
            "alert_end": ep.get("alert_end"), "alert_source": ep.get("alert_source"),
            "stored_checks": ep.get("checks"),
            "stored_episode": ep,
            "candidate_ids_with_stored_trigger_reference": matched_candidates,
        })
    return {
        "reference": reference,
        "reference_present_in_each_raw_document": serialized_matches,
        "mapping_status": ("EXPLICIT_EPISODE_REFERENCE" if exact_links
                           else "NOT_STORED_AS_AN_EPISODE_REFERENCE"),
        "identity_is_proven_from_pinned_data": bool(exact_links),
        "explicitly_linked_episode_ids": exact_links,
        "unverified_date_hint": "2026-10-08",
        "date_hint_episode_ids_not_claimed_as_event_matches": sorted(date_hint_ids),
        "scope": "Complete stored Ivano-Frankivsk alert-episode follow-up state",
        "episode_count": len(history),
        "episodes": history,
        "caveat": ("Stored alert episodes and scheduled searches are not a proven "
                   "one-to-one physical-attack or IF-1008 event-reference mapping."),
    }


def deny_network_during_calculation():
    def blocked(*args, **kwargs):
        raise RuntimeError("NETWORK_REQUEST_DURING_OFFLINE_CALCULATION")
    socket.socket = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked


def calculate(out, replay_dir):
    sources = {role: json.loads((out / raw_path).read_bytes())
               for role, _, _, _, raw_path in OBJECTS}
    snapshots = {"frozen": sources["frozen_queue"], "newer": sources["newer_queue"]}
    metrics = {}
    clusters = {}
    for snapshot, rows in snapshots.items():
        metrics[snapshot], clusters[snapshot] = queue_metrics(rows)
    duplicates = duplicate_rows(clusters)
    lookup = candidate_lookup_rows(snapshots)
    deltas, counts = transitions(snapshots["frozen"], snapshots["newer"])
    if len(duplicates) != sum(metrics[s]["duplicate_clusters"] for s in snapshots):
        raise RuntimeError("Duplicate inventory is incomplete")
    if len(lookup) != sum(metrics[s]["candidates"] for s in snapshots):
        raise RuntimeError("Candidate lookup inventory is incomplete")
    write_csv(replay_dir / NORMALIZED[0], CLUSTER_FIELDS, duplicates)
    write_csv(replay_dir / NORMALIZED[1], LOOKUP_FIELDS, lookup)
    write_csv(replay_dir / NORMALIZED[2], TRANSITION_FIELDS, deltas)
    followup = if1008_chronology(sources["newer_monitor_state"],
                                sources["newer_queue"], sources)
    write_json(replay_dir / NORMALIZED[3], followup)
    return {
        "metrics": metrics,
        "expected_metric_matches": {s: metrics[s] == EXPECTED[s] for s in EXPECTED},
        "total_duplicate_rows": len(duplicates),
        "total_candidate_lookup_rows": len(lookup),
        "transition_rows": len(deltas),
        "transition_types": counts,
        "if1008_mapping_status": followup["mapping_status"],
        "if1008_episode_count": followup["episode_count"],
        "normalized_sha256": {name: sha256_file(replay_dir / name)
                              for name in NORMALIZED},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = Path(args.output_dir).resolve()
    if out.exists():
        raise RuntimeError("Proof output directory must not pre-exist")
    out.mkdir(parents=True)
    manifest = extract(repo, out)
    deny_network_during_calculation()
    with tempfile.TemporaryDirectory(prefix="offline-proof-") as base:
        first = Path(base) / "run_a"
        second = Path(base) / "run_b"
        first.mkdir()
        second.mkdir()
        replay_a = calculate(out, first)
        replay_b = calculate(out, second)
        if replay_a != replay_b:
            raise RuntimeError("Offline metric or normalized SHA divergence")
        for name in NORMALIZED:
            if (first / name).read_bytes() != (second / name).read_bytes():
                raise RuntimeError("Offline normalized byte divergence: " + name)
            shutil.copyfile(first / name, out / name)
    replay_proof = {
        "script_purpose": "Two full offline calculations from same four pinned raw files",
        "runs": {"A": replay_a, "B": replay_b},
        "identical_metrics": replay_a["metrics"] == replay_b["metrics"],
        "identical_row_counts": replay_a["total_duplicate_rows"] == replay_b["total_duplicate_rows"]
                                and replay_a["total_candidate_lookup_rows"] == replay_b["total_candidate_lookup_rows"],
        "identical_normalized_bytes": True, "identical_normalized_sha256": True,
        "all_expected_metrics_match": all(replay_a["expected_metric_matches"].values()),
        "source_github_commit": os.environ.get("GITHUB_SHA"),
        "source_github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "calculation_network_requests": 0,
        "no_external_event_mapping_or_public_source_research": True,
    }
    write_json(out / "reproduction_results.json", replay_proof)
    explanation = (
        "# Casualty 25-event raw Git evidence proof\n\n"
        "Scope: byte-for-byte export of four named, pinned Git blobs and two "
        "independent offline calculations. This is NOT a complete v3 or 25-event "
        "coverage audit. No 23-city population-wide recall is claimed.\n\n"
        "Four raw JSON files in raw/ are git cat-file blob outputs, with blob "
        "identities, SHA-256 hashes, byte lengths and historical paths recorded "
        "in blob_manifest.json. Original raw bytes were not rewritten.\n\n"
        "duplicate_clusters_complete.csv: one row per snapshot-specific city "
        "and stored RSS URL cluster containing two or more candidates.\n"
        "candidate_lookup_complete.csv: one row per candidate per frozen/newer "
        "snapshot, retaining original stored RSS URLs, publisher and trigger "
        "provenance.\n"
        "candidate_transitions.csv: changed, added and removed candidate records, "
        "including before/after JSON.\n"
        "if1008_followup.json: exact stored Ivano-Frankivsk episode/check history "
        "and candidate trigger references. IF-1008 is an external event reference: "
        "unless an explicit join exists in the pinned files, no episode is "
        "claimed as the unique IF-1008 attack. A date hint is not identity proof.\n\n"
        "reproduction_results.json records both complete offline calculations, "
        "metric assertions, file hashes, and byte equality. "
        "checksums.sha256 covers every other payload file in this artifact.\n\n"
        "Production, review queues, Git refs, ledgers, dashboards and Neon "
        "were not modified by this proof workflow.\n"
    )
    (out / "README.md").write_bytes(explanation.encode("utf-8"))
    names = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()
                   and p.name != "checksums.sha256")
    (out / "checksums.sha256").write_text(
        "".join(sha256_file(out / name) + "  " + name + "\n" for name in names),
        encoding="utf-8", newline="\n")
    print("RAW_GIT_BLOBS_VERIFIED", len(manifest["objects"]))
    for obj in manifest["objects"]:
        print(obj["role"], "blob", obj["git_blob_expected"],
              "sha256", obj["sha256"], "bytes", obj["byte_length"])
    print("OFFLINE_REPRODUCTION_IDENTICAL", replay_proof["identical_normalized_bytes"])
    print("EXPECTED_METRICS_MATCH", replay_proof["all_expected_metrics_match"])
    print("METRICS", canonical(replay_a["metrics"]))
    print("INVENTORY", replay_a["total_duplicate_rows"],
          replay_a["total_candidate_lookup_rows"],
          replay_a["transition_rows"])
    print("IF1008_MAPPING", replay_a["if1008_mapping_status"])
    print("PAYLOAD_FILE_COUNT", len(names) + 1)


if __name__ == "__main__":
    main()
