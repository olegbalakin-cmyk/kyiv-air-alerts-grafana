#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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
API_URL = "https://api.ukrainealarm.com/api/v3/alerts/regionHistory"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
HISTORY_LIMIT = 25
UTC = timezone.utc

EXACT_ALIASES = {
    "м. Харків та Харківська територіальна громада": [
        "Харківська територіальна громада", "Харківська міська територіальна громада",
        "м. Харків", "Харків",
    ],
    "м. Запоріжжя та Запорізька територіальна громада": [
        "Запорізька територіальна громада", "Запорізька міська територіальна громада",
        "м. Запоріжжя", "Запоріжжя",
    ],
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        # Tolerate .NET timestamps with >6 fractional digits.
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


def configure_proxies() -> dict[str, dict]:
    cfg = {k: dict(v) for k, v in base.PROXY_CONFIG.items()}
    cfg.update({k: dict(v) for k, v in extended.ADDITIONAL_PROXIES.items()})
    base.PROXY_CONFIG = cfg
    base.PROXY_KEYS = list(cfg)
    base.CITY_LABELS = {
        "kyiv": "Київ", "kharkiv": "Харків", "zaporizhzhia": "Запоріжжя",
        **{k: extended.explicit_proxy_label(v["label"], v["raion"]) for k, v in cfg.items()},
    }
    return cfg


def fetch_history(token: str) -> list[dict]:
    r = requests.get(
        API_URL,
        headers={"Accept": "application/json", "Authorization": token,
                 "User-Agent": "kyiv-air-alerts-grafana/1.0 (+public dashboard updater)"},
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected UkraineAlarm payload: {type(payload).__name__}")
    return [x for x in payload if isinstance(x, dict)]


def groups_by_name(payload: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for group in payload:
        name = str(group.get("regionName") or "").strip()
        alarms = group.get("alarms") or []
        if not name or not isinstance(alarms, list):
            continue
        bucket = out.setdefault(name, {"regionName": name, "regionId": group.get("regionId"), "alarms": []})
        bucket["alarms"].extend(a for a in alarms if isinstance(a, dict))
    return out


def find_group(groups: dict[str, dict], target: str) -> dict | None:
    for name in [target, *EXACT_ALIASES.get(target, [])]:
        if name in groups:
            return groups[name]
    return None


def merge_history(store: dict, payload: list[dict], cutoffs: dict[str, datetime]) -> dict:
    groups = groups_by_name(payload)
    fetched_at = datetime.now(UTC)
    events = {
        (e.get("region_name"), e.get("start"), e.get("end"), e.get("alert_type")): e
        for e in store["events"] if isinstance(e, dict)
    }
    for target, cutoff in cutoffs.items():
        prev = store["regions"].get(target, {})
        group = find_group(groups, target)
        if group is None:
            store["regions"][target] = {
                **prev, "region_name": target, "seen_in_latest_payload": False,
                "last_checked_at": iso(fetched_at), "continuity_cutoff": iso(cutoff),
                "continuous_from_upstream": bool(prev.get("continuous_from_upstream")),
                "continuity_reason": prev.get("continuity_reason") or "region_missing_from_history_payload",
            }
            continue

        alarms = group["alarms"]
        starts = [x for x in (parse_dt(a.get("startDate")) for a in alarms) if x]
        oldest = min(starts) if starts else None
        latest_ok = len(alarms) < HISTORY_LIMIT or (oldest is not None and oldest <= cutoff.astimezone(UTC))
        continuous = bool(prev.get("continuous_from_upstream")) or latest_ok
        reason = prev.get("continuity_reason") if prev.get("continuous_from_upstream") else (
            "history_not_truncated" if len(alarms) < HISTORY_LIMIT else
            "history_overlaps_upstream" if latest_ok else "history_window_does_not_reach_upstream"
        )
        accepted = {target, str(group.get("regionName") or ""), *EXACT_ALIASES.get(target, [])}
        air_count = 0
        latest_end = None
        for alarm in alarms:
            if str(alarm.get("alertType") or "").upper() != "AIR":
                continue
            start, end = parse_dt(alarm.get("startDate")), parse_dt(alarm.get("endDate"))
            if not start or not end or end <= start:
                continue
            embedded = str(alarm.get("regionName") or group.get("regionName") or "").strip()
            if embedded and embedded not in accepted:
                continue
            air_count += 1
            latest_end = max(latest_end, end) if latest_end else end
            row = {
                "region_id": str(alarm.get("regionId") or group.get("regionId") or ""),
                "region_name": target, "api_region_name": str(group.get("regionName") or target),
                "start": iso(start), "end": iso(end), "alert_type": "AIR",
            }
            events[(target, row["start"], row["end"], "AIR")] = row
        store["regions"][target] = {
            "region_id": str(group.get("regionId") or prev.get("region_id") or ""),
            "region_name": target, "api_region_name": str(group.get("regionName") or target),
            "seen_in_latest_payload": True, "last_checked_at": iso(fetched_at),
            "continuity_cutoff": iso(cutoff), "history_count": len(alarms),
            "completed_air_count_in_history": air_count, "oldest_history_start": iso(oldest),
            "latest_history_end": iso(latest_end), "history_limit_hit": len(alarms) >= HISTORY_LIMIT,
            "continuous_from_upstream": continuous, "continuity_reason": reason,
        }
    store["events"] = sorted(events.values(), key=lambda e: (e.get("start") or "", e.get("region_name") or ""))
    store["first_successful_fetch_at"] = store.get("first_successful_fetch_at") or iso(fetched_at)
    store["last_successful_fetch_at"] = iso(fetched_at)
    store["last_fetch_error"] = None
    store["event_count"] = len(store["events"])
    return store


def bridge_events(store: dict, region: str, cutoff: datetime) -> list[Alert]:
    if not store["regions"].get(region, {}).get("continuous_from_upstream"):
        return []
    out = []
    for row in store["events"]:
        if row.get("region_name") != region or row.get("alert_type") != "AIR":
            continue
        start, end = parse_dt(row.get("start")), parse_dt(row.get("end"))
        if start and end and end > start and end > cutoff.astimezone(UTC):
            out.append(Alert(start=start.astimezone(TZ), end=end.astimezone(TZ), source="ukrainealarm_official_api_bridge"))
    return sorted(out, key=lambda a: a.start)


def union(alerts: list[Alert], source: str) -> list[Alert]:
    merged: list[list[datetime]] = []
    for a in sorted(alerts, key=lambda x: x.start):
        if not merged or a.start > merged[-1][1]:
            merged.append([a.start, a.end])
        elif a.end > merged[-1][1]:
            merged[-1][1] = a.end
    return [Alert(start=s, end=e, source=source) for s, e in merged]


def comparison(cities: dict, keys: list[str], period: str) -> list[dict]:
    by_city = {k: {r["time"]: r for r in cities[k].get(period, [])} for k in keys}
    shared = set(by_city[keys[0]])
    for k in keys[1:]:
        shared &= set(by_city[k])
    rows = []
    for t in sorted(shared):
        row = {"time": t}
        for k in keys:
            src = by_city[k][t]
            row[f"{k}_alerts_per_day"] = src.get("alerts_per_day")
            row[f"{k}_avg_daily_alert_hours"] = src.get("avg_daily_alert_hours")
            row[f"{k}_avg_alert_duration_min"] = src.get("avg_alert_duration_min")
        rows.append(row)
    return rows


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    store = load_store()
    token = os.getenv(TOKEN_ENV, "").strip()
    if not token and not store["events"]:
        print(f"{TOKEN_ENV} is not configured and no bridge store exists; bridge skipped")
        return

    proxy_cfg = configure_proxies()
    exact_base = exactmod.fetch_city_alerts()
    proxy_base = base.fetch_proxy_alerts()
    cutoffs: dict[str, datetime] = {}
    row_specs: dict[str, tuple[str, str | None, datetime]] = {}

    for key, cfg in exactmod.CITY_CONFIG.items():
        cutoff = max(a.end for a in exact_base[key])
        cutoffs[cfg["hromada"]] = cutoff
        row_specs[key] = (cfg["hromada"], None, cutoff)
    for key, cfg in proxy_cfg.items():
        cutoff = max(a.end for a in proxy_base[key])
        cutoffs[cfg["raion"]] = cutoff
        cutoffs[cfg["oblast"]] = cutoff
        row_specs[key] = (cfg["raion"], cfg["oblast"], cutoff)

    fetch_error = None
    if token:
        try:
            store = merge_history(store, fetch_history(token), cutoffs)
            STORE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("UkraineAlarm API history fetched successfully")
        except Exception as exc:
            fetch_error = f"{type(exc).__name__}: {exc}"
            store["last_fetch_error"] = fetch_error
            if STORE_FILE.exists():
                STORE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("UkraineAlarm API fetch failed; retaining prior bridge store:", fetch_error)
    if not store["events"]:
        return

    now = datetime.now(TZ)
    status: dict[str, dict] = {}
    for key, cfg in exactmod.CITY_CONFIG.items():
        primary, _, cutoff = row_specs[key]
        extra = bridge_events(store, primary, cutoff)
        continuous = bool(store["regions"].get(primary, {}).get("continuous_from_upstream"))
        status[key] = {"primary_region": primary, "primary_continuous": continuous,
                       "bridge_events_applied": len(extra), "upstream_cutoff": cutoff.isoformat(),
                       "latest_bridge_event_end": max((a.end.isoformat() for a in extra), default=None)}
        if not continuous:
            continue
        merged = union([*exact_base[key], *extra], "vadimkin_plus_ukrainealarm_api")
        meta = dict(cities[key].get("meta", {}))
        meta.update({"city_completed_alerts": len(merged), "latest_city_record_start": max(a.start for a in merged).isoformat(),
                     "latest_city_record_end": max(a.end for a in merged).isoformat(),
                     "data_source_kind": "official city-level hromada; Vadimkin history + official UkraineAlarm API bridge",
                     "ukrainealarm_bridge_primary_region": primary, "ukrainealarm_bridge_continuous": True,
                     "ukrainealarm_bridge_events_applied": len(extra)})
        out = build_outputs(merged, now, meta)
        exactmod.enrich_weekly(out, merged)
        exactmod.trim_first_partial_periods(out, min(a.start for a in exact_base[key]).astimezone(TZ).date())
        cities[key] = out

    for key, cfg in proxy_cfg.items():
        primary, optional, cutoff = row_specs[key]
        raion = bridge_events(store, primary, cutoff)
        oblast = bridge_events(store, optional, cutoff) if optional else []
        continuous = bool(store["regions"].get(primary, {}).get("continuous_from_upstream"))
        status[key] = {"primary_region": primary, "optional_oblast_region": optional,
                       "primary_continuous": continuous, "raion_bridge_events_applied": len(raion),
                       "oblast_bridge_events_applied": len(oblast), "upstream_cutoff": cutoff.isoformat(),
                       "latest_bridge_event_end": max((a.end.isoformat() for a in [*raion, *oblast]), default=None)}
        if not continuous:
            continue
        merged = union([*proxy_base[key], *raion, *oblast], "vadimkin_proxy_plus_ukrainealarm_api")
        meta = dict(cities[key].get("meta", {}))
        meta.update({"proxy_completed_alert_episodes": len(merged),
                     "latest_proxy_record_start": max(a.start for a in merged).isoformat(),
                     "latest_proxy_record_end": max(a.end for a in merged).isoformat(),
                     "data_source_kind": "eponymous raion proxy union explicit oblast; Vadimkin history + official UkraineAlarm API bridge",
                     "ukrainealarm_bridge_primary_region": primary, "ukrainealarm_bridge_continuous": True,
                     "ukrainealarm_bridge_raion_events_applied": len(raion), "ukrainealarm_bridge_oblast_events_applied": len(oblast)})
        out = build_outputs(merged, now, meta)
        base.enrich_weekly(out, merged)
        base.trim_to_complete_coverage(out, date.fromisoformat(cfg["coverage_start"]))
        cities[key] = out

    data["cities"] = cities
    keys = [k for k in data.get("multicity_meta", {}).get("production_city_keys", []) if k in cities]
    if keys:
        data["comparison"] = {"monthly": comparison(cities, keys, "monthly"), "weekly": comparison(cities, keys, "weekly")}
    covered = sorted(k for k, v in status.items() if v["primary_continuous"])
    required = sorted(status)
    summary = {
        "source_url": API_URL, "history_limit_per_region": HISTORY_LIMIT,
        "token_present_this_run": bool(token), "last_successful_fetch_at": store.get("last_successful_fetch_at"),
        "last_fetch_error": fetch_error or store.get("last_fetch_error"), "event_store_file": "data/ukrainealarm_bridge.json",
        "event_count": len(store["events"]), "required_rows": required, "continuity_verified_rows": covered,
        "continuity_unverified_rows": sorted(set(required) - set(covered)), "fully_continuous": len(covered) == len(required),
        "rows": status,
    }
    data.setdefault("multicity_meta", {})["official_ukrainealarm_bridge"] = summary
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Official API bridge continuity: {len(covered)}/{len(required)} rows")


if __name__ == "__main__":
    main()
