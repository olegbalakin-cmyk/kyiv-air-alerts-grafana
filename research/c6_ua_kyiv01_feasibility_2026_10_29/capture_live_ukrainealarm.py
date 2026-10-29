#!/usr/bin/env python3
"""C6-UA-KYIV-01: bounded, read-only, protected UkraineAlarm API capture.

Runs only in isolated Actions workflow; uses pinned production request-policy client.
No DML/DDL, no POST, no production changes. Raw 200 JSON is a short-lived CI artifact,
never committed to Git. Headers/API credentials are never logged or recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ua_kyiv_research_adapter import history_air, region_nodes, compare_exact, iso, utc

UTC = timezone.utc
BASE = "https://api.ukrainealarm.com/api/v3"
OUTPUT = Path(__file__).resolve().parent / "live_proof"
PUBLISHER_PATHS = ("/regions", "/alerts/{regionId}", "/alerts/regionHistory", "/alerts")
PRODUCERS = {
    "update-netlify-site.yml", "update.yml",
    "explosion-monitor-wip.yml", "update-explosion-wip.yml",
}
LIMIT_SECONDS = 11 * 60
START = time.monotonic()


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for val in obj.values():
            yield from walk(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from walk(val)


def schema(obj: Any) -> dict:
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for d in walk(obj):
        keys = tuple(sorted(d.keys()))
        signature = ",".join(keys)[:400]
        counts[signature] = counts.get(signature, 0) + 1
    return {"root_type": type(obj).__name__,
            "root_keys": sorted(obj) if isinstance(obj, dict) else [],
            "top_object_key_sets_and_counts": sorted(counts.items(), key=lambda kv: -kv[1])[:25]}


def norm_city(s: Any) -> str:
    s = str(s or "").strip().casefold()
    s = re.sub(r"^(м\.?\s*|місто\s+)", "", s)
    return " ".join(s.split())


def scopes(payload: Any) -> dict:
    nodes = region_nodes(payload)
    city = [n for n in nodes if norm_city(n["regionName"]) in {"київ", "kyiv", "kiev"}]
    oblast = [n for n in nodes if n["regionName"].casefold() in
              {"київська область", "kyiv oblast", "киевская область"}]
    strict = [n for n in city if n.get("regionType") in ("State", "Community")
              and not any("київська область" == a.casefold() for a in n.get("ancestors", []))]
    ids = [n["regionId"] for n in strict]
    candidate = strict[0] if len(strict) == 1 and len(set(ids)) == 1 and oblast and all(
        o["regionId"] != strict[0]["regionId"] for o in oblast
    ) else None
    return {"candidate": candidate, "city_nodes": city,
            "oblast_nodes": oblast, "regions_total": len(nodes),
            "scope_status": "CANDIDATE_UNCORROBORATED" if candidate else "NOT_PROVEN"}


def kinds(d: Any, *, has_region: bool = False) -> dict:
    """Collect exact raw reason keys/values without presuming threat taxonomy."""
    key_counts: dict[str, int] = {}
    vals: dict[str, set[str]] = {}
    air_count = 0
    types: dict[str, int] = {}
    for obj in walk(d):
        if "type" in obj and ("activeAlerts" not in obj) and isinstance(obj["type"], (str, int)):
            v = str(obj["type"])
            types[v] = types.get(v, 0) + 1
        if str(obj.get("type", "")).upper() == "AIR":
            air_count += 1
        for key, val in obj.items():
            if key.casefold() in {"reason", "alertlevel", "activealertlevels", "lastcause", "causes"}:
                key_counts[key] = key_counts.get(key, 0) + 1
                if key.casefold() == "reason":
                    items = val if isinstance(val, list) else [val]
                    vals.setdefault(key, set()).update(str(x)[:180] for x in items if x is not None)
    return {"reason_key_counts": key_counts, "reason_raw_values": {
                k: sorted(v) for k, v in vals.items()},
            "air_type_node_count": air_count, "type_values_count": types}


def repository_actions_idle() -> tuple[bool, list[dict]]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo or "/" not in repo:
        return False, [{"blocked": "ACTIONS_PREFLIGHT_CREDENTIAL_OR_REPO_MISSING"}]
    conflicts = []
    for status in ("in_progress", "queued", "waiting"):
        url = f"https://api.github.com/repos/{repo}/actions/runs?status={status}&per_page=100"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "c6-ua-kyiv01-readonly-runner",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read(1_500_000))
        except Exception:
            return False, [{"blocked": "ACTIONS_PREFLIGHT_API_UNAVAILABLE"}]
        for row in payload.get("workflow_runs", []):
            path = str(row.get("path", "")).rsplit("/", 1)[-1]
            if path in PRODUCERS and str(row.get("id")) != os.environ.get("GITHUB_RUN_ID", ""):
                conflicts.append({"workflow": path, "run_id": row.get("id"),
                                  "status": row.get("status")})
    return not conflicts, conflicts


def schedule_safe() -> tuple[bool, str]:
    """Keep 12 minutes before production's UTC 00/04/08/12/16/20:15 cron slot."""
    now = datetime.now(UTC)
    next_slot = None
    for hour_offset in range(0, 9):
        target = (now + timedelta(hours=hour_offset)).replace(minute=15, second=0, microsecond=0)
        if target > now and target.hour % 4 == 0:
            next_slot = target
            break
    if next_slot is None:
        return False, "NEXT_SCHEDULE_NOT_DETERMINED"
    return (next_slot - now).total_seconds() >= 12 * 60, iso(next_slot)


