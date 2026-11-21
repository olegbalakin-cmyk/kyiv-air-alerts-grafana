#!/usr/bin/env python3
"""Offline, non-publishing Kyiv 24-27 Feb 2022 start-only audit from alerts.in.ua exports.

The exported end may be an imputed 30/60-minute placeholder. This module NEVER
creates interval rows, writes to Neon, or modifies canonical Git JSON.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")
FIRST = datetime(2022, 2, 24, tzinfo=KYIV_TZ)
LAST = datetime(2022, 2, 28, tzinfo=KYIV_TZ)
REQUIRED = {"Оголошено о", "Закінчено о", "Регіон", "Країна", "Тип"}
CANONICAL_NAMES = {"alerts_combined.json", "dashboard_data.json", "monthly.csv", "weekly.csv"}


def parse_local(value: str) -> datetime:
    dt = datetime.strptime(value.strip(), "%d.%m.%Y, %H:%M:%S")
    return dt.replace(tzinfo=KYIV_TZ)


def parse_existing(path: Path | None) -> list[datetime]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Existing canonical alerts must be a JSON array")
    out = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict) or not item.get("start") or not item.get("end"):
            raise ValueError(f"Invalid canonical alert at index {i}")
        start = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(item["end"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError(f"Invalid canonical interval at index {i}")
        out.append(start.astimezone(timezone.utc))
    return out


def build_report(paths: list[Path], existing_path: Path | None = None) -> dict:
    if len(paths) != 4:
        raise ValueError("Exactly four daily CSV exports for 2022-02-24..27 required")
    existing = parse_existing(existing_path)
    seen_sources = []
    candidates = {}
    for path in paths:
        raw = path.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f"Wrong alerts.in.ua CSV columns: {path}")
        matched = []
        all_starts = []
        for line_no, row in enumerate(reader, start=2):
            if row.get("Країна", "").strip() != "Україна":
                continue
            started = parse_local(row["Оголошено о"])
            all_starts.append(started.date().isoformat())
            if row.get("Регіон", "").strip() != "м. Київ" or row.get("Тип", "").strip() != "Повітряна тривога":
                continue
            if not FIRST <= started < LAST:
                raise ValueError(f"Kyiv event outside 2022-02-24..27 at {path}:{line_no}")
            exported_end = parse_local(row["Закінчено о"])
            if exported_end <= started:
                raise ValueError(f"Non-positive exported interval at {path}:{line_no}")
            key = started.astimezone(timezone.utc).isoformat()
            record = candidates.setdefault(key, {
                "start": started.isoformat(), "end": None,
                "duration_seconds": None, "end_status": "UNVERIFIED_EXPORT_PLACEHOLDER",
                "raw_exported_end_not_for_statistics": exported_end.isoformat(),
                "record_type": "OBSERVED_START_ONLY", "city_key": "kyiv",
                "confidence": "PROVISIONAL_SOURCE", "evidence": [],
            })
            record["evidence"].append({"source": "alerts.in.ua CSV export",
                "source_file": path.name, "source_sha256": source_hash, "line": line_no})
            matched.append(key)
        if not matched:
            raise ValueError(f"No Kyiv alert starts in {path}")
        seen_sources.append({"file": path.name, "sha256": source_hash, "kyiv_rows": len(matched),
                             "dates_observed": sorted(set(all_starts))})
    records = [candidates[k] for k in sorted(candidates)]
    days = Counter(r["start"][:10] for r in records)
    if set(days) != {"2022-02-24", "2022-02-25", "2022-02-26", "2022-02-27"}:
        raise ValueError("Incomplete Kyiv four-day coverage")
    for r in records:
        t = datetime.fromisoformat(r["start"]).astimezone(timezone.utc)
        overlaps = [x.isoformat() for x in existing if abs((x - t).total_seconds()) <= 180]
        r["review_status"] = "POSSIBLE_CANONICAL_DUPLICATE" if overlaps else "START_CANDIDATE"
        r["canonical_matches_within_3min"] = overlaps
    return {
        "schema": "kyiv-early-2022-start-only-shadow-v1", "publish_allowed": False,
        "neon_write_allowed": False, "canonical_intervals": [],
        "input_existing_checked": existing_path is not None,
        "source_methodology": "https://blog.alerts.in.ua/p/data-sources",
        "source_files": seen_sources,
        "summary": {"unique_kyiv_starts": len(records), "possible_duplicates":
                    sum(r["review_status"] != "START_CANDIDATE" for r in records),
                    "all_exported_ends_unverified": True},
        "daily_preview": [{"date": d, "observed_starts_provisional": days[d],
                           "hours_under_alert": None, "average_alert_duration": None,
                           "complete_coverage_verified": False}
                          for d in sorted(days)],
        "candidates": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, action="append", required=True)
    parser.add_argument("--existing", type=Path,
                        help="Optional read-only canonical alerts_combined.json for duplicate audit")
    parser.add_argument("--out", type=Path, help="Shadow JSON output (otherwise stdout)")
    args = parser.parse_args()
    result = build_report(args.csv, args.existing)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        if args.out.name in CANONICAL_NAMES or args.out.exists():
            parser.error("Refusing to overwrite a canonical or existing file")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
