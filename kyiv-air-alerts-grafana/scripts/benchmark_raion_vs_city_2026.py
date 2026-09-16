from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SOURCE_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_uk.csv"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2027, 1, 1, tzinfo=timezone.utc)

CASES = {
    "kharkiv": {
        "display_name": "Харків",
        "oblast": "Харківська область",
        "raion": "Харківський район",
        "hromada": "м. Харків та Харківська територіальна громада",
    },
    "zaporizhzhia": {
        "display_name": "Запоріжжя",
        "oblast": "Запорізька область",
        "raion": "Запорізький район",
        "hromada": "м. Запоріжжя та Запорізька територіальна громада",
    },
}

OUT_DIR = Path("data")
OUT_JSON = OUT_DIR / "raion_vs_exact_city_2026.json"
OUT_CSV = OUT_DIR / "raion_vs_exact_city_2026.csv"


def parse_dt(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clip_interval(start: datetime, end: datetime):
    start = max(start, START)
    end = min(end, END)
    if end <= start:
        return None
    return (start, end)


def merge_intervals(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def duration_hours(intervals):
    return sum((b - a).total_seconds() for a, b in intervals) / 3600


def intersection(a, b):
    a = merge_intervals(a)
    b = merge_intervals(b)
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if start < end:
            out.append((start, end))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return merge_intervals(out)


def subtract(a, b):
    a = merge_intervals(a)
    b = merge_intervals(b)
    out = []
    j = 0
    for start, end in a:
        cur = start
        while j < len(b) and b[j][1] <= cur:
            j += 1
        k = j
        while k < len(b) and b[k][0] < end:
            if b[k][0] > cur:
                out.append((cur, min(b[k][0], end)))
            cur = max(cur, b[k][1])
            if cur >= end:
                break
            k += 1
        if cur < end:
            out.append((cur, end))
    return merge_intervals(out)


def union(a, b):
    return merge_intervals(list(a) + list(b))


def pct(num, den):
    return round(num / den * 100, 2) if den else None


def main():
    resp = requests.get(SOURCE_URL, timeout=120)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    reader = csv.DictReader(lines)

    collected = {
        key: {"city": [], "raion": []}
        for key in CASES
    }

    for row in reader:
        oblast = (row.get("oblast") or "").strip()
        level = (row.get("level") or "").strip()
        raion = (row.get("raion") or "").strip()
        hromada = (row.get("hromada") or "").strip()
        started = (row.get("started_at") or "").strip()
        finished = (row.get("finished_at") or "").strip()
        if not started or not finished:
            continue
        try:
            iv = clip_interval(parse_dt(started), parse_dt(finished))
        except Exception:
            continue
        if not iv:
            continue

        for key, cfg in CASES.items():
            if oblast != cfg["oblast"]:
                continue
            if level == "hromada" and hromada == cfg["hromada"]:
                collected[key]["city"].append(iv)
            elif level == "raion" and raion == cfg["raion"]:
                collected[key]["raion"].append(iv)

    results = []
    for key, cfg in CASES.items():
        city = merge_intervals(collected[key]["city"])
        raion = merge_intervals(collected[key]["raion"])
        overlap = intersection(city, raion)
        city_only = subtract(city, raion)
        raion_only = subtract(raion, city)
        either = union(city, raion)

        city_h = duration_hours(city)
        raion_h = duration_hours(raion)
        overlap_h = duration_hours(overlap)
        city_only_h = duration_hours(city_only)
        raion_only_h = duration_hours(raion_only)
        union_h = duration_hours(either)

        results.append({
            "city": key,
            "display_name": cfg["display_name"],
            "oblast": cfg["oblast"],
            "exact_city_source": cfg["hromada"],
            "raion_source": cfg["raion"],
            "city_alert_hours": round(city_h, 3),
            "raion_alert_hours": round(raion_h, 3),
            "overlap_hours": round(overlap_h, 3),
            "city_only_hours": round(city_only_h, 3),
            "raion_only_hours": round(raion_only_h, 3),
            "union_hours": round(union_h, 3),
            "city_time_covered_by_raion_pct": pct(overlap_h, city_h),
            "raion_time_matching_city_pct": pct(overlap_h, raion_h),
            "jaccard_pct": pct(overlap_h, union_h),
            "raion_total_duration_bias_vs_city_pct": round((raion_h - city_h) / city_h * 100, 2) if city_h else None,
            "city_interval_count_after_merge": len(city),
            "raion_interval_count_after_merge": len(raion),
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "source": SOURCE_URL,
        "period": "2026",
        "definition": {
            "city_time_covered_by_raion_pct": "share of exact-city alert time that overlaps the raion proxy",
            "raion_time_matching_city_pct": "share of raion alert time that overlaps exact-city alerts",
            "jaccard_pct": "overlap / union of alert-time intervals",
            "raion_total_duration_bias_vs_city_pct": "(raion alert hours - exact-city alert hours) / exact-city alert hours",
        },
    }
    OUT_JSON.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = list(results[0].keys())
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("city\tcity_h\traion_h\toverlap_h\tcity_only_h\traion_only_h\tcoverage%\tprecision%\tjaccard%\tbias%")
    for r in results:
        print(
            f"{r['display_name']}\t{r['city_alert_hours']}\t{r['raion_alert_hours']}\t{r['overlap_hours']}\t"
            f"{r['city_only_hours']}\t{r['raion_only_hours']}\t{r['city_time_covered_by_raion_pct']}\t"
            f"{r['raion_time_matching_city_pct']}\t{r['jaccard_pct']}\t{r['raion_total_duration_bias_vs_city_pct']}"
        )


if __name__ == "__main__":
    main()