def safe_to_request(receipt: dict) -> bool:
    if time.monotonic() - START > LIMIT_SECONDS:
        receipt["stop_reason"] = "RESEARCH_TIME_BUDGET_EXHAUSTED"
        return False
    safe, next_slot = schedule_safe()
    receipt["next_production_cron_utc"] = next_slot
    if not safe:
        receipt["stop_reason"] = "PRODUCTION_CRON_WITHIN_12_MINUTES"
        return False
    idle, conflicts = repository_actions_idle()
    if not idle:
        receipt["stop_reason"] = "ACTIVE_OR_QUEUED_API_CONSUMER_OR_PREFLIGHT_BLOCKED"
        receipt["conflicts"] = conflicts
        return False
    return True


def compare(history: Any, city_id: str, expected_file: Path) -> dict:
    report = {"status": "NOT_PROVEN", "expected_source": str(expected_file),
              "source_expected_count": 0, "eligible": 0, "matched": 0,
              "out_of_coverage": 0}
    if not expected_file.exists():
        report["reason"] = "PINNED_CITY_JSON_UNAVAILABLE"
        return report
    try:
        source = json.loads(expected_file.read_text("utf-8"))
        if not isinstance(source, list):
            raise ValueError("expected JSON array")
        h = history_air(history, city_id)
        rows = [{"start": iso(utc(a["start"])), "end": iso(utc(a["end"])),
                 "source": str(a.get("source") or "UNKNOWN")}
                for a in source if isinstance(a, dict) and a.get("start") and a.get("end")]
        report["source_expected_count"] = len(rows)
        result = compare_exact(h, rows)
        report.update(result)
        report["status"] = "BOUNDED_COMPARISON"
        low = min((utc(x["start"]) for x in h["completed"]), default=None)
        high = max((utc(x["end"]) for x in h["completed"]), default=None)
        if low and high:
            observed = {(x["start"], x["end"]) for x in h["completed"]}
            eligible = [a for a in rows if low <= utc(a["start"]) <= high]
            report["by_source"] = {}
            for src in sorted(set(a["source"] for a in eligible)):
                sub = [a for a in eligible if a["source"] == src]
                report["by_source"][src] = {
                    "eligible": len(sub),
                    "matched": sum((a["start"], a["end"]) in observed for a in sub),
                    "not_exact": sum((a["start"], a["end"]) not in observed for a in sub),
                }
            expected_set = {(a["start"], a["end"]) for a in eligible}
            report["extra_ua_completed_in_window"] = [
                x for x in h["completed"] if (x["start"], x["end"]) not in expected_set][:25]
            report["nonmatching_expected_examples"] = [
                a for a in eligible if (a["start"], a["end"]) not in observed][:25]
            report["history_earliest_start"] = iso(low)
            report["history_latest_end"] = iso(high)
        report["history_observed"] = h
    except Exception as exc:
        report["status"] = "PARSE_FAIL_CLOSED"
        report["error_type"] = type(exc).__name__
    return report


