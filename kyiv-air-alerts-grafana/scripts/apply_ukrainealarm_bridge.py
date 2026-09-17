#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import add_duration_unit_switch as exactmod
import expand_multicity_production as base
import extend_remaining_proxies as extended
from update_data import Alert, TZ, build_outputs

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
STORE_FILE = ROOT / "data" / "ukrainealarm_bridge.json"
STATIC_BRIDGES = [
    ROOT / "data" / "alerts_in_ua_bridge_2026-09-07_16.csv.gz.b64",
    ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.csv.gz.b64",
]
STATIC_METAS = [
    ROOT / "data" / "alerts_in_ua_bridge_2026-09-07_16.meta.json",
    ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.meta.json",
]
API_BASE = "https://api.ukrainealarm.com/api/v3"
REGIONS_URL = f"{API_BASE}/regions"
HISTORY_URL = f"{API_BASE}/alerts/regionHistory"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
UTC = timezone.utc
MATCH_TOLERANCE_SECONDS = 15.0
MIN_API_INTERVAL_SECONDS = float(os.getenv("UKRAINEALARM_MIN_INTERVAL_SECONDS", "70"))
MAX_401_RETRIES = 2
STORE_SCHEMA_VERSION = 3

EXACT_OBLAST = {
    "kharkiv": "Харківська область",
    "zaporizhzhia": "Запорізька область",
}
EXACT_ALIASES = {
    "kharkiv": [
        "м. Харків та Харківська територіальна громада",
        "Харківська територіальна громада",
        "Харківська міська територіальна громада",
        "м. Харків",
        "Харків",
    ],
    "zaporizhzhia": [
        "м. Запоріжжя та Запорізька територіальна громада",
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


def norm(value: str) -> str:
    return " ".join(str(value).casefold().replace("’", "'").split())


def load_static_bridge() -> tuple[dict[str, list[Alert]], dict]:
    rows: dict[str, list[Alert]] = {}
    metas = []
    for payload_path, meta_path in zip(STATIC_BRIDGES, STATIC_METAS):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        metas.append(meta)
        raw = gzip.decompress(
            base64.b64decode(payload_path.read_text(encoding="ascii").strip())
        ).decode("utf-8")
        for row in csv.DictReader(io.StringIO(raw)):
            key = (row.get("city_key") or "").strip()
            start = parse_dt(row.get("start"))
            end = parse_dt(row.get("end"))
            if key and start and end and end > start:
                rows.setdefault(key, []).append(
                    Alert(
                        start=start.astimezone(TZ),
                        end=end.astimezone(TZ),
                        source="alerts_in_ua_static_bridge",
                    )
                )
    for key, alerts in rows.items():
        unique = {(a.start, a.end): a for a in alerts}
        rows[key] = sorted(unique.values(), key=lambda a: a.start)

    starts = [parse_dt(m.get("coverage_start")) for m in metas]
    ends = [parse_dt(m.get("coverage_end_exclusive")) for m in metas]
    if any(x is None for x in [*starts, *ends]):
        raise RuntimeError("Invalid static bridge coverage metadata")
    info = {
        "source": "Alerts.in.ua manual CSV export",
        "coverage_start": iso(min(x for x in starts if x)),
        "coverage_end_exclusive": iso(max(x for x in ends if x)),
        "payload_files": [p.name for p in STATIC_BRIDGES],
        "completed_event_rows": sum(len(v) for v in rows.values()),
        "cross_source_match_tolerance_seconds": MATCH_TOLERANCE_SECONDS,
    }
    return rows, info


def load_store() -> dict:
    if not STORE_FILE.exists():
        return {
            "schema_version": STORE_SCHEMA_VERSION,
            "source_url": HISTORY_URL,
            "regions": {},
            "events": [],
        }
    try:
        store = json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        store = {}
    if store.get("schema_version") != STORE_SCHEMA_VERSION:
        return {
            "schema_version": STORE_SCHEMA_VERSION,
            "source_url": HISTORY_URL,
            "regions": {},
            "events": [],
            "reset_from_schema_version": store.get("schema_version"),
        }
    store.setdefault("regions", {})
    store.setdefault("events", [])
    store.setdefault("source_url", HISTORY_URL)
    return store


def collect_nodes(payload) -> list[dict]:
    nodes: list[dict] = []
    seen = set()

    def walk(value, ancestors=()):
        if isinstance(value, list):
            for item in value:
                walk(item, ancestors)
            return
        if not isinstance(value, dict):
            return
        rid = value.get("regionId")
        name = str(value.get("regionName") or "").strip()
        child_ancestors = ancestors
        if rid is not None and name:
            marker = (str(rid), name)
            if marker not in seen:
                seen.add(marker)
                nodes.append(
                    {
                        "regionId": str(rid),
                        "regionName": name,
                        "regionType": value.get("regionType"),
                        "ancestors": list(ancestors),
                    }
                )
            child_ancestors = (*ancestors, name)
        for child in value.values():
            if isinstance(child, (dict, list)):
                walk(child, child_ancestors)

    walk(payload)
    return nodes


def resolve_region(nodes: list[dict], names: list[str], oblast: str) -> dict | None:
    wanted = {norm(x) for x in names}
    matches = [n for n in nodes if norm(n["regionName"]) in wanted]
    oblast_norm = norm(oblast)
    scoped = [
        n
        for n in matches
        if oblast_norm in {norm(a) for a in n.get("ancestors", [])}
        or norm(n["regionName"]) == oblast_norm
    ]
    if scoped:
        matches = scoped
    if not matches:
        return None
    matches.sort(key=lambda n: (len(n.get("ancestors", [])), n["regionId"]))
    return matches[-1]


class UkraineAlarmClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.session = requests.Session()
        self.last_request_at: float | None = None

    def _wait_for_slot(self) -> None:
        if self.last_request_at is None:
            return
        wait = MIN_API_INTERVAL_SECONDS - (time.monotonic() - self.last_request_at)
        if wait > 0:
            print(f"UkraineAlarm rate-limit guard: sleeping {wait:.1f}s", flush=True)
            time.sleep(wait)

    def get(self, url: str, *, params: dict | None = None, context: str) -> requests.Response:
        for attempt in range(MAX_401_RETRIES + 1):
            self._wait_for_slot()
            response = self.session.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": self.token,
                    "User-Agent": "kyiv-air-alerts-grafana/verified-multicity-bridge",
                },
                params=params,
                timeout=60,
            )
            self.last_request_at = time.monotonic()
            if response.status_code != 401:
                if not response.ok:
                    body = response.text.strip().replace("\n", " ")[:300]
                    raise RuntimeError(
                        f"{context}: HTTP {response.status_code} {response.reason}; response={body!r}"
                    )
                return response
            if attempt >= MAX_401_RETRIES:
                raise RuntimeError(f"{context}: HTTP 401 after {attempt + 1} attempts")
            print(
                f"{context}: HTTP 401 on attempt {attempt + 1}; retrying after guard interval",
                flush=True,
            )
        raise AssertionError("unreachable")


