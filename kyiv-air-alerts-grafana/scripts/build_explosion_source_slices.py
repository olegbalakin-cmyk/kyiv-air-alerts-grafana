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

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HANDOFF = DATA / "explosion_metric_handoff"
SUBSLICES_CSV = HANDOFF / "RESEARCH_SUBSLICES_2026-09-19.csv"
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


def load_subslices() -> list[dict[str, str]]:
    with SUBSLICES_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals, key=lambda x: x[0]):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(start, end) for start, end in merged]


def production_episodes(source_bytes: bytes, wanted_keys: set[str]) -> tuple[dict[str, list[tuple[datetime, datetime]]], dict[str, dict]]:
    # Reproduce the historical adapters used by the WIP production pipeline:
    #   proxy cities = union(eponymous raion, explicit oblast), clipped at coverage start;
    #   Kharkiv/Zaporizhzhia = validated exact-city hromada stream from valid_from.
    proxy_cfg = extended.configure_all_proxies()
    exact_cfg = exactmod.CITY_CONFIG

    proxy_keys = wanted_keys & set(proxy_cfg)
    exact_keys = wanted_keys & set(exact_cfg)
    unknown = wanted_keys - proxy_keys - exact_keys
    if unknown:
        raise RuntimeError(f"No production historical adapter for: {sorted(unknown)}")

    proxy_by_oblast = {proxy_cfg[key]["oblast"]: key for key in proxy_keys}
    exact_by_hromada = {exact_cfg[key]["hromada"]: key for key in exact_keys}

    raw_intervals: dict[str, list[tuple[datetime, datetime]]] = {
        key: [] for key in wanted_keys
    }
    seen_proxy: dict[str, set[tuple[str, str, str]]] = {
        key: set() for key in proxy_keys
    }
    seen_exact: dict[str, set[tuple[str, str]]] = {
        key: set() for key in exact_keys
    }

    text = source_bytes.decode("utf-8-sig")
    for row in csv.DictReader(io.StringIO(text)):
        level = (row.get("level") or "").strip()
        oblast = (row.get("oblast") or "").strip()
        raion = (row.get("raion") or "").strip()
        hromada = (row.get("hromada") or "").strip()
        s = (row.get("started_at") or "").strip()
        e = (row.get("finished_at") or "").strip()
        if not s or not e:
            continue

        proxy_key = proxy_by_oblast.get(oblast)
        if proxy_key:
            cfg = proxy_cfg[proxy_key]
            if level == "oblast" or (level == "raion" and raion == cfg["raion"]):
                marker = (level, s, e)
                if marker not in seen_proxy[proxy_key]:
                    try:
                        start = proxymod.parse_source_dt(s)
                        end = proxymod.parse_source_dt(e)
                    except ValueError:
                        start = end = None
                    if start and end and end > start:
                        cutoff = proxymod.coverage_start_dt(cfg["coverage_start"])
                        if end > cutoff:
                            raw_intervals[proxy_key].append((max(start, cutoff), end))
                            seen_proxy[proxy_key].add(marker)

        exact_key = exact_by_hromada.get(hromada) if level == "hromada" else None
        if exact_key:
            marker = (s, e)
            if marker in seen_exact[exact_key]:
                continue
            try:
                start = exactmod.parse_source_dt(s)
                end = exactmod.parse_source_dt(e)
            except ValueError:
                continue
            if end <= start:
                continue
            valid_from = datetime.fromisoformat(exact_cfg[exact_key]["valid_from"]).astimezone(TZ)
            if start < valid_from:
                continue
            raw_intervals[exact_key].append((start, end))
            seen_exact[exact_key].add(marker)

    episodes = {key: merge_intervals(raw_intervals[key]) for key in wanted_keys}
    meta: dict[str, dict] = {}
    for key in wanted_keys:
        if key in proxy_keys:
            cfg = proxy_cfg[key]
            meta[key] = {
                "type": "production_proxy_union",
                "name": f"{cfg['raion']} + explicit {cfg['oblast']}",
                "coverage_start": cfg["coverage_start"],
            }
        else:
            cfg = exact_cfg[key]
            meta[key] = {
                "type": "production_exact_city_union",
                "name": cfg["hromada"],
                "valid_from": cfg["valid_from"],
            }
    return episodes, meta


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
        "adapter": "WIP production historical adapters: proxy raion+oblast union; exact-city hromada union",
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
            f"{x['task_id']}:{x['episode_count']}!={x['frozen_denominator']}"
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
