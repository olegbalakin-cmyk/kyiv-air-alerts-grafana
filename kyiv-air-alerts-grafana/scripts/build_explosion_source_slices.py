#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

import add_duration_unit_switch as exactmod
import expand_multicity_production as proxymod
import extend_remaining_proxies as extended
import apply_ukrainealarm_bridge as bridgemod

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HANDOFF = DATA / "explosion_metric_handoff"
SUBSLICES_CSV = HANDOFF / "RESEARCH_SUBSLICES_2026-09-19.csv"
PARENTS_CSV = HANDOFF / "RESEARCH_SLICES_2026-09-18.csv"
OUT_DIR = HANDOFF / "source_slices"
MANIFEST = HANDOFF / "SOURCE_SLICES_MANIFEST_2026-09-19.json"
SOURCE_URL = proxymod.CITY_SOURCE_URL
TZ = proxymod.TZ
UTC = timezone.utc


def utc_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_id(city_key: str, start: datetime, end: datetime) -> str:
    return hashlib.sha256(
        f"{city_key}|{utc_z(start)}|{utc_z(end)}".encode("utf-8")
    ).hexdigest()[:24]


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_subslices() -> list[dict[str, str]]:
    return load_csv(SUBSLICES_CSV)


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals, key=lambda x: x[0]):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(start, end) for start, end in merged]


def production_episodes(source_bytes: bytes, wanted_keys: set[str]) -> tuple[dict[str, list[tuple[datetime, datetime]]], dict[str, dict]]:
    # Reproduce the exact assembled WIP production episode list:
    # historical adapter + Alerts.in.ua seam + persisted UkraineAlarm continuation.
    # The historical adapters download the same public upstream CSV used here.
    proxy_cfg = extended.configure_all_proxies()
    proxy_base = proxymod.fetch_proxy_alerts()
    exact_base = exactmod.fetch_city_alerts()
    static, static_info = bridgemod.load_static_bridge()
    store = bridgemod.load_store()

    proxy_keys = wanted_keys & set(proxy_cfg)
    exact_keys = wanted_keys & set(exactmod.CITY_CONFIG)
    unknown = wanted_keys - proxy_keys - exact_keys
    if unknown:
        raise RuntimeError(f"No production adapter for: {sorted(unknown)}")

    episodes: dict[str, list[tuple[datetime, datetime]]] = {}
    meta: dict[str, dict] = {}
    for key in sorted(wanted_keys):
        if key in exact_keys:
            base_alerts = exact_base[key]
            cfg = exactmod.CITY_CONFIG[key]
            source_type = "production_exact_city_assembled"
            source_name = cfg["hromada"]
            source_extra = {"valid_from": cfg["valid_from"]}
        else:
            base_alerts = proxy_base[key]
            cfg = proxy_cfg[key]
            source_type = "production_proxy_assembled"
            source_name = f"{cfg['raion']} + explicit {cfg['oblast']}"
            source_extra = {"coverage_start": cfg["coverage_start"]}

        region = (store.get("regions") or {}).get(key) or {}
        continuous = bool(region.get("continuous"))
        api_alerts = bridgemod.api_store_alerts(store, key) if continuous else []
        static_alerts = static.get(key) or []
        combined = bridgemod.union_alerts(
            [*base_alerts, *static_alerts, *api_alerts],
            "historical_plus_alertsinua_plus_ukrainealarm",
        )
        episodes[key] = [(a.start, a.end) for a in combined]
        meta[key] = {
            "type": source_type,
            "name": source_name,
            **source_extra,
            "static_bridge_events": len(static_alerts),
            "ukrainealarm_bridge_events": len(api_alerts),
            "ukrainealarm_bridge_continuous": continuous,
            "static_bridge_coverage_start": static_info.get("coverage_start"),
            "static_bridge_coverage_end_exclusive": static_info.get("coverage_end_exclusive"),
        }
    return episodes, meta

def reconcile_parent_boundaries(
    by_city: dict[str, list[tuple[datetime, datetime]]],
    source_meta: dict[str, dict],
    subslice_rows: list[dict[str, str]],
) -> list[dict]:
    parent_rows = {row["task_id"]: row for row in load_csv(PARENTS_CSV)}
    represented = sorted({row["parent_task_id"] for row in subslice_rows})
    exclusions: list[dict] = []

    for parent_id in represented:
        parent = parent_rows[parent_id]
        city_key = parent["city_key"]
        date_from = parent["episode_start_date_from"]
        date_to = parent["episode_start_date_to"]
        frozen = int(parent["frozen_denominator"])
        parent_events = [
            (start, end)
            for start, end in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        ]
        if len(parent_events) == frozen:
            continue
        if len(parent_events) != frozen + 1:
            continue

        smeta = source_meta[city_key]
        boundary: datetime | None = None
        reason: str | None = None
        if smeta["type"] == "production_proxy_assembled":
            if date_from == smeta.get("coverage_start"):
                boundary = proxymod.coverage_start_dt(smeta["coverage_start"])
                reason = "exclude clipped carry-in at proxy coverage_start from alert-start denominator"
        elif smeta["type"] == "production_exact_city_assembled":
            valid_from = smeta.get("valid_from")
            if valid_from:
                candidate = datetime.fromisoformat(valid_from).astimezone(TZ)
                if date_from == candidate.date().isoformat():
                    boundary = candidate
                    reason = "exclude exact adapter transition-boundary seed to preserve frozen parent denominator"

        if boundary is None:
            continue
        matches = [
            (start, end)
            for start, end in parent_events
            if start == boundary
        ]
        if len(matches) != 1:
            continue

        target = matches[0]
        by_city[city_key] = [
            pair for pair in by_city[city_key] if pair != target
        ]
        exclusions.append(
            {
                "parent_task_id": parent_id,
                "city_key": city_key,
                "alert_start": utc_z(target[0]),
                "alert_end": utc_z(target[1]),
                "reason": reason,
                "before": frozen + 1,
                "after": frozen,
            }
        )

    # Parent denominators are the hard contract. Fail if any represented parent
    # still differs after the narrowly-defined boundary reconciliation.
    bad = []
    for parent_id in represented:
        parent = parent_rows[parent_id]
        city_key = parent["city_key"]
        date_from = parent["episode_start_date_from"]
        date_to = parent["episode_start_date_to"]
        frozen = int(parent["frozen_denominator"])
        actual = sum(
            1
            for start, _ in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        )
        if actual != frozen:
            bad.append(f"{parent_id}:{actual}!={frozen}")
    if bad:
        raise RuntimeError(
            "Parent denominator mismatch after boundary reconciliation: "
            + ", ".join(bad)
        )
    return exclusions


