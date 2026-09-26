#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")

CITY_KEY = "lviv"
OBLAST = "Львівська область"
RAION = "Львівський район"
COVERAGE_START = date(2025, 9, 1)
HISTORICAL_END_EXCLUSIVE = date(2026, 9, 18)

EXPECTED_FROZEN_COUNT = 120
EXPECTED_BRIDGE_COUNT = 20
EXPECTED_BRIDGE_NEW_COUNT = 6
EXPECTED_BRIDGE_OVERLAP_COUNT = 14
EXPECTED_FINAL_COUNT = 126
EXPECTED_CONTROL_START = "2026-09-01T21:49:49.559255Z"
EXPECTED_CONTROL_END = "2026-09-01T21:57:16.737992Z"
EXPECTED_CONTROL_ID = "56d59bf102df184eda42379a"

EXPECTED_NEW_API_INTERVALS = [
    ("2026-09-01T21:49:49.559255Z", "2026-09-01T21:57:16.737992Z"),
    ("2026-09-12T22:00:05.398348Z", "2026-09-12T22:14:23.315771Z"),
    ("2026-09-13T02:32:14.172141Z", "2026-09-13T06:11:11.976953Z"),
    ("2026-09-15T16:44:13.025549Z", "2026-09-15T17:08:51.287249Z"),
    ("2026-09-16T23:05:54.464221Z", "2026-09-16T23:25:51.608234Z"),
    ("2026-09-17T10:23:09.135819Z", "2026-09-17T10:41:50.457837Z"),
]


def parse_dt(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"Expected timezone-aware timestamp, got {value!r}")
    return dt.astimezone(UTC)


def utc_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_id(city_key: str, start: datetime, end: datetime) -> str:
    return hashlib.sha256(
        f"{city_key}|{utc_z(start)}|{utc_z(end)}".encode("utf-8")
    ).hexdigest()[:24]


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    xs = sorted(intervals, key=lambda x: (x[0], x[1]))
    out: list[list[datetime]] = []
    for start, end in xs:
        if end <= start:
            continue
        if not out or start > out[-1][1]:
            out.append([start, end])
        elif end > out[-1][1]:
            out[-1][1] = end
    return [(start, end) for start, end in out]


