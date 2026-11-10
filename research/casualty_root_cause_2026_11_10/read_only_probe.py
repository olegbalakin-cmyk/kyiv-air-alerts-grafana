#!/usr/bin/env python3
"""Bounded offline diagnostics. No network; no REVIEW/PROMOTE; inputs never written.

Run from the scratch snapshot root containing evidence/:
    python research/casualty_root_cause_2026_11_10/read_only_probe.py
The authoritative input refs/blobs are recorded in input_manifest.json.
"""
import ast
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EVIDENCE = BASE / "evidence"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_read_only_definitions(path):
    # Source bodies are unchanged. Remove unavailable network adapters/imports
    # and the __main__ invocation; call only local loaders and pure functions.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dropped = {"requests", "add_sevastopol_exact", "apply_ukrainealarm_bridge", "update_data"}
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import) and any(a.name in dropped for a in node.names):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "bs4":
            continue
        if isinstance(node, ast.If):
            continue
        body.append(node)
    namespace = {"__file__": str(path), "__name__": "read_only_definitions"}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def main():
    wip = EVIDENCE / "multicity-wip-2026-09-16/kyiv-air-alerts-grafana"
    prod = EVIDENCE / "site-prod/kyiv-air-alerts-grafana"
    queue_path = wip / "data/casualties/multicity_review_queue.json"
    state_path = wip / "data/casualties/candidate_monitor_state.json"
    revision_path = prod / "data/casualties/revisions.csv"
    protected = [queue_path, state_path, revision_path]
    before = {str(p.relative_to(BASE)): digest(p) for p in protected}
    queue = json.loads(queue_path.read_text())
    state = json.loads(state_path.read_text())
    dashboard = json.loads((EVIDENCE / "git_dashboard.json").read_text())
    cases = json.loads((OUT / "cases.json").read_text())
    by_id = {x["candidate_id"]: x for x in queue}
    monitor = load_read_only_definitions(wip / "scripts/monitor_casualty_candidates.py")
    generator = load_read_only_definitions(prod / "scripts/update_casualties.py")

    baseline = generator["load_baseline"]()
    generator["validate_baseline"](baseline)
    revisions = generator["load_revisions"]()
    routes = generator["city_baseline_routes"]()
    all_city_series = generator["load_validated_city_series"]()
    replay = {}
    for city, route in routes.items():
        if city == "kyiv":
            monthly = generator["build_monthly"](baseline, revisions, city_key=city)
        else:
            monthly = generator["apply_city_revision_overlay"](all_city_series[city], revisions, city)["monthly"]
        published = dashboard["casualties_by_city"][city]["monthly"]
        assert monthly == published, city
        replay[city] = {"route": route, "monthly_matches_published": True,
                        "last_month": monthly[-1]["month"],
                        "total_deaths": sum(x["deaths"] for x in monthly)}

    traces = []
    for case in cases:
        items = [by_id[cid] for cid in case["candidate_ids"]]
        first = min(items, key=lambda x: x["first_discovered_at"])
        retained = {e["episode_id"]: e for e in state["cities"][case["city_key"]]["episodes"]}
        episode_ids = first.get("trigger_episode_ids", [])
        links = [retained[eid] for eid in episode_ids if eid in retained]
        day_episodes = [e for e in retained.values()
                        if e["alert_start"][:10] <= case["attack_date"] <= e["alert_end"][:10]]
        matched_revisions = [r["record_id"] for r in revisions
                             if r["city_key"] == case["city_key"]
                             and r["attack_date"].isoformat() == case["attack_date"]]
        sample_candidates = []
        for item in items:
            published = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            discovered = datetime.fromisoformat(item["first_discovered_at"].replace("Z", "+00:00"))
            combined = item["title"] + " " + (item.get("snippet") or "")
            sample_candidates.append({
                "candidate_id": item["candidate_id"], "status": item["status"],
                "publisher": item["publisher"], "published_at": item["published_at"],
                "first_discovered_at": item["first_discovered_at"],
                "rss_timestamp_to_discovery_hours": round((discovered-published).total_seconds()/3600, 3),
                "passes_local_geography_lexical_filter": monitor["city_mentioned"](case["city_key"], combined),
                "passes_local_casualty_aerial_filter": monitor["relevant_news"](combined),
            })
        traces.append({"case_id": case["id"], "city_key": case["city_key"],
                       "candidate_count_selected": len(items), "candidates": sample_candidates,
                       "first_discovered_at": first["first_discovered_at"],
                       "first_selected_candidate_trigger_count": len(episode_ids),
                       "retained_trigger_count": len(links),
                       "retained_trigger_date_span": [min((x["alert_start"] for x in links), default=None),
                                                       max((x["alert_end"] for x in links), default=None)],
                       "city_episodes_touching_attack_date_utc": len(day_episodes),
                       "causal_alert_match": "UNKNOWN: trigger IDs are a union of due searches, not causal matches",
                       "revision_record_ids": matched_revisions,
                       "published_attack_month_present": any(x["month"] == case["attack_date"][:7]
                           for x in dashboard["casualties_by_city"][case["city_key"]]["monthly"])})

    groups = collections.defaultdict(list)
    for item in queue:
        groups[(item["city_key"], item["title"].strip().casefold())].append(item["candidate_id"])
    duplicate_groups = [ids for ids in groups.values() if len(ids) > 1]

    # Pure synthetic scheduling/provenance probes; no real candidate objects used.
    now = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    assert monitor["due_checks"]({"cities": {"odesa": {"episodes": []}}}, now) == {}
    make = monitor["make_episode"]
    e1 = make("odesa", datetime(2026,11,8,7,tzinfo=timezone.utc),
              datetime(2026,11,8,8,tzinfo=timezone.utc), "SYNTHETIC")
    e2 = make("odesa", datetime(2026,11,9,7,tzinfo=timezone.utc),
              datetime(2026,11,9,8,tzinfo=timezone.utc), "SYNTHETIC")
    scratch = []
    monitor["add_news_candidates"](scratch, "odesa", [{"title":"SYNTHETIC fixture",
        "url":"https://example.invalid/offline-fixture"}], [(e1,e1["checks"][0]),(e2,e2["checks"][0])], now)
    assert len(scratch[0]["trigger_episode_ids"]) == 2
    after = {str(p.relative_to(BASE)): digest(p) for p in protected}
    assert before == after, "Authoritative input changed"
    summary = {
        "queue_count": len(queue), "queue_statuses": dict(collections.Counter(x["status"] for x in queue)),
        "queue_city_counts": dict(collections.Counter(x["city_key"] for x in queue)),
        "same_city_exact_title_duplicate_groups": len(duplicate_groups),
        "excess_records_in_exact_title_groups": sum(len(ids)-1 for ids in duplicate_groups),
        "selected_duplicate_groups": [ids for ids in duplicate_groups if
            any(cid in {"5b66f06ed9aa6654861618be","93607059f26871023b56195f"} for cid in ids)],
        "generator_actual_ledger_replay": replay,
        "confirmed_revisions_total": len([x for x in revisions if x["status"] == "confirmed"]),
        "case_traces": traces,
        "synthetic_probes": {"no_episodes_no_due_search": True, "candidate_gets_all_due_episode_ids": True},
        "input_sha256_before": before, "input_sha256_after": after, "inputs_unchanged": before == after,
        "scope": "No network, no live candidate status changes, no REVIEW/PROMOTE or generator main invocation."
    }
    (OUT / "offline_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"queue":summary["queue_statuses"], "generator_city_replays":len(replay),
        "duplicate_groups":len(duplicate_groups), "duplicate_excess":summary["excess_records_in_exact_title_groups"],
        "unchanged_inputs":summary["inputs_unchanged"],
        "cases":[{k:x[k] for k in ["case_id","first_discovered_at","city_episodes_touching_attack_date_utc","first_selected_candidate_trigger_count"]}
                 for x in traces]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