def history_rows(client: UkraineAlarmClient, region_id: str, name: str) -> list[dict]:
    response = client.get(
        HISTORY_URL,
        params={"regionId": region_id},
        context=f"regionHistory {name} ({region_id})",
    )
    payload = response.json()
    groups = [payload] if isinstance(payload, dict) else [x for x in payload if isinstance(x, dict)]
    rows = []
    for group in groups:
        for alarm in group.get("alarms") or []:
            if not isinstance(alarm, dict):
                continue
            if str(alarm.get("alertType") or "").upper() != "AIR":
                continue
            start = parse_dt(alarm.get("startDate"))
            end = parse_dt(alarm.get("endDate"))
            if start and end and end > start:
                rows.append({"start": start, "end": end})
    unique = {(r["start"], r["end"]): r for r in rows}
    return sorted(unique.values(), key=lambda r: r["start"])


def match_static_event(api_rows: list[dict], static_rows: list[Alert]) -> dict | None:
    for api in api_rows:
        for bridge in static_rows:
            ds = abs((api["start"] - bridge.start.astimezone(UTC)).total_seconds())
            de = abs((api["end"] - bridge.end.astimezone(UTC)).total_seconds())
            if ds <= MATCH_TOLERANCE_SECONDS and de <= MATCH_TOLERANCE_SECONDS:
                return {
                    "api_start": iso(api["start"]),
                    "api_end": iso(api["end"]),
                    "static_start": bridge.start.isoformat(),
                    "static_end": bridge.end.isoformat(),
                    "start_delta_seconds": round(ds, 3),
                    "end_delta_seconds": round(de, 3),
                }
    return None


