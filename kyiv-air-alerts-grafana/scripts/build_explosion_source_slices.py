#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from audit_city_sources import CITY_CONFIG, DATA_URL, TZ, collect, source_events

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HANDOFF = DATA / "explosion_metric_handoff"
SUBSLICES_CSV = HANDOFF / "RESEARCH_SUBSLICES_2026-09-19.csv"
OUT_DIR = HANDOFF / "source_slices"
MANIFEST = HANDOFF / "SOURCE_SLICES_MANIFEST_2026-09-19.json"
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


def main() -> None:
    response = requests.get(
        DATA_URL,
        timeout=240,
        headers={"User-Agent": "kyiv-air-alerts-grafana source-slice builder"},
    )
    response.raise_for_status()
    source_bytes = response.content
    source_sha = git_blob_sha(source_bytes)

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(source_bytes)
        source_path = Path(tmp.name)

    try:
        grouped = collect(source_path)
    finally:
        source_path.unlink(missing_ok=True)

    configs = {cfg["key"]: cfg for cfg in CITY_CONFIG}
    rows = load_subslices()
    built: list[tuple[Path, dict]] = []
    manifest_rows: list[dict] = []
    mismatches: list[dict] = []

    for row in rows:
        task_id = row["task_id"]
        city_key = row["city_key"]
        cfg = configs.get(city_key)
        if not cfg:
            raise RuntimeError(f"No city source config for {city_key}")

        all_events, source_type, source_name = source_events(cfg, grouped)
        date_from = row["episode_start_date_from"]
        date_to = row["episode_start_date_to"]
        expected = int(row["frozen_denominator"])
        events = [
            e
            for e in all_events
            if date_from <= e.start.astimezone(TZ).date().isoformat() <= date_to
        ]
        events.sort(key=lambda e: (e.start, e.end))

        sigs = {(utc_z(e.start), utc_z(e.end)) for e in events}
        if len(sigs) != len(events):
            raise RuntimeError(f"Duplicate event signatures in {task_id}")

        actual = len(events)
        manifest_row = {
            "task_id": task_id,
            "parent_task_id": row["parent_task_id"],
            "city_key": city_key,
            "source_type": source_type,
            "source_name": source_name,
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
                "url": DATA_URL,
                "git_blob_sha": source_sha,
                "type": source_type,
                "name": source_name,
            },
            "assignment_rule": "alert start date in Europe/Kyiv",
            "episode_start_range": [date_from, date_to],
            "frozen_denominator": expected,
            "episode_count": actual,
            "episodes": [
                {
                    "episode_id": event_id(city_key, e.start, e.end),
                    "alert_start": utc_z(e.start),
                    "alert_end": utc_z(e.end),
                    "alert_start_date_kyiv": e.start.astimezone(TZ).date().isoformat(),
                }
                for e in events
            ],
        }
        built.append((OUT_DIR / f"{task_id}_alerts.json", payload))

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": DATA_URL,
        "source_git_blob_sha": source_sha,
        "subslice_count": len(rows),
        "all_match_frozen_denominator": not mismatches,
        "mismatches": mismatches,
        "subslices": manifest_rows,
    }

    if mismatches:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        details = ", ".join(
            f"{x['task_id']}:{x['episode_count']}!={x['frozen_denominator']}"
            for x in mismatches
        )
        raise RuntimeError(f"Frozen denominator mismatch; source slices not written: {details}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, payload in built:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
