#!/usr/bin/env python3
"""Read-only, offline reproduction of the Zaporizhzhia WIP coverage inventory.

No publisher HTTP, no data mutation. Run from a Git checkout containing both
frozen commits (fetch 'multicity-wip-2026-09-16' and 'site-prod' if needed).
This verifies *inventory and monitoring receipts*, NOT the completeness
of Google News or the 23-death publisher article evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

WIP_SHA = "c66c242a852d7647b6183425228cb3db2d1d088b"
PROD_SHA = "fc7261660bdee75ee59296ee94cc1189be6b1a22"
ROOT = "kyiv-air-alerts-grafana/data/casualties/"
EXPECTED_HASHES = {
    "queue": "3d9133d178d229d5356e1939db827411f8b2af21a4b72766c16c214933da0d8d",
    "monitor_state": "2088be30621f623b6874c37395ece36ca5f22c04e593bc5227be78d854e966f2",
    "last_run": "8f815ea4d04b9ef9ab0b9bf0194211857983870ef8c16ffa134d5ffdf5afc71d",
    "city_manifest": "141e95e95caff7b4a03c41936a465d07bd82fc1741dc17f972cc6a635f0f9da5",
}


def pinned_read(commit: str, path: str, label: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", commit + ":" + path],
        capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Missing pinned Git object " + commit + ":" + path
            + "; fetch WIP and site-prod branches first. "
            + completed.stderr.decode("utf-8", "replace")[:300]
        )
    content = completed.stdout
    observed = hashlib.sha256(content).hexdigest()
    assert observed == EXPECTED_HASHES[label], (label, observed)
    return content


def verify() -> dict:
    queue_blob = pinned_read(WIP_SHA, ROOT + "multicity_review_queue.json", "queue")
    state_blob = pinned_read(WIP_SHA, ROOT + "candidate_monitor_state.json", "monitor_state")
    last_blob = pinned_read(WIP_SHA, ROOT + "candidate_monitor_last_run.json", "last_run")
    city_blob = pinned_read(PROD_SHA, ROOT + "cities/zaporizhzhia/manifest.json", "city_manifest")

    queue = json.loads(queue_blob)
    state = json.loads(state_blob)
    last_run = json.loads(last_blob)
    city_manifest = json.loads(city_blob)
    inventory = json.loads(Path(__file__).with_name("candidate_inventory.json").read_text(encoding="utf-8"))

    assert city_manifest["validated_through"] == "2026-09-18"
    city_rows = [x for x in queue if x.get("city_key") == "zaporizhzhia"]
    in_window = [
        x for x in city_rows
        if "2026-09-19" <= x["published_at"][:10] <= "2026-10-31"
    ]
    assert len(queue) == 1678 and len(city_rows) == 208
    assert len(in_window) == 197
    assert sum(x["published_at"].startswith("2026-09") for x in in_window) == 63
    assert sum(x["published_at"].startswith("2026-10") for x in in_window) == 134
    assert all(x["status"] == "needs_review" for x in city_rows)
    assert len(set(x["url"] for x in city_rows)) == 166
    assert len(set(x["url"] for x in in_window)) == 155

    line_map = {}
    for line_no, raw_line in enumerate(queue_blob.decode("utf-8").splitlines(), start=1):
        match = re.match(r'\s*"candidate_id": "([a-f0-9]{24})"', raw_line)
        if match:
            line_map[match.group(1)] = line_no

    rows_in_index = inventory["candidate_rows"]
    assert len(rows_in_index) == len(city_rows)
    assert len({x["candidate_id"] for x in rows_in_index}) == 208
    by_id = {x["candidate_id"]: x for x in city_rows}
    for item in rows_in_index:
        original = by_id[item["candidate_id"]]
        for idx_field, orig_field in (
            ("status_in_wip", "status"),
            ("published_at", "published_at"),
            ("publisher", "publisher"),
            ("title", "title"),
            ("original_wip_rss_url", "url"),
            ("wip_snippet", "snippet"),
            ("first_discovered_at", "first_discovered_at"),
            ("last_seen_at", "last_seen_at"),
        ):
            assert item[idx_field] == original[orig_field], (item["candidate_id"], idx_field)
        assert item["wip_queue_line"] == line_map[item["candidate_id"]]
        expected_window = "2026-09-19" <= original["published_at"][:10] <= "2026-10-31"
        assert item["published_in_screening_window"] == expected_window

    z_state = state["cities"]["zaporizhzhia"]
    episodes = [
        ep for ep in z_state["episodes"]
        if "2026-09-19" <= ep["alert_end"][:10] <= "2026-10-31"
    ]
    checks = [c for ep in episodes for c in ep["checks"]]
    check_days = {c["checked_at"][:10] for c in checks if c.get("checked_at")}
    assert len(episodes) == 191 and len(checks) == 764
    assert all(c.get("checked_at") for c in checks)
    assert len(check_days) == 42
    assert min(check_days) == "2026-09-27"
    assert max(check_days) == "2026-11-07"
    assert last_run["mode"] == "local_only"
    assert "zaporizhzhia" in last_run["cities_searched"]
    assert last_run["searches"]["zaporizhzhia"]["due_checks"] == 7
    assert "when%3A8d" in last_run["searches"]["zaporizhzhia"]["query_url"]

    return {
        "inventory_verified": True,
        "wip_sha": WIP_SHA,
        "production_sha": PROD_SHA,
        "queue_candidates_total": len(queue),
        "zaporizhzhia_city_tagged": len(city_rows),
        "screening_window_published": len(in_window),
        "sept_published": 63,
        "oct_published": 134,
        "wip_unresolved_city_tagged": 208,
        "zaporizhzhia_alert_episodes_with_checks": len(episodes),
        "recorded_checks": len(checks),
        "unique_check_days": len(check_days),
        "checked_days_start": min(check_days),
        "checked_days_end": max(check_days),
        "site_baseline_validated_through": city_manifest["validated_through"],
        "coverage_completeness_proven": False,
        "monthly_total_from_this_script": None,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
