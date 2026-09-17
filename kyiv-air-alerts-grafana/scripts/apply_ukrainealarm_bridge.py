#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

import add_duration_unit_switch as exactmod
from update_data import Alert, TZ, build_outputs

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
STORE_FILE = ROOT / "data" / "ukrainealarm_bridge.json"
API_BASE = "https://api.ukrainealarm.com/api/v3"
API_URL = f"{API_BASE}/alerts/regionHistory"
REGIONS_URL = f"{API_BASE}/regions"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
HISTORY_LIMIT = 25
UTC = timezone.utc

EXACT_ALIASES = {
    "м. Харків та Харківська територіальна громада": [
        "Харківська територіальна громада",
        "Харківська міська територіальна громада",
        "м. Харків",
        "Харків",
    ],
    "м. Запоріжжя та Запорізька територіальна громада": [
        "Запорізька територіальна громада",
        "Запорізька міська територіальна громада",
        "м. Запоріжжя",
        "Запоріжжя",
    ],
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        if "." not in text:
            return None
        head, tail = text.split(".", 1)
        offset = ""
        for i, ch in enumerate(tail):
            if i and ch in "+-":
                offset, tail = tail[i:], tail[:i]
                break
        digits = "".join(ch for ch in tail if ch.isdigit())[:6]
        try:
            dt = datetime.fromisoformat(f"{head}.{digits}{offset}")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


def load_store() -> dict:
    if STORE_FILE.exists():
        store = json.loads(STORE_FILE.read_text(encoding="utf-8"))
    else:
        store = {"schema_version": 1, "events": [], "regions": {}}
    store.setdefault("events", [])
    store.setdefault("regions", {})
    store.setdefault("source_url", API_URL)
    store.setdefault("history_limit_per_region", HISTORY_LIMIT)
    return store


def api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": token,
        "User-Agent": "kyiv-air-alerts-grafana/1.0 (+public dashboard updater)",
    }


def raise_api_error(response: requests.Response, context: str) -> None:
    if response.ok:
        return
    body = response.text.strip().replace("\n", " ")[:500]
    raise RuntimeError(
        f"{context}: HTTP {response.status_code} {response.reason}; response={body!r}"
    )


def collect_region_nodes(payload) -> list[dict]:
    nodes: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def walk(value) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return

        region_id = value.get("regionId")
        region_name = str(value.get("regionName") or "").strip()
        if region_id is not None and region_name:
            key = (str(region_id), region_name)
            if key not in seen:
                seen.add(key)
                nodes.append(
                    {
                        "regionId": str(region_id),
                        "regionName": region_name,
                        "regionType": value.get("regionType"),
                    }
                )

        for child in value.values():
            if isinstance(child, (dict, list)):
                walk(child)

    walk(payload)
    return nodes


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def find_region_node(nodes: list[dict], target: str) -> dict | None:
    candidates = [target, *EXACT_ALIASES.get(target, [])]
    by_name = {normalize_name(str(node["regionName"])): node for node in nodes}
    for candidate in candidates:
        node = by_name.get(normalize_name(candidate))
        if node:
            return node
    return None


def fetch_regions(token: str) -> list[dict]:
    response = requests.get(REGIONS_URL, headers=api_headers(token), timeout=60)
    raise_api_error(response, "UkraineAlarm regions request failed")
    payload = response.json()
    nodes = collect_region_nodes(payload)
    if not nodes:
        raise RuntimeError("UkraineAlarm regions response contained no regionId/regionName nodes")
    return nodes


def normalize_history_payload(payload, fallback: dict) -> list[dict]:
    if isinstance(payload, dict):
        groups = [payload]
    elif isinstance(payload, list):
        groups = [row for row in payload if isinstance(row, dict)]
    else:
        raise RuntimeError(
            f"Unexpected UkraineAlarm regionHistory payload: {type(payload).__name__}"
        )

    out: list[dict] = []
    for group in groups:
        row = dict(group)
        row.setdefault("regionId", fallback["regionId"])
        row.setdefault("regionName", fallback["regionName"])
        alarms = row.get("alarms")
        if alarms is None:
            row["alarms"] = []
        elif not isinstance(alarms, list):
            continue
        out.append(row)
    return out