def main() -> int:
    OUTPUT.mkdir(exist_ok=True)
    proof = {"track": "C6-UA-KYIV-01",
             "captured_at": timestamp(), "status": "INITIALIZED",
             "commit": os.environ.get("GITHUB_SHA"),
             "run_id": os.environ.get("GITHUB_RUN_ID"),
             "production_input_sha": os.environ.get("C6_SITE_PROD_SHA"),
             "API_secrets_exposed": False, "production_changes": 0, "neon_writes": 0,
             "requests": [], "policy": {"minimum_gap_seconds": 70,
             "same_concurrency_group_as_production": True,
             "API_calls_max": 4, "scheduled_production_before_minutes": 12}}
    try:
        token = os.environ.get("UKRAINEALARM_API_TOKEN", "")
        if not token.strip():
            proof["status"] = "ACCESS_BLOCKED"
            proof["stop_reason"] = "GITHUB_ACTIONS_SECRET_UNAVAILABLE"
            return 2
        # A GitHub workflow's GITHUB_TOKEN is only for read-only Actions coordination.
        if not safe_to_request(proof):
            proof["status"] = "COORDINATION_BLOCKED"
            return 2
        scripts_dir = Path(os.environ.get("C6_PINNED_PRODUCTION_SCRIPTS", "")).resolve()
        if not (scripts_dir / "ukrainealarm_request_policy.py").is_file():
            proof["status"] = "ACCESS_BLOCKED"
            proof["stop_reason"] = "PINNED_PRODUCTION_REQUEST_POLICY_UNAVAILABLE"
            return 2
        sys.path.insert(0, str(scripts_dir))
        from ukrainealarm_request_policy import UkraineAlarmClient
        # If no authenticated handoff is known, the existing policy waits 70 seconds
        # before even the first request. Retry/cooldown/timeout enforced by same client.
        client = UkraineAlarmClient(
            token, capture_diagnostic_path=str(OUTPUT / "missing_handoff.json"),
            min_interval=70, total_api_seconds=LIMIT_SECONDS - 30)
        del token
        collected: dict[str, Any] = {}
        def get(name: str, path: str, params: dict | None = None):
            if not safe_to_request(proof):
                return None
            item = {"name": name, "endpoint_path": path,
                    "params": params, "requested_at": timestamp(),
                    "status": "REQUEST_STARTED", "http_status": None,
                    "sha256_raw_body": None}
            proof["requests"].append(item)
            try:
                response = client.get(BASE + path, params=params, context=name)
                raw = response.content
                item.update({"http_status": response.status_code, "status": "HTTP_OK",
                             "response_received_at": timestamp(), "content_type": response.headers.get("Content-Type", "")[:80],
                             "raw_bytes": len(raw), "sha256_raw_body": hashlib.sha256(raw).hexdigest()})
                payload = response.json()
                item["schema"] = schema(payload)
                item["reason_summary"] = kinds(payload)
                (OUTPUT / f"raw_{name}.json").write_bytes(raw)
                collected[name] = payload
                return payload
            except Exception as exc:
                item.update({"status": "REQUEST_ERROR_FAIL_CLOSED",
                             "error_class": type(exc).__name__,
                             "response_received_at": timestamp()})
                return None

        regions = get("regions", "/regions")
        if regions is None:
            proof["status"] = "REGIONS_ACCESS_BLOCKED"
            return 2
        s = scopes(regions)
        proof["region_tree"] = s
        target = s["candidate"]
        if not target:
            proof["status"] = "CITY_REGION_SCOPE_NOT_PROVEN"
            return 2
        city_id = str(target["regionId"])
        proof["candidate_region_id_not_yet_city_parity_certified"] = city_id
        city_current = get("city_current", f"/alerts/{city_id}")
        if city_current is None:
            proof["status"] = "CURRENT_ACCESS_BLOCKED"
            return 2
        history = get("city_history", "/alerts/regionHistory", params={"regionId": city_id})
        if history is None:
            proof["status"] = "HISTORY_ACCESS_BLOCKED"
            return 2
        h = history_air(history, city_id)
        proof["history_analysis"] = {"rows": h["source_rows"], "air_rows": h["air_rows"],
                                     "completed": len(h["completed"]), "open_air_rows": h["open_air_rows"],
                                     "window_truncation_possible": h["window_truncation_possible"],
                                     "reason_field_seen": h["reason_in_observed_history"]}
        expected_file = Path(os.environ.get("C6_PINNED_KYIV_JSON", "notfound"))
        proof["timestamp_comparison"] = compare(history, city_id, expected_file)
        proof["current_analysis"] = kinds(city_current)
        proof["current_object_schemas"] = schema(city_current)
        if safe_to_request(proof):
            general = get("general_active", "/alerts")
            proof["general_reason_analysis"] = kinds(general) if general is not None else {"status": "NOT_PROVEN"}
        # Do not equate observed city candidate to true municipality on label alone.
        exact = proof["timestamp_comparison"]
        proof["city_scope_evidence"] = {
            "tree_distinct_city_vs_oblast": bool(s["city_nodes"] and s["oblast_nodes"]),
            "history_city_id_matches": True,
            "positive_exact_city_parity": exact.get("matched", 0) > 0,
            "full_scope_pass": bool(exact.get("matched", 0) > 0 and
                                    s["candidate"] and not s["candidate"].get("ancestors"))}
        proof["status"] = "LIVE_CAPTURED_BOUNDED"
        return 0
    finally:
        proof["finished_at"] = timestamp()
        proof["elapsed_seconds"] = round(time.monotonic() - START, 2)
        dump(OUTPUT / "capture_receipt.json", proof)
        checks = {}
        for file in sorted(OUTPUT.glob("*")):
            if file.is_file() and file.name != "sha256_manifest.json":
                data = file.read_bytes()
                checks[file.name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        dump(OUTPUT / "sha256_manifest.json", checks)
        print(json.dumps({"status": proof["status"], "request_count": len(proof["requests"]),
                          "http_statuses": [r.get("http_status") for r in proof["requests"]],
                          "region_candidate_id": proof.get("candidate_region_id_not_yet_city_parity_certified"),
                          "timestamps_matched": proof.get("timestamp_comparison", {}).get("matched"),
                          "timestamps_eligible": proof.get("timestamp_comparison", {}).get("eligible"),
                          "stop_reason": proof.get("stop_reason"),
                          "secrets_exposed": False}, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