def overlap(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    # Production merge joins touching or overlapping intervals.
    return a[0] <= b[1] and b[0] <= a[1]


def load_frozen_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_frozen(rows: list[dict[str, str]]) -> list[tuple[datetime, datetime]]:
    cutoff = datetime.combine(COVERAGE_START, time.min, tzinfo=KYIV_TZ).astimezone(UTC)
    seen: set[tuple[str, str, str]] = set()
    intervals: list[tuple[datetime, datetime]] = []

    for row in rows:
        if (row.get("oblast") or "").strip() != OBLAST:
            continue

        level = (row.get("level") or "").strip()
        raion = (row.get("raion") or "").strip()
        if level != "oblast" and not (level == "raion" and raion == RAION):
            continue

        started = (row.get("started_at") or "").strip()
        finished = (row.get("finished_at") or "").strip()
        if not started or not finished:
            continue

        marker = (level, started, finished)
        if marker in seen:
            continue
        seen.add(marker)

        try:
            start = parse_dt(started)
            end = parse_dt(finished)
        except (TypeError, ValueError):
            continue

        if end <= start or end <= cutoff:
            continue
        start = max(start, cutoff)
        intervals.append((start, end))

    return merge(intervals)


def load_bridge(path: Path) -> list[tuple[datetime, datetime]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    end_exclusive = datetime.combine(
        HISTORICAL_END_EXCLUSIVE, time.min, tzinfo=KYIV_TZ
    ).astimezone(UTC)

    intervals = []
    for row in data.get("events", []):
        if row.get("city_key") != CITY_KEY:
            continue
        if str(row.get("alert_type") or "").upper() != "AIR":
            continue
        start = parse_dt(str(row["start"]))
        end = parse_dt(str(row["end"]))
        if end <= start:
            raise AssertionError(f"Invalid bridge interval: {row}")
        if start >= end_exclusive:
            continue
        intervals.append((start, end))

    return sorted(set(intervals), key=lambda x: (x[0], x[1]))


def serial(intervals: list[tuple[datetime, datetime]]) -> list[tuple[str, str]]:
    return [(utc_z(start), utc_z(end)) for start, end in intervals]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, read-only canonical Lviv historical alert corpus."
    )
    parser.add_argument("--frozen-csv", required=True, type=Path)
    parser.add_argument("--bridge-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-frozen-blob", required=True)
    parser.add_argument("--expected-bridge-blob", required=True)
    parser.add_argument("--upstream-ref", required=True)
    parser.add_argument("--bridge-ref", required=True)
    args = parser.parse_args()

    frozen_bytes = args.frozen_csv.read_bytes()
    bridge_bytes = args.bridge_json.read_bytes()
    frozen_blob = git_blob_sha(frozen_bytes)
    bridge_blob = git_blob_sha(bridge_bytes)

    assert frozen_blob == args.expected_frozen_blob, (
        f"Frozen CSV blob mismatch: expected {args.expected_frozen_blob}, got {frozen_blob}"
    )
    assert bridge_blob == args.expected_bridge_blob, (
        f"Bridge blob mismatch: expected {args.expected_bridge_blob}, got {bridge_blob}"
    )

    frozen_rows = load_frozen_rows(args.frozen_csv)
    frozen = build_frozen(frozen_rows)
    bridge = load_bridge(args.bridge_json)

    assert len(frozen) == EXPECTED_FROZEN_COUNT, (
        f"Expected {EXPECTED_FROZEN_COUNT} frozen episodes, got {len(frozen)}"
    )
    assert len(bridge) == EXPECTED_BRIDGE_COUNT, (
        f"Expected {EXPECTED_BRIDGE_COUNT} persisted Lviv API intervals, got {len(bridge)}"
    )

    bridge_new = [
        interval
        for interval in bridge
        if not any(overlap(interval, frozen_interval) for frozen_interval in frozen)
    ]
    bridge_overlap = [interval for interval in bridge if interval not in bridge_new]

    assert len(bridge_new) == EXPECTED_BRIDGE_NEW_COUNT
    assert len(bridge_overlap) == EXPECTED_BRIDGE_OVERLAP_COUNT
    assert serial(bridge_new) == EXPECTED_NEW_API_INTERVALS, (
        "The six API intervals that add new episodes do not match the audited control set."
    )

    final_intervals = merge([*frozen, *bridge])
    assert len(final_intervals) == EXPECTED_FINAL_COUNT, (
        f"Expected final union count {EXPECTED_FINAL_COUNT}, got {len(final_intervals)}"
    )

    episodes = [
        {
            "city_key": CITY_KEY,
            "episode_id": event_id(CITY_KEY, start, end),
            "start": utc_z(start),
            "end": utc_z(end),
        }
        for start, end in final_intervals
    ]

    ids = [row["episode_id"] for row in episodes]
    assert len(set(ids)) == EXPECTED_FINAL_COUNT, (
        f"Expected {EXPECTED_FINAL_COUNT} unique IDs, got {len(set(ids))}"
    )

    for previous, current in zip(final_intervals, final_intervals[1:]):
        assert previous[1] < current[0], (
            f"Residual overlap/touch after final merge: {serial([previous, current])}"
        )

    control = next(
        (
            row
            for row in episodes
            if row["start"] == EXPECTED_CONTROL_START and row["end"] == EXPECTED_CONTROL_END
        ),
        None,
    )
    assert control is not None, "Control 2026-09-01 episode missing from final corpus"
    assert control["episode_id"] == EXPECTED_CONTROL_ID, (
        f"Control ID mismatch: expected {EXPECTED_CONTROL_ID}, got {control['episode_id']}"
    )

    # Determinism / source-order invariance check.
    frozen_reversed = build_frozen(list(reversed(frozen_rows)))
    bridge_reversed = list(reversed(bridge))
    final_reversed = merge([*frozen_reversed, *bridge_reversed])
    assert serial(final_reversed) == serial(final_intervals), (
        "Final merged corpus changes when source-row order is reversed"
    )
    reversed_ids = [
        event_id(CITY_KEY, start, end) for start, end in final_reversed
    ]
    assert reversed_ids == ids, "Episode IDs are not deterministic under source-row reversal"

    artifact = {
        "schema_version": 1,
        "city_key": CITY_KEY,
        "coverage_start": COVERAGE_START.isoformat(),
        "coverage_end_inclusive": "2026-09-17",
        "inputs": {
            "frozen_official_data_uk": {
                "repository": "Vadimkin/ukrainian-air-raid-sirens-dataset",
                "ref": args.upstream_ref,
                "path": "datasets/official_data_uk.csv",
                "blob_sha": frozen_blob,
            },
            "ukrainealarm_bridge": {
                "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
                "ref": args.bridge_ref,
                "path": "kyiv-air-alerts-grafana/data/ukrainealarm_bridge.json",
                "blob_sha": bridge_blob,
            },
        },
        "contract": {
            "source_geography": {
                "raion": RAION,
                "oblast": OBLAST,
                "rule": "union matching raion intervals and explicit oblast intervals after coverage_start",
            },
            "merge_rule": "sort by start; merge when next.start <= current.end",
            "episode_id": 'SHA256(f"{city_key}|{start_utc_z}|{end_utc_z}")[:24]',
        },
        "checks": {
            "frozen_merged_count": len(frozen),
            "persisted_lviv_api_interval_count": len(bridge),
            "api_intervals_new_vs_frozen": len(bridge_new),
            "api_intervals_overlap_or_refine_frozen": len(bridge_overlap),
            "final_merged_count": len(final_intervals),
            "unique_episode_ids": len(set(ids)),
            "no_residual_overlaps": True,
            "chronological_order": True,
            "source_order_invariant": True,
            "control_episode_verified": True,
        },
        "diagnostics": {
            "api_intervals_new_vs_frozen": [
                {"start": start, "end": end}
                for start, end in serial(bridge_new)
            ],
            "api_intervals_overlap_or_refine_frozen": [
                {"start": start, "end": end}
                for start, end in serial(bridge_overlap)
            ],
            "first_episode": episodes[0],
            "last_episode": episodes[-1],
            "control_episode": control,
        },
        "episodes": episodes,
        "verdict": "LVIV HISTORICAL ALERT CORPUS READY FOR EVIDENCE BINDING",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("LVIV HISTORICAL ALERT CORPUS READY FOR EVIDENCE BINDING")
    print(f"frozen={len(frozen)} bridge={len(bridge)} final={len(final_intervals)}")
    print(f"unique_ids={len(set(ids))} new_api={len(bridge_new)} overlap_api={len(bridge_overlap)}")
    print(f"control={control['episode_id']} {control['start']} -> {control['end']}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
