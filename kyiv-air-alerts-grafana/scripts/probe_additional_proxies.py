#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from update_data import Alert, TZ

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_FILE = ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.csv.gz.b64"
BRIDGE_META = ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.meta.json"
REPORT_FILE = ROOT / "data" / "additional_proxy_bridge_probe.json"
API_BASE = "https://api.ukrainealarm.com/api/v3"
REGIONS_URL = f"{API_BASE}/regions"
HISTORY_URL = f"{API_BASE}/alerts/regionHistory"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
UTC = timezone.utc
EXACT_TOLERANCE_SECONDS = 5
MIN_API_INTERVAL_SECONDS = float(os.getenv("UKRAINEALARM_MIN_INTERVAL_SECONDS", "70"))
MAX_401_RETRIES = 2

# First pass already verified Lutsk, Ivano-Frankivsk and Mykolaiv.
# This diagnostic retry focuses only on the four unresolved rows.
SPECS = {
    "uzhhorod": {"raion": "Ужгородський район", "oblast": "Закарпатська область"},
    "chernivtsi": {"raion": "Чернівецький район", "oblast": "Чернівецька область"},
    "ternopil": {"raion": "Тернопільський район", "oblast": "Тернопільська область"},
    "kherson": {"raion": "Херсонський район", "oblast": "Херсонська область"},
}


def parse_dt(value):
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def norm(s):
    return " ".join(str(s).casefold().replace("’", "'").split())


def headers(token):
    return {
        "Accept": "application/json",
        "Authorization": token,
        "User-Agent": "kyiv-air-alerts-grafana/additional-proxy-probe",
    }


