#!/usr/bin/env python3
"""Fail-closed, read-only checks for pinned production UkraineAlarm snapshots.

This validator never performs HTTP, changes monitoring state, or opens a database.
The production bridge is a regional/raion observation source, not city-level
attribution proof. Episode grouping remains in monitor_explosion_candidates.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
MAX_SOURCE_AGE = timedelta(hours=12)
EXPECTED_REGIONS = frozenset((
    "kharkiv", "zaporizhzhia", "cherkasy", "zhytomyr", "dnipro",
    "khmelnytskyi", "poltava", "rivne", "sumy", "vinnytsia",
    "kropyvnytskyi", "lviv", "chernihiv", "odesa", "kherson",
    "mykolaiv", "lutsk", "uzhhorod", "ivano_frankivsk",
    "ternopil", "chernivtsi",
))
EXACT_REGION_KEYS = frozenset(("kharkiv", "zaporizhzhia"))
SPECIAL_CITY_KEYS = frozenset(("kyiv", "sevastopol"))
EXPECTED_SOURCE_URL = "https://api.ukrainealarm.com/api/v3/alerts/regionHistory"


class CachedSnapshotError(RuntimeError):
    """Rejected production alert snapshot; consuming must not write anything."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CachedSnapshotError(message)


def aware_timestamp(value, where: str) -> datetime:
    require(isinstance(value, str) and bool(value.strip()), f"{where}: missing timestamp")
    require(bool(re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", value)), f"{where}: timezone is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise CachedSnapshotError(f"{where}: malformed timestamp") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{where}: naive timestamp")
    return parsed.astimezone(UTC)


def fresh_timestamp(value, where: str, now: datetime) -> tuple[str, float]:
    stamp = aware_timestamp(value, where)
    age = now - stamp
    require(age >= timedelta(0), f"{where}: future timestamp")
    require(age <= MAX_SOURCE_AGE, f"{where}: older than strict 12-hour limit")
    return stamp.isoformat().replace("+00:00", "Z"), round(age.total_seconds() / 3600, 6)


def read_json_file(path: Path, where: str):
    require(path.is_file(), f"{where}: file missing")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CachedSnapshotError(f"{where}: cannot read") from exc
    try:
        payload = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CachedSnapshotError(f"{where}: invalid JSON") from exc
    return payload, hashlib.sha256(data).hexdigest(), len(data)


def check_completed_intervals(rows, where: str, *, city_key: str | None = None) -> int:
    require(isinstance(rows, list) and bool(rows), f"{where}: missing or empty interval list")
    seen = set()
    for idx, row in enumerate(rows):
        prefix = f"{where}[{idx}]"
        require(isinstance(row, dict), f"{prefix}: not an object")
        start = aware_timestamp(row.get("start"), prefix + ".start")
        end = aware_timestamp(row.get("end"), prefix + ".end")
        require(end > start, f"{prefix}: non-positive interval")
        key = (start, end)
        require(key not in seen, f"{prefix}: duplicate interval")
        seen.add(key)
    return len(rows)


def validate_snapshot(
    bridge_path: Path,
    kyiv_path: Path,
    sevastopol_path: Path,
    *,
    now: datetime,
    source_commit_sha: str | None = None,
) -> dict:
    """Validate all three inputs before any observable monitor/persistence action."""
    require(now.tzinfo is not None and now.utcoffset() is not None, "now must be timezone aware")
    now = now.astimezone(UTC)
    if source_commit_sha is not None:
        require(bool(re.fullmatch(r"[0-9a-f]{40}", source_commit_sha)), "invalid pinned site-prod commit")
    bridge, bridge_hash, bridge_size = read_json_file(bridge_path, "bridge")
    kyiv, kyiv_hash, kyiv_size = read_json_file(kyiv_path, "kyiv_exact_city")
    sev, sev_hash, sev_size = read_json_file(sevastopol_path, "sevastopol_exact_city")

    require(isinstance(bridge, dict), "bridge: not an object")
    require(type(bridge.get("schema_version")) is int and bridge["schema_version"] == 3, "bridge: unexpected schema")
    require(bridge.get("source_url") == EXPECTED_SOURCE_URL, "bridge: unexpected source")
    require(bridge.get("last_fetch_error") is None, "bridge: last_fetch_error is non-null")
    checkpoint, global_age = fresh_timestamp(bridge.get("last_successful_fetch_at"), "global checkpoint", now)
    checkpoint_dt = aware_timestamp(checkpoint, "global checkpoint")
    regions = bridge.get("regions")
    require(isinstance(regions, dict), "bridge: missing regions object")
    require(set(regions) == EXPECTED_REGIONS, "bridge: required 21-region coverage differs")
    regional = {}
    for key in sorted(EXPECTED_REGIONS):
        region = regions[key]
        require(isinstance(region, dict), f"{key}: missing region object")
        require(region.get("city_key") == key, f"{key}: region key mismatch")
        expected_kind = "exact" if key in EXACT_REGION_KEYS else "proxy"
        require(region.get("kind") == expected_kind, f"{key}: exact/proxy contract mismatch")
        region_id = region.get("region_id")
        require(isinstance(region_id, str) and region_id.isdecimal(), f"{key}: invalid region_id")
        require(isinstance(region.get("api_region_name"), str) and region["api_region_name"], f"{key}: no API identity")
        require(region.get("continuous") is True, f"{key}: history not continuous")
        require(region.get("poll_overlap_verified") is True, f"{key}: history overlap not verified")
        require(region.get("last_error") is None, f"{key}: regional fetch error")
        stamp, age = fresh_timestamp(region.get("last_checked_at"), key + ".last_checked_at", now)
        require(aware_timestamp(stamp, key) <= checkpoint_dt, f"{key}: regional check later than global success")
        regional[key] = {
            "region_id": region_id,
            "kind": expected_kind,
            "continuous": True,
            "poll_overlap_verified": True,
            "last_checked_at": stamp,
            "age_hours": age,
            "fresh": True,
        }
    events = bridge.get("events")
    require(isinstance(events, list) and bool(events), "bridge: missing events")
    require(type(bridge.get("event_count")) is int and bridge["event_count"] == len(events),
            "bridge: event_count mismatch")
    seen_events = set()
    event_counts = {key: 0 for key in EXPECTED_REGIONS}
    for idx, item in enumerate(events):
        where = f"bridge.events[{idx}]"
        require(isinstance(item, dict), f"{where}: not an object")
        key = item.get("city_key")
        require(isinstance(key, str) and key in EXPECTED_REGIONS, f"{where}: invalid city_key")
        require(item.get("region_id") == regional[key]["region_id"], f"{where}: region_id mismatch")
        require(item.get("alert_type") == "AIR", f"{where}: invalid alert_type")
        start = aware_timestamp(item.get("start"), where + ".start")
        end = aware_timestamp(item.get("end"), where + ".end")
        require(end > start, f"{where}: non-positive interval")
        require(end <= checkpoint_dt, f"{where}: interval finishes after checkpoint")
        eid = (key, start, end, "AIR")
        require(eid not in seen_events, f"{where}: duplicate event identity")
        seen_events.add(eid)
        event_counts[key] += 1
    require(all(event_counts.values()), "bridge: missing regional event observations")
    require(isinstance(kyiv, list), "kyiv_exact_city: expected list")
    kyiv_count = check_completed_intervals(kyiv, "kyiv_exact_city")
    require(isinstance(sev, dict), "sevastopol_exact_city: expected object")
    seva_count = check_completed_intervals(sev.get("pairs"), "sevastopol_exact_city")
    require(isinstance(sev.get("meta"), dict), "sevastopol_exact_city: no metadata")
    if sev["meta"].get("complete_pair_count") is not None:
        require(sev["meta"]["complete_pair_count"] == seva_count,
                "sevastopol_exact_city: complete_pair_count mismatch")
    # Sevastopol event recency is not a freshness clock; the production update timestamp is.
    if sev["meta"].get("updated_at") is not None:
        fresh_timestamp(sev["meta"]["updated_at"], "sevastopol update checkpoint", now)
    input_hashes = {
        "ukrainealarm_bridge.json": bridge_hash,
        "alerts_combined.json": kyiv_hash,
        "sevastopol_events.json": sev_hash,
    }
    snapshot_hash = hashlib.sha256(
        json.dumps(input_hashes, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return {
        "ok": True, "mode": "cached_bridge", "source_commit_sha": source_commit_sha,
        "bridge_schema_version": 3, "last_successful_fetch_at": checkpoint,
        "global_checkpoint_age_hours": global_age, "last_fetch_error": None,
        "required_regions": len(EXPECTED_REGIONS), "valid_regions": len(regional),
        "regions": regional, "event_count": len(events), "events_per_region": event_counts,
        "kyiv_exact_city_intervals": kyiv_count, "sevastopol_exact_city_intervals": seva_count,
        "input_sha256": input_hashes, "input_bytes": {
            "ukrainealarm_bridge.json": bridge_size, "alerts_combined.json": kyiv_size,
            "sevastopol_events.json": seva_size,
        }, "snapshot_sha256": snapshot_hash,
    }


def validate_episode_regression(polled: dict, state: dict, snapshot: dict, *, is_proxy) -> dict:
    """Detect prior accepted-state regressions without reidentifying city/raion alerts."""
    expected_cities = EXPECTED_REGIONS | SPECIAL_CITY_KEYS
    require(isinstance(state, dict) and state.get("schema_version") == 1,
            "WIP accepted monitoring state invalid")
    require(isinstance(state.get("cities"), dict), "WIP state has no cities mapping")
    require(set(polled) == expected_cities, "cached poll lacks 23 city keys")
    prior = state.get("cached_bridge_source") or {}
    require(isinstance(prior, dict), "cached source checkpoint malformed")
    current_checkpoint = aware_timestamp(snapshot["last_successful_fetch_at"], "snapshot checkpoint")
    if prior:
        prior_checkpoint = aware_timestamp(prior.get("last_successful_fetch_at"), "prior cached checkpoint")
        require(current_checkpoint >= prior_checkpoint, "cached checkpoint regressed")
        require(snapshot["event_count"] >= prior.get("event_count", 0),
                "cached bridge event count regressed")
        if current_checkpoint == prior_checkpoint:
            require(prior.get("input_sha256", {}).get("ukrainealarm_bridge.json")
                    == snapshot["input_sha256"]["ukrainealarm_bridge.json"],
                    "same checkpoint but different cached bridge bytes")
    retained = 0
    legitimately_grouped_fragments = 0
    episode_counts = {}
    for key in sorted(expected_cities):
        rows = polled[key]
        require(isinstance(rows, list), f"{key}: no episode list")
        ids = set()
        intervals = []
        for ep in rows:
            require(ep.get("city_key") == key and bool(ep.get("episode_id")), f"{key}: invalid episode identity")
            start = aware_timestamp(ep.get("alert_start"), key + ".alert_start")
            end = aware_timestamp(ep.get("alert_end"), key + ".alert_end")
            require(end > start, f"{key}: invalid cached episode interval")
            require(ep["episode_id"] not in ids, f"{key}: duplicate cached episode ID")
            ids.add(ep["episode_id"])
            intervals.append((start, end))
        episode_counts[key] = len(rows)
        old = state["cities"].get(key) or {}
        require(isinstance(old, dict), f"{key}: malformed accepted city state")
        previous_end = old.get("latest_api_alert_end")
        if previous_end:
            previous_end_dt = aware_timestamp(previous_end, key + ".previous_latest")
            # A newer network run can be ahead of production; fail until site-prod catches up.
            if intervals:
                newest_end = max(x[1] for x in intervals)
                require(newest_end >= previous_end_dt, f"{key}: latest accepted observation regressed")
            else:
                raise CachedSnapshotError(f"{key}: accepted observation absent from cached source")
        if not intervals:
            continue
        oldest_visible_end = min(x[1] for x in intervals)
        for ep in old.get("episodes") or []:
            if not isinstance(ep, dict) or not ep.get("episode_id"):
                raise CachedSnapshotError(f"{key}: invalid accepted episode")
            if ep.get("identity_superseded_by_episode_id"):
                continue
            end = aware_timestamp(ep.get("alert_end"), key + ".accepted_end")
            if end < oldest_visible_end or end > current_checkpoint:
                continue
            if ep["episode_id"] in ids:
                retained += 1
                continue
            if is_proxy(key):
                old_start = aware_timestamp(ep.get("alert_start"), key + ".accepted_start")
                if any(start <= old_start and end <= row_end and
                       (start < old_start or end < row_end) for start, row_end in intervals):
                    legitimately_grouped_fragments += 1
                    continue
            raise CachedSnapshotError(f"{key}: accepted episode identity not in cached source: {ep['episode_id']}")
    return {
        "ok": True, "episode_counts": episode_counts,
        "cached_episode_count": sum(episode_counts.values()),
        "retained_accepted_episode_ids": retained,
        "prior_fragments_with_authoritative_union": legitimately_grouped_fragments,
        "unexpected_identity_regressions": 0,
    }


def cli() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed pinned production cached-bridge validation")
    parser.add_argument("--bridge-file", required=True)
    parser.add_argument("--kyiv-alerts-file", required=True)
    parser.add_argument("--sevastopol-events-file", required=True)
    parser.add_argument("--source-commit-sha", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    snapshot = validate_snapshot(
        Path(args.bridge_file), Path(args.kyiv_alerts_file),
        Path(args.sevastopol_events_file), now=datetime.now(UTC),
        source_commit_sha=args.source_commit_sha,
    )
    result = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    cli()