def fetch_history(token: str, targets: list[str]) -> list[dict]:
    nodes = fetch_regions(token)
    payload: list[dict] = []

    for target in targets:
        node = find_region_node(nodes, target)
        if node is None:
            hints = sorted(
                n["regionName"]
                for n in nodes
                if any(
                    piece in normalize_name(n["regionName"])
                    for piece in normalize_name(target).split()
                    if len(piece) >= 5
                )
            )[:12]
            raise RuntimeError(
                f"UkraineAlarm region not found for {target!r}; possible matches={hints}"
            )

        response = requests.get(
            API_URL,
            headers=api_headers(token),
            params={"regionId": node["regionId"]},
            timeout=60,
        )
        raise_api_error(
            response,
            f"UkraineAlarm regionHistory request failed for {node['regionName']} ({node['regionId']})",
        )
        groups = normalize_history_payload(response.json(), node)
        if not groups:
            raise RuntimeError(
                f"UkraineAlarm regionHistory returned no usable group for {node['regionName']}"
            )
        payload.extend(groups)
        print(
            f"UkraineAlarm region resolved: {target} -> "
            f"{node['regionName']} ({node['regionId']})"
        )

    return payload


def groups_by_name(payload: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for group in payload:
        name = str(group.get("regionName") or "").strip()
        alarms = group.get("alarms") or []
        if not name or not isinstance(alarms, list):
            continue
        bucket = groups.setdefault(
            name,
            {"regionName": name, "regionId": group.get("regionId"), "alarms": []},
        )
        bucket["alarms"].extend(a for a in alarms if isinstance(a, dict))
    return groups


def find_group(groups: dict[str, dict], target: str) -> dict | None:
    normalized = {normalize_name(name): group for name, group in groups.items()}
    for name in [target, *EXACT_ALIASES.get(target, [])]:
        group = normalized.get(normalize_name(name))
        if group:
            return group
    return None


def merge_history(store: dict, payload: list[dict], cutoffs: dict[str, datetime]) -> dict:
    groups = groups_by_name(payload)
    fetched_at = datetime.now(UTC)
    events = {
        (e.get("region_name"), e.get("start"), e.get("end"), e.get("alert_type")): e
        for e in store["events"]
        if isinstance(e, dict)
    }

    for target, cutoff in cutoffs.items():
        previous = store["regions"].get(target, {})
        group = find_group(groups, target)
        if group is None:
            store["regions"][target] = {
                **previous,
                "region_name": target,
                "seen_in_latest_payload": False,
                "last_checked_at": iso(fetched_at),
                "continuity_cutoff": iso(cutoff),
                "continuous_from_upstream": bool(previous.get("continuous_from_upstream")),
                "continuity_reason": previous.get("continuity_reason")
                or "region_missing_from_history_payload",
            }
            continue

        alarms = group["alarms"]
        starts = [dt for dt in (parse_dt(a.get("startDate")) for a in alarms) if dt]
        oldest = min(starts) if starts else None
        history_reaches_cutoff = len(alarms) < HISTORY_LIMIT or (
            oldest is not None and oldest <= cutoff.astimezone(UTC)
        )
        continuous = bool(previous.get("continuous_from_upstream")) or history_reaches_cutoff
        if previous.get("continuous_from_upstream"):
            reason = previous.get("continuity_reason") or "previously_verified"
        elif len(alarms) < HISTORY_LIMIT:
            reason = "history_not_truncated"
        elif history_reaches_cutoff:
            reason = "history_overlaps_upstream"
        else:
            reason = "history_window_does_not_reach_upstream"

        accepted_names = {
            normalize_name(target),
            normalize_name(str(group.get("regionName") or "")),
            *(normalize_name(name) for name in EXACT_ALIASES.get(target, [])),
        }
        completed_air = 0
        latest_end = None
        for alarm in alarms:
            if str(alarm.get("alertType") or "").upper() != "AIR":
                continue
            start = parse_dt(alarm.get("startDate"))
            end = parse_dt(alarm.get("endDate"))
            if not start or not end or end <= start:
                continue
            embedded_name = str(
                alarm.get("regionName") or group.get("regionName") or ""
            ).strip()
            if embedded_name and normalize_name(embedded_name) not in accepted_names:
                continue
            completed_air += 1
            latest_end = max(latest_end, end) if latest_end else end
            row = {
                "region_id": str(alarm.get("regionId") or group.get("regionId") or ""),
                "region_name": target,
                "api_region_name": str(group.get("regionName") or target),
                "start": iso(start),
                "end": iso(end),
                "alert_type": "AIR",
            }
            events[(target, row["start"], row["end"], "AIR")] = row

        store["regions"][target] = {
            "region_id": str(group.get("regionId") or previous.get("region_id") or ""),
            "region_name": target,
            "api_region_name": str(group.get("regionName") or target),
            "seen_in_latest_payload": True,
            "last_checked_at": iso(fetched_at),
            "continuity_cutoff": iso(cutoff),
            "history_count": len(alarms),
            "completed_air_count_in_history": completed_air,
            "oldest_history_start": iso(oldest),
            "latest_history_end": iso(latest_end),
            "history_limit_hit": len(alarms) >= HISTORY_LIMIT,
            "continuous_from_upstream": continuous,
            "continuity_reason": reason,
        }

    store["events"] = sorted(
        events.values(), key=lambda e: (e.get("start") or "", e.get("region_name") or "")
    )
    store["first_successful_fetch_at"] = store.get("first_successful_fetch_at") or iso(fetched_at)
    store["last_successful_fetch_at"] = iso(fetched_at)
    store["last_fetch_error"] = None
    store["event_count"] = len(store["events"])
    return store


def bridge_events(store: dict, region: str, cutoff: datetime) -> list[Alert]:
    if not store.get("regions", {}).get(region, {}).get("continuous_from_upstream"):
        return []
    alerts: list[Alert] = []
    for row in store.get("events", []):
        if row.get("region_name") != region or row.get("alert_type") != "AIR":
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if start and end and end > start and end > cutoff.astimezone(UTC):
            alerts.append(
                Alert(
                    start=start.astimezone(TZ),
                    end=end.astimezone(TZ),
                    source="ukrainealarm_official_api_bridge",
                )
            )
    return sorted(alerts, key=lambda alert: alert.start)


def union_alerts(alerts: list[Alert], source: str) -> list[Alert]:
    merged: list[list[datetime]] = []
    for alert in sorted(alerts, key=lambda item: item.start):
        if not merged or alert.start > merged[-1][1]:
            merged.append([alert.start, alert.end])
        elif alert.end > merged[-1][1]:
            merged[-1][1] = alert.end
    return [Alert(start=start, end=end, source=source) for start, end in merged]


def bridged_exact_alerts(
    base_alerts: dict[str, list[Alert]], store: dict | None = None
) -> tuple[dict[str, list[Alert]], set[str]]:
    store = store or load_store()
    result = {key: list(alerts) for key, alerts in base_alerts.items()}
    covered: set[str] = set()
    for key, cfg in exactmod.CITY_CONFIG.items():
        if key not in result or not result[key]:
            continue
        cutoff = max(alert.end for alert in result[key])
        region = cfg["hromada"]
        if not store.get("regions", {}).get(region, {}).get("continuous_from_upstream"):
            continue
        extra = bridge_events(store, region, cutoff)
        result[key] = union_alerts(
            [*result[key], *extra],
            "vadimkin_plus_official_ukrainealarm_api",
        )
        covered.add(key)
    return result, covered


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    if not all(key in cities for key in exactmod.CITY_KEYS):
        raise RuntimeError("Expected Kyiv, Kharkiv and Zaporizhzhia rows before API bridge")

    token = os.getenv(TOKEN_ENV, "").strip()
    store = load_store()
    if not token:
        raise RuntimeError(f"{TOKEN_ENV} is not configured")

    base_alerts = exactmod.fetch_city_alerts()
    cutoffs = {
        cfg["hromada"]: max(alert.end for alert in base_alerts[key])
        for key, cfg in exactmod.CITY_CONFIG.items()
    }

    try:
        history_payload = fetch_history(token, list(cutoffs))
        store = merge_history(store, history_payload, cutoffs)
        STORE_FILE.write_text(
            json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("UkraineAlarm API history fetched successfully")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        store["last_fetch_error"] = error
        if STORE_FILE.exists():
            STORE_FILE.write_text(
                json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        if not store.get("events"):
            raise RuntimeError(f"UkraineAlarm API first fetch failed: {error}") from exc
        print("UkraineAlarm API fetch failed; retaining prior bridge store:", error)

    merged_alerts, covered_keys = bridged_exact_alerts(base_alerts, store)
    now = datetime.now(TZ)
    status: dict[str, dict] = {}

    for key, cfg in exactmod.CITY_CONFIG.items():
        base = base_alerts[key]
        cutoff = max(alert.end for alert in base)
        region = cfg["hromada"]
        region_meta = store.get("regions", {}).get(region, {})
        continuous = bool(region_meta.get("continuous_from_upstream"))
        extra = bridge_events(store, region, cutoff)
        status[key] = {
            "region": region,
            "api_region_id": region_meta.get("region_id"),
            "api_region_name": region_meta.get("api_region_name"),
            "continuous": continuous,
            "continuity_reason": region_meta.get("continuity_reason"),
            "upstream_cutoff": cutoff.isoformat(),
            "api_history_count": region_meta.get("history_count"),
            "api_oldest_history_start": region_meta.get("oldest_history_start"),
            "api_latest_history_end": region_meta.get("latest_history_end"),
            "bridge_events_applied": len(extra),
            "latest_bridge_event_end": max(
                (alert.end.isoformat() for alert in extra), default=None
            ),
        }
        if key not in covered_keys:
            continue

        merged = merged_alerts[key]
        meta = dict(cities[key].get("meta", {}))
        meta.update(
            {
                "city_completed_alerts": len(merged),
                "latest_city_record_start": max(alert.start for alert in merged).isoformat(),
                "latest_city_record_end": max(alert.end for alert in merged).isoformat(),
                "data_source_kind": (
                    "official city-level hromada history + official UkraineAlarm API bridge"
                ),
                "ukrainealarm_bridge_region": region,
                "ukrainealarm_bridge_continuous": True,
                "ukrainealarm_bridge_events_applied": len(extra),
            }
        )
        output = build_outputs(merged, now, meta)
        exactmod.enrich_weekly(output, merged)
        first_day = min(alert.start for alert in base).astimezone(TZ).date()
        exactmod.trim_first_partial_periods(output, first_day)
        cities[key] = output

    data["cities"] = cities
    data["comparison"] = {
        "monthly": exactmod.build_comparison(cities, "monthly"),
        "weekly": exactmod.build_comparison(cities, "weekly"),
    }

    required = sorted(exactmod.CITY_CONFIG)
    covered = sorted(covered_keys)
    summary = {
        "source_url": API_URL,
        "regions_url": REGIONS_URL,
        "history_limit_per_region": HISTORY_LIMIT,
        "last_successful_fetch_at": store.get("last_successful_fetch_at"),
        "last_fetch_error": store.get("last_fetch_error"),
        "event_store_file": "data/ukrainealarm_bridge.json",
        "event_count": len(store.get("events", [])),
        "required_rows": required,
        "continuity_verified_rows": covered,
        "continuity_unverified_rows": sorted(set(required) - set(covered)),
        "fully_continuous": len(covered) == len(required),
        "rows": status,
    }
    data.setdefault("multicity_meta", {})["official_ukrainealarm_bridge"] = summary
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Official UkraineAlarm bridge continuity: {len(covered)}/{len(required)} exact city rows"
    )


if __name__ == "__main__":
    main()