def load_bridge():
    meta = json.loads(BRIDGE_META.read_text(encoding="utf-8"))
    raw = gzip.decompress(
        base64.b64decode(BRIDGE_FILE.read_text(encoding="ascii").strip())
    ).decode("utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(raw)):
        s = parse_dt(row.get("start"))
        e = parse_dt(row.get("end"))
        key = (row.get("city_key") or "").strip()
        if key and s and e and e > s:
            out.setdefault(key, []).append(
                Alert(start=s.astimezone(TZ), end=e.astimezone(TZ), source="alerts_in_ua")
            )
    for rows in out.values():
        rows.sort(key=lambda a: a.start)
    return out, meta


def collect_nodes(payload):
    nodes = []
    seen = set()

    def walk(v, ancestors=()):
        if isinstance(v, list):
            for x in v:
                walk(x, ancestors)
            return
        if not isinstance(v, dict):
            return
        rid = v.get("regionId")
        name = str(v.get("regionName") or "").strip()
        child = ancestors
        if rid is not None and name:
            k = (str(rid), name)
            if k not in seen:
                seen.add(k)
                nodes.append(
                    {
                        "regionId": str(rid),
                        "regionName": name,
                        "ancestors": list(ancestors),
                    }
                )
            child = (*ancestors, name)
        for x in v.values():
            if isinstance(x, (dict, list)):
                walk(x, child)

    walk(payload)
    return nodes


def resolve(nodes, raion, oblast):
    matches = [n for n in nodes if norm(n["regionName"]) == norm(raion)]
    scoped = [
        n
        for n in matches
        if norm(oblast) in {norm(a) for a in n.get("ancestors", [])}
    ]
    if scoped:
        matches = scoped
    return matches[-1] if matches else None


class Client:
    def __init__(self, token):
        self.token = token
        self.last = None
        self.s = requests.Session()

    def _wait(self):
        if self.last is None:
            return
        wait = MIN_API_INTERVAL_SECONDS - (time.monotonic() - self.last)
        if wait > 0:
            print(f"rate-limit guard: sleeping {wait:.1f}s", flush=True)
            time.sleep(wait)

    def get(self, url, params=None, context="request"):
        for attempt in range(MAX_401_RETRIES + 1):
            self._wait()
            r = self.s.get(
                url,
                headers=headers(self.token),
                params=params,
                timeout=60,
            )
            self.last = time.monotonic()
            if r.status_code != 401:
                if not r.ok:
                    raise RuntimeError(f"{context}: HTTP {r.status_code}: {r.text[:200]}")
                return r
            if attempt >= MAX_401_RETRIES:
                raise RuntimeError(f"{context}: HTTP 401 after {attempt + 1} attempts")
            print(
                f"{context}: HTTP 401 on attempt {attempt + 1}; retrying after guard interval",
                flush=True,
            )
        raise AssertionError("unreachable")


def api_rows(client, node):
    payload = client.get(
        HISTORY_URL,
        {"regionId": node["regionId"]},
        context=f"regionHistory {node['regionName']} ({node['regionId']})",
    ).json()
    groups = [payload] if isinstance(payload, dict) else [x for x in payload if isinstance(x, dict)]
    out = []
    for g in groups:
        for a in g.get("alarms") or []:
            if str(a.get("alertType") or "").upper() != "AIR":
                continue
            s = parse_dt(a.get("startDate"))
            e = parse_dt(a.get("endDate"))
            if s and e and e > s:
                out.append({"start": s, "end": e})
    return sorted(out, key=lambda x: x["start"])


def exact_match(api, bridge):
    for a in api:
        for b in bridge:
            ds = abs((a["start"] - b.start.astimezone(UTC)).total_seconds())
            de = abs((a["end"] - b.end.astimezone(UTC)).total_seconds())
            if ds <= EXACT_TOLERANCE_SECONDS and de <= EXACT_TOLERANCE_SECONDS:
                return diagnostic_row(a, b, ds, de)
    return None


def diagnostic_row(a, b, ds=None, de=None):
    if ds is None:
        ds = abs((a["start"] - b.start.astimezone(UTC)).total_seconds())
    if de is None:
        de = abs((a["end"] - b.end.astimezone(UTC)).total_seconds())
    adur = (a["end"] - a["start"]).total_seconds()
    bdur = (b.end.astimezone(UTC) - b.start.astimezone(UTC)).total_seconds()
    return {
        "api_start": a["start"].isoformat(),
        "api_end": a["end"].isoformat(),
        "bridge_start": b.start.isoformat(),
        "bridge_end": b.end.isoformat(),
        "start_delta_seconds": round(ds, 3),
        "end_delta_seconds": round(de, 3),
        "duration_delta_seconds": round(abs(adur - bdur), 3),
    }


def nearest_candidates(api, bridge, limit=5):
    candidates = []
    for a in api:
        for b in bridge:
            ds = abs((a["start"] - b.start.astimezone(UTC)).total_seconds())
            de = abs((a["end"] - b.end.astimezone(UTC)).total_seconds())
            score = ds + de
            candidates.append((score, max(ds, de), diagnostic_row(a, b, ds, de)))
    candidates.sort(key=lambda x: (x[0], x[1]))
    return [row for _, _, row in candidates[:limit]]


def serialise_api_rows(api):
    return [
        {"start": row["start"].isoformat(), "end": row["end"].isoformat()}
        for row in api
    ]


def main():
    token = os.getenv(TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{TOKEN_ENV} missing")

    bridge, meta = load_bridge()
    client = Client(token)
    nodes = collect_nodes(client.get(REGIONS_URL, context="regions").json())
    rows = {}

    for i, (key, cfg) in enumerate(SPECS.items(), 1):
        node = resolve(nodes, cfg["raion"], cfg["oblast"])
        result = {
            "raion": cfg["raion"],
            "oblast": cfg["oblast"],
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
            print(f"[{i}/{len(SPECS)}] {key}: region not found", flush=True)
            continue

        try:
            api = api_rows(client, node)
            match = exact_match(api, bridge.get(key, []))
            nearest = nearest_candidates(api, bridge.get(key, []))
            oldest = min((x["start"] for x in api), default=None)
            latest = max((x["end"] for x in api), default=None)
            result.update(
                {
                    "api_region_found": True,
                    "api_region_id": node["regionId"],
                    "api_region_name": node["regionName"],
                    "api_history_completed_air": len(api),
                    "api_oldest_start": oldest.isoformat() if oldest else None,
                    "api_latest_end": latest.isoformat() if latest else None,
                    "matched_overlap_event": match,
                    "nearest_candidates": nearest,
                    "api_history": serialise_api_rows(api),
                    "continuous": bool(match),
                    "reason": "matched_static_and_api_event" if match else "no_exact_overlap_diagnostic_recorded",
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
            f"[{i}/{len(SPECS)}] {key}: continuous={result['continuous']} "
            f"region={result.get('api_region_id')} history={result.get('api_history_completed_air')} "
            f"match={bool(result.get('matched_overlap_event'))}",
            flush=True,
        )
        if result.get("nearest_candidates") and not result.get("matched_overlap_event"):
            print(
                f"  nearest={json.dumps(result['nearest_candidates'][0], ensure_ascii=False)}",
                flush=True,
            )

    verified = sorted(k for k, v in rows.items() if v["continuous"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "bridge_source": meta.get("source_url"),
        "coverage_start": meta.get("coverage_start"),
        "coverage_end_exclusive": meta.get("coverage_end_exclusive"),
        "exact_tolerance_seconds": EXACT_TOLERANCE_SECONDS,
        "request_guard_seconds": MIN_API_INTERVAL_SECONDS,
        "required_rows": sorted(rows),
        "verified_rows": verified,
        "unverified_rows": sorted(set(rows) - set(verified)),
        "fully_continuous": len(verified) == len(rows),
        "rows": rows,
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Retry continuity verified: {len(verified)}/{len(rows)}", flush=True)
    if not report["fully_continuous"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
