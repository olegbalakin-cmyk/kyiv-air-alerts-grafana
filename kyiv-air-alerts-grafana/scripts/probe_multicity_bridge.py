#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

import add_duration_unit_switch as exactmod
import expand_multicity_production as base
from update_data import Alert, TZ

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_FILE = ROOT / "data" / "alerts_in_ua_bridge_2026-09-07_16.csv.gz.b64"
BRIDGE_META = ROOT / "data" / "alerts_in_ua_bridge_2026-09-07_16.meta.json"
REPORT_FILE = ROOT / "data" / "multicity_bridge_probe.json"
API_BASE = "https://api.ukrainealarm.com/api/v3"
REGIONS_URL = f"{API_BASE}/regions"
HISTORY_URL = f"{API_BASE}/alerts/regionHistory"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
UTC = timezone.utc
TOLERANCE_SECONDS = 5
MIN_API_INTERVAL_SECONDS = float(os.getenv("UKRAINEALARM_MIN_INTERVAL_SECONDS", "65"))
MAX_401_RETRIES = 2
UPSTREAM_COMMITS_URL = (
    "https://api.github.com/repos/Vadimkin/ukrainian-air-raid-sirens-dataset/commits"
)
UPSTREAM_PATH = "datasets/official_data_uk.csv"