def union_alerts(alerts: list[Alert], source: str) -> list[Alert]:
    merged: list[list[datetime]] = []
    for alert in sorted(alerts, key=lambda a: a.start):
        if not merged or alert.start > merged[-1][1]:
            merged.append([alert.start, alert.end])
        elif alert.end > merged[-1][1]:
            merged[-1][1] = alert.end
    return [Alert(start=s, end=e, source=source) for s, e in merged]


def generic_comparison(cities: dict, keys: list[str], period: str) -> list[dict]:
    by_city = {key: {row["time"]: row for row in cities[key].get(period, [])} for key in keys}
    if not keys:
        return []
    shared = set(by_city[keys[0]])
    for key in keys[1:]:
        shared &= set(by_city[key])
    out = []
    for timestamp in sorted(shared):
        row = {"time": timestamp}
        for key in keys:
            src = by_city[key][timestamp]
            row[f"{key}_alerts_per_day"] = src.get("alerts_per_day")
            row[f"{key}_avg_daily_alert_hours"] = src.get("avg_daily_alert_hours")
            row[f"{key}_avg_alert_duration_min"] = src.get("avg_alert_duration_min")
        out.append(row)
    return out


def api_store_alerts(store: dict, key: str) -> list[Alert]:
    out = []
    for row in store.get("events", []):
        if row.get("city_key") != key:
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if start and end and end > start:
            out.append(
                Alert(
                    start=start.astimezone(TZ),
                    end=end.astimezone(TZ),
                    source="ukrainealarm_official_api_bridge",
                )
            )
    return sorted(out, key=lambda a: a.start)