def main() -> None:
    response = requests.get(
        SOURCE_URL,
        timeout=240,
        headers={"User-Agent": "kyiv-air-alerts-grafana source-slice builder"},
    )
    response.raise_for_status()
    source_bytes = response.content
    source_sha = git_blob_sha(source_bytes)

    rows = load_subslices()
    wanted_keys = {row["city_key"] for row in rows}
    by_city, source_meta = production_episodes(source_bytes, wanted_keys)
    boundary_exclusions = reconcile_parent_boundaries(by_city, source_meta, rows)

    built: list[tuple[Path, dict]] = []
    manifest_rows: list[dict] = []
    mismatches: list[dict] = []

    for row in rows:
        task_id = row["task_id"]
        city_key = row["city_key"]
        date_from = row["episode_start_date_from"]
        date_to = row["episode_start_date_to"]
        expected = int(row["frozen_denominator"])

        events = [
            (start, end)
            for start, end in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        ]
        events.sort(key=lambda x: (x[0], x[1]))

        sigs = {(utc_z(start), utc_z(end)) for start, end in events}
        if len(sigs) != len(events):
            raise RuntimeError(f"Duplicate production episode signatures in {task_id}")

        actual = len(events)
        start_day_events = [
            utc_z(start)
            for start, _ in by_city[city_key]
            if start.astimezone(TZ).date().isoformat() == date_from
        ]
        start_day_count = len(start_day_events)
        smeta = source_meta[city_key]
        manifest_row = {
            "task_id": task_id,
            "parent_task_id": row["parent_task_id"],
            "city_key": city_key,
            "source_type": smeta["type"],
            "source_name": smeta["name"],
            "episode_start_range": [date_from, date_to],
            "frozen_denominator": expected,
            "episode_count": actual,
            "matches_frozen_denominator": actual == expected,
            "source_start_day_count": start_day_count,
            "source_start_day_starts": start_day_events,
        }
        manifest_rows.append(manifest_row)
        if actual != expected:
            mismatches.append(manifest_row)
            continue

        payload = {
            "schema_version": 1,
            "task_id": task_id,
            "parent_task_id": row["parent_task_id"],
            "city_key": city_key,
            "city": row["city_label"],
            "source": {
                "url": SOURCE_URL,
                "git_blob_sha": source_sha,
                **smeta,
            },
            "assignment_rule": "alert start date in Europe/Kyiv",
            "episode_start_range": [date_from, date_to],
            "frozen_denominator": expected,
            "episode_count": actual,
            "episodes": [
                {
                    "episode_id": event_id(city_key, start, end),
                    "alert_start": utc_z(start),
                    "alert_end": utc_z(end),
                    "alert_start_date_kyiv": start.astimezone(TZ).date().isoformat(),
                }
                for start, end in events
            ],
        }
        built.append((OUT_DIR / f"{task_id}_alerts.json", payload))

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "source_git_blob_sha": source_sha,
        "adapter": "assembled WIP production episodes: historical adapter + Alerts.in.ua seam + persisted UkraineAlarm continuation",
        "boundary_exclusions": boundary_exclusions,
        "subslice_count": len(rows),
        "all_match_frozen_denominator": not mismatches,
        "mismatches": mismatches,
        "subslices": manifest_rows,
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if mismatches:
        details = ", ".join(
            f"{x['task_id']}:{x['episode_count']}!={x['frozen_denominator']}[startday={x['source_start_day_count']}:{'|'.join(x['source_start_day_starts'])}]"
            for x in mismatches
        )
        raise RuntimeError(
            f"Frozen denominator mismatch; source slices not written: {details}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, payload in built:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    print(
        json.dumps(
            {
                "source_git_blob_sha": source_sha,
                "subslice_count": len(rows),
                "written": len(built),
                "all_match_frozen_denominator": True,
                "min_denominator": min(int(r["frozen_denominator"]) for r in rows),
                "max_denominator": max(int(r["frozen_denominator"]) for r in rows),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