EXACT = {
    "kharkiv": {
        "api_name": "м. Харків та Харківська територіальна громада",
        "oblast": "Харківська область",
        "aliases": [
            "Харківська територіальна громада",
            "Харківська міська територіальна громада",
            "м. Харків",
            "Харків",
        ],
    },
    "zaporizhzhia": {
        "api_name": "м. Запоріжжя та Запорізька територіальна громада",
        "oblast": "Запорізька область",
        "aliases": [
            "Запорізька територіальна громада",
            "Запорізька міська територіальна громада",
            "м. Запоріжжя",
            "Запоріжжя",
        ],
    },
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
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


def norm(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": token,
        "User-Agent": "kyiv-air-alerts-grafana/bridge-probe",
    }


class UkraineAlarmClient:
    """Small client that respects the observed per-key request cadence.

    UkraineAlarm can answer overly frequent authenticated requests with an empty 401.
    We therefore serialize requests and keep a safety margin above one minute.
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.last_request_at: float | None = None
        self.session = requests.Session()

    def _wait_for_slot(self) -> None:
        if self.last_request_at is None:
            return
        elapsed = time.monotonic() - self.last_request_at
        wait = MIN_API_INTERVAL_SECONDS - elapsed
        if wait > 0:
            print(f"UkraineAlarm rate-limit guard: sleeping {wait:.1f}s", flush=True)
            time.sleep(wait)

    def get(self, url: str, *, params: dict | None = None, context: str) -> requests.Response:
        for attempt in range(MAX_401_RETRIES + 1):
            self._wait_for_slot()
            response = self.session.get(
                url,
                headers=api_headers(self.token),
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
                body = response.text.strip().replace("\n", " ")[:300]
                raise RuntimeError(
                    f"{context}: HTTP 401 after {attempt + 1} attempts; response={body!r}"
                )
            retry_after = response.headers.get("Retry-After")
            print(
                f"{context}: HTTP 401, treating as possible cadence limit "
                f"(Retry-After={retry_after!r}); will retry after guard interval",
                flush=True,
            )
        raise AssertionError("unreachable")


def load_bridge() -> tuple[dict[str, list[Alert]], dict]:
    meta = json.loads(BRIDGE_META.read_text(encoding="utf-8"))
    raw = gzip.decompress(
        base64.b64decode(BRIDGE_FILE.read_text(encoding="ascii").strip())
    ).decode("utf-8")
    out: dict[str, list[Alert]] = {}
    for row in csv.DictReader(io.StringIO(raw)):
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        key = (row.get("city_key") or "").strip()
        if key and start and end and end > start:
            out.setdefault(key, []).append(
                Alert(
                    start=start.astimezone(TZ),
                    end=end.astimezone(TZ),
                    source="alerts_in_ua",
                )
            )
    for rows in out.values():
        rows.sort(key=lambda a: a.start)
    return out, meta


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


def resolve(nodes: list[dict], names: list[str], oblast: str) -> dict | None:
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
    if len(matches) == 1:
        return matches[0]
    matches.sort(key=lambda n: (len(n.get("ancestors", [])), n["regionId"]))
    return matches[-1]


def history_rows(client: UkraineAlarmClient, node: dict) -> list[dict]:
    response = client.get(
        HISTORY_URL,
        params={"regionId": node["regionId"]},
        context=f"regionHistory {node['regionName']} ({node['regionId']})",
    )
    payload = response.json()
    groups = [payload] if isinstance(payload, dict) else [x for x in payload if isinstance(x, dict)]
    alarms = []
    for group in groups:
        for alarm in group.get("alarms") or []:
            if not isinstance(alarm, dict) or str(alarm.get("alertType") or "").upper() != "AIR":
                continue
            start = parse_dt(alarm.get("startDate"))
            end = parse_dt(alarm.get("endDate"))
            if start and end and end > start:
                alarms.append({"start": start, "end": end})
    alarms.sort(key=lambda x: x["start"])
    return alarms


def match_event(api_rows: list[dict], bridge_rows: list[Alert]) -> dict | None:
    for api in api_rows:
        for bridge in bridge_rows:
            ds = abs((api["start"] - bridge.start.astimezone(UTC)).total_seconds())
            de = abs((api["end"] - bridge.end.astimezone(UTC)).total_seconds())
            if ds <= TOLERANCE_SECONDS and de <= TOLERANCE_SECONDS:
                return {
                    "api_start": api["start"].isoformat(),
                    "api_end": api["end"].isoformat(),
                    "bridge_start": bridge.start.isoformat(),
                    "bridge_end": bridge.end.isoformat(),
                    "start_delta_seconds": round(ds, 3),
                    "end_delta_seconds": round(de, 3),
                }
    return None


def upstream_snapshot() -> dict:
    """Resolve the last complete local day represented by the stale upstream snapshot.

    The upstream repository's dataset job is a daily snapshot. A commit made on local
    calendar day D safely proves completeness through D-1. This is deliberately more
    conservative than treating each city's last event as the coverage cutoff: a city
    can simply have no alerts for several days.
    """

    response = requests.get(
        UPSTREAM_COMMITS_URL,
        params={"path": UPSTREAM_PATH, "per_page": 1},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "kyiv-air-alerts-grafana/bridge-probe"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise RuntimeError("No upstream commit found for official_data_uk.csv")
    commit_at = parse_dt(payload[0].get("commit", {}).get("committer", {}).get("date"))
    if commit_at is None:
        raise RuntimeError("Could not parse upstream file commit timestamp")
    commit_local = commit_at.astimezone(TZ)
    complete_through = commit_local.date() - timedelta(days=1)
    return {
        "commit_sha": payload[0].get("sha"),
        "commit_at": commit_at.isoformat(),
        "commit_local_date": commit_local.date().isoformat(),
        "complete_through_local_date": complete_through.isoformat(),
    }


def bridge_covers_after_snapshot(meta: dict, complete_through: date) -> bool:
    coverage_start = parse_dt(meta.get("coverage_start"))
    coverage_end = parse_dt(meta.get("coverage_end_exclusive"))
    if not coverage_start or not coverage_end:
        return False
    start_day = coverage_start.astimezone(TZ).date()
    end_day_exclusive = coverage_end.astimezone(TZ).date()
    return start_day <= complete_through < end_day_exclusive


def main() -> None:
    token = os.getenv(TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{TOKEN_ENV} is not configured")

    bridge, meta = load_bridge()
    coverage_start = parse_dt(meta["coverage_start"])
    coverage_end = parse_dt(meta["coverage_end_exclusive"])
    if not coverage_start or not coverage_end:
        raise RuntimeError("Invalid bridge coverage metadata")

    upstream = upstream_snapshot()
    upstream_complete_day = date.fromisoformat(upstream["complete_through_local_date"])
    source_to_static = bridge_covers_after_snapshot(meta, upstream_complete_day)
    print(
        "Upstream snapshot: "
        f"commit={upstream['commit_at']} complete_through={upstream['complete_through_local_date']} "
        f"static_bridge_starts={coverage_start.astimezone(TZ).date()} continuous={source_to_static}",
        flush=True,
    )

    exact_base = exactmod.fetch_city_alerts()
    proxy_base = base.fetch_proxy_alerts()
    specs = {}
    for key, cfg in EXACT.items():
        specs[key] = {
            "kind": "exact",
            "api_name": cfg["api_name"],
            "names": [cfg["api_name"], *cfg["aliases"]],
            "oblast": cfg["oblast"],
            "last_upstream_event_end": max(a.end for a in exact_base[key]),
        }
    for key, cfg in base.PROXY_CONFIG.items():
        specs[key] = {
            "kind": "proxy",
            "api_name": cfg["raion"],
            "names": [cfg["raion"]],
            "oblast": cfg["oblast"],
            "last_upstream_event_end": max(a.end for a in proxy_base[key]),
        }

    client = UkraineAlarmClient(token)
    regions_response = client.get(REGIONS_URL, context="regions")
    nodes = collect_nodes(regions_response.json())

    rows = {}
    for index, (key, spec) in enumerate(specs.items(), start=1):
        node = resolve(nodes, spec["names"], spec["oblast"])
        result = {
            "kind": spec["kind"],
            "api_target": spec["api_name"],
            "oblast": spec["oblast"],
            "last_upstream_event_end": spec["last_upstream_event_end"].isoformat(),
            "upstream_snapshot_complete_through": upstream["complete_through_local_date"],
            "source_to_static_continuous": source_to_static,
            "static_completed_events": len(bridge.get(key, [])),
        }
        if not node:
            result.update(
                {
                    "api_region_found": False,
                    "continuous": False,
                    "reason": "api_region_not_found",
                }
            )
            rows[key] = result
            print(f"[{index}/{len(specs)}] {key}: API region not found", flush=True)
            continue

        try:
            api = history_rows(client, node)
            oldest = min((x["start"] for x in api), default=None)
            newest = max((x["end"] for x in api), default=None)
            overlaps_static_window = bool(
                oldest is not None
                and newest is not None
                and oldest < coverage_end
                and newest >= coverage_start
            )
            match = match_event(api, bridge.get(key, []))
            continuous = bool(source_to_static and match)
            result.update(
                {
                    "api_region_found": True,
                    "api_region_id": node["regionId"],
                    "api_region_name": node["regionName"],
                    "api_history_completed_air": len(api),
                    "api_oldest_start": oldest.isoformat() if oldest else None,
                    "api_latest_end": newest.isoformat() if newest else None,
                    "api_overlaps_static_bridge_window": overlaps_static_window,
                    "matched_overlap_event": match,
                    "continuous": continuous,
                    "reason": (
                        "upstream_snapshot_static_bridge_api_event_match"
                        if continuous
                        else "no_verified_static_api_event_match"
                    ),
                }
            )
        except Exception as exc:
            result.update(
                {
                    "api_region_found": True,
                    "api_region_id": node["regionId"],
                    "continuous": False,
                    "reason": f"api_error: {type(exc).__name__}: {exc}",
                }
            )
        rows[key] = result
        print(
            f"[{index}/{len(specs)}] {key}: continuous={result['continuous']} "
            f"region={result.get('api_region_id')} history={result.get('api_history_completed_air')} "
            f"match={bool(result.get('matched_overlap_event'))}",
            flush=True,
        )

    verified = sorted(k for k, v in rows.items() if v["continuous"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "static_bridge": {
            "source": meta.get("source_url"),
            "coverage_start": meta["coverage_start"],
            "coverage_end_exclusive": meta["coverage_end_exclusive"],
            "completed_event_rows": meta.get("completed_event_rows"),
        },
        "upstream_snapshot": upstream,
        "ukrainealarm_request_guard_seconds": MIN_API_INTERVAL_SECONDS,
        "kyiv_note": "Kyiv uses its independent current source and does not require this bridge.",
        "required_non_kyiv_rows": sorted(rows),
        "verified_rows": verified,
        "unverified_rows": sorted(set(rows) - set(verified)),
        "fully_continuous": len(verified) == len(rows),
        "rows": rows,
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Continuity verified: {len(verified)}/{len(rows)} non-Kyiv rows",
        flush=True,
    )
    if not report["fully_continuous"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