def specs(proxy_cfg: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for key, cfg in exactmod.CITY_CONFIG.items():
        out[key] = {
            "kind": "exact",
            "names": EXACT_ALIASES[key],
            "oblast": EXACT_OBLAST[key],
            "display_target": cfg["hromada"],
        }
    for key, cfg in proxy_cfg.items():
        out[key] = {
            "kind": "proxy",
            "names": [cfg["raion"]],
            "oblast": cfg["oblast"],
            "display_target": cfg["raion"],
        }
    return out


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.setdefault("cities", {})
    mm = data.setdefault("multicity_meta", {})
    token = os.getenv(TOKEN_ENV, "").strip()
    static, static_info = load_static_bridge()

    proxy_cfg = extended.configure_all_proxies()
    target_specs = specs(proxy_cfg)
    required_keys = list(target_specs)
    missing_static = [key for key in required_keys if not static.get(key)]
    if missing_static:
        raise RuntimeError(f"Static bridge has no completed events for: {missing_static}")

    exact_base = exactmod.fetch_city_alerts()
    proxy_base = base.fetch_proxy_alerts()
    store = load_store()
    store["static_bridge"] = static_info
    store["match_tolerance_seconds"] = MATCH_TOLERANCE_SECONDS
    attempt_at = datetime.now(UTC)
    store["last_attempt_at"] = iso(attempt_at)

    events = {
        (e.get("city_key"), e.get("start"), e.get("end")): e
        for e in store.get("events", [])
        if isinstance(e, dict)
    }
    request_errors: dict[str, str] = {}
    fetched_keys: list[str] = []

    if token:
        client = UkraineAlarmClient(token)
        nodes: list[dict] | None = None
        unresolved = [key for key in required_keys if not store.get("regions", {}).get(key, {}).get("region_id")]
        if unresolved:
            nodes = collect_nodes(client.get(REGIONS_URL, context="regions").json())

        for index, key in enumerate(required_keys, 1):
            spec = target_specs[key]
            prev = dict(store.get("regions", {}).get(key, {}))
            region_id = str(prev.get("region_id") or "")
            api_name = str(prev.get("api_region_name") or "")
            if not region_id:
                node = resolve_region(nodes or [], spec["names"], spec["oblast"])
                if node is None:
                    request_errors[key] = "api_region_not_found"
                    store.setdefault("regions", {})[key] = {
                        **prev,
                        "city_key": key,
                        "target": spec["display_target"],
                        "continuous": False,
                        "last_error": request_errors[key],
                        "last_attempt_at": iso(datetime.now(UTC)),
                    }
                    print(f"[{index}/{len(required_keys)}] {key}: API region not found", flush=True)
                    continue
                region_id = node["regionId"]
                api_name = node["regionName"]

            try:
                history = history_rows(client, region_id, api_name or spec["display_target"])
                checked_at = datetime.now(UTC)
                oldest = min((r["start"] for r in history), default=None)
                latest = max((r["end"] for r in history), default=None)
                initial_match = match_static_event(history, static[key])

                if prev.get("continuous") and prev.get("last_checked_at"):
                    previous_check = parse_dt(prev.get("last_checked_at"))
                    poll_overlap = bool(oldest and previous_check and oldest <= previous_check)
                    continuous = poll_overlap
                    reason = "history_reaches_previous_poll" if continuous else "history_window_no_longer_reaches_previous_poll"
                else:
                    poll_overlap = None
                    continuous = bool(initial_match)
                    reason = "static_alertsinua_event_matches_api" if continuous else "no_verified_static_api_event_match"

                if continuous:
                    for row in history:
                        event = {
                            "city_key": key,
                            "region_id": region_id,
                            "api_region_name": api_name or spec["display_target"],
                            "start": iso(row["start"]),
                            "end": iso(row["end"]),
                            "alert_type": "AIR",
                        }
                        events[(key, event["start"], event["end"])] = event

                store.setdefault("regions", {})[key] = {
                    "city_key": key,
                    "kind": spec["kind"],
                    "target": spec["display_target"],
                    "oblast": spec["oblast"],
                    "region_id": region_id,
                    "api_region_name": api_name or spec["display_target"],
                    "continuous": continuous,
                    "continuity_reason": reason,
                    "initial_static_match": initial_match or prev.get("initial_static_match"),
                    "poll_overlap_verified": poll_overlap,
                    "history_completed_air_count": len(history),
                    "oldest_history_start": iso(oldest),
                    "latest_history_end": iso(latest),
                    "last_checked_at": iso(checked_at),
                    "last_error": None,
                }
                fetched_keys.append(key)
                print(
                    f"[{index}/{len(required_keys)}] {key}: continuous={continuous} "
                    f"region={region_id} history={len(history)} "
                    f"static_match={bool(initial_match)} poll_overlap={poll_overlap}",
                    flush=True,
                )
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                request_errors[key] = message
                store.setdefault("regions", {})[key] = {
                    **prev,
                    "city_key": key,
                    "target": spec["display_target"],
                    "region_id": region_id,
                    "api_region_name": api_name or spec["display_target"],
                    "last_error": message,
                    "last_attempt_at": iso(datetime.now(UTC)),
                }
                print(f"[{index}/{len(required_keys)}] {key}: ERROR {message}", flush=True)

        if len(fetched_keys) == len(required_keys) and not request_errors:
            store["last_successful_fetch_at"] = iso(datetime.now(UTC))
        store["last_fetch_error"] = None if not request_errors else request_errors
    elif not store.get("events"):
        print(f"{TOKEN_ENV} is not configured and bridge store is empty; API continuation skipped")

    store["events"] = sorted(
        events.values(), key=lambda e: (e.get("start") or "", e.get("city_key") or "")
    )
    store["event_count"] = len(store["events"])
    STORE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    now_local = datetime.now(TZ)
    status: dict[str, dict] = {}

    for key, cfg in exactmod.CITY_CONFIG.items():
        region_status = store.get("regions", {}).get(key, {})
        continuous = bool(region_status.get("continuous"))
        api_alerts = api_store_alerts(store, key) if continuous else []
        combined = union_alerts(
            [*exact_base[key], *static[key], *api_alerts],
            "historical_plus_alertsinua_plus_ukrainealarm",
        )
        meta = dict(cities.get(key, {}).get("meta", {}))
        meta.update(
            {
                "city_completed_alerts": len(combined),
                "latest_city_record_start": max(a.start for a in combined).isoformat(),
                "latest_city_record_end": max(a.end for a in combined).isoformat(),
                "data_source_kind": "exact-city history + Alerts.in.ua seam + official UkraineAlarm API",
                "static_bridge_events": len(static[key]),
                "ukrainealarm_bridge_events": len(api_alerts),
                "ukrainealarm_bridge_continuous": continuous,
                "ukrainealarm_api_region_id": region_status.get("region_id"),
            }
        )
        out = build_outputs(combined, now_local, meta)
        exactmod.enrich_weekly(out, combined)
        first_day = datetime.fromisoformat(cfg["valid_from"]).astimezone(TZ).date()
        exactmod.trim_first_partial_periods(out, first_day)
        cities[key] = out
        status[key] = {
            "primary_region": cfg["hromada"],
            "primary_continuous": continuous,
            "static_bridge_events_applied": len(static[key]),
            "api_bridge_events_applied": len(api_alerts),
            "latest_record_end": max(a.end for a in combined).isoformat(),
            "continuity_reason": region_status.get("continuity_reason"),
            "last_checked_at": region_status.get("last_checked_at"),
            "last_error": region_status.get("last_error"),
        }

    for key, cfg in proxy_cfg.items():
        region_status = store.get("regions", {}).get(key, {})
        continuous = bool(region_status.get("continuous"))
        api_alerts = api_store_alerts(store, key) if continuous else []
        combined = union_alerts(
            [*proxy_base[key], *static[key], *api_alerts],
            "historical_proxy_plus_alertsinua_plus_ukrainealarm",
        )
        meta = dict(cities.get(key, {}).get("meta", {}))
        meta.update(
            {
                "proxy_completed_alert_episodes": len(combined),
                "latest_proxy_record_start": max(a.start for a in combined).isoformat(),
                "latest_proxy_record_end": max(a.end for a in combined).isoformat(),
                "data_source_kind": "raion proxy history + Alerts.in.ua seam + official UkraineAlarm API",
                "static_bridge_events": len(static[key]),
                "ukrainealarm_bridge_events": len(api_alerts),
                "ukrainealarm_bridge_continuous": continuous,
                "ukrainealarm_api_region_id": region_status.get("region_id"),
            }
        )
        out = build_outputs(combined, now_local, meta)
        base.enrich_weekly(out, combined)
        base.trim_to_complete_coverage(out, date.fromisoformat(cfg["coverage_start"]))
        cities[key] = out
        status[key] = {
            "primary_region": cfg["raion"],
            "primary_continuous": continuous,
            "static_bridge_events_applied": len(static[key]),
            "api_bridge_events_applied": len(api_alerts),
            "latest_record_end": max(a.end for a in combined).isoformat(),
            "continuity_reason": region_status.get("continuity_reason"),
            "last_checked_at": region_status.get("last_checked_at"),
            "last_error": region_status.get("last_error"),
        }

    data["cities"] = cities
    keys = [k for k in mm.get("production_city_keys", []) if k in cities]
    data["comparison"] = {
        "monthly": generic_comparison(cities, keys, "monthly"),
        "weekly": generic_comparison(cities, keys, "weekly"),
    }

    covered = sorted(k for k in required_keys if status.get(k, {}).get("primary_continuous"))
    summary = {
        "source_url": HISTORY_URL,
        "regions_url": REGIONS_URL,
        "token_present_this_run": bool(token),
        "request_guard_seconds": MIN_API_INTERVAL_SECONDS,
        "cross_source_match_tolerance_seconds": MATCH_TOLERANCE_SECONDS,
        "static_bridge": static_info,
        "event_store_file": "data/ukrainealarm_bridge.json",
        "event_count": len(store.get("events", [])),
        "last_attempt_at": store.get("last_attempt_at"),
        "last_successful_fetch_at": store.get("last_successful_fetch_at"),
        "last_fetch_error": store.get("last_fetch_error"),
        "required_rows": sorted(required_keys),
        "continuity_verified_rows": covered,
        "continuity_unverified_rows": sorted(set(required_keys) - set(covered)),
        "fully_continuous": len(covered) == len(required_keys),
        "rows": status,
    }
    mm["official_ukrainealarm_bridge"] = summary
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Verified multicity bridge continuity: {len(covered)}/{len(required_keys)} rows")
    if request_errors:
        print("API request errors:", json.dumps(request_errors, ensure_ascii=False))


if __name__ == "__main__":
    main()
