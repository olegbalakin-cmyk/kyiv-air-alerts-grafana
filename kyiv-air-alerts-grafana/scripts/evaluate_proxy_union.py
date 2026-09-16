from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

SOURCE_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_uk.csv"
KYIV_TZ = ZoneInfo("Europe/Kyiv")
END_2026 = datetime(2027, 1, 1, tzinfo=timezone.utc)
START_2026 = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Day-level rollout dates. Local midnight is used as the reproducible cutoff when
# the official source establishes a date but not an exact start time.
PROXIES = {
    "cherkasy": {"display_name": "Черкаси", "oblast": "Черкаська область", "raion": "Черкаський район", "coverage_start": "2025-01-10", "basis": "official_rollout"},
    "zhytomyr": {"display_name": "Житомир", "oblast": "Житомирська область", "raion": "Житомирський район", "coverage_start": "2025-01-23", "basis": "official_test_rollout"},
    "dnipro": {"display_name": "Дніпро", "oblast": "Дніпропетровська область", "raion": "Дніпровський район", "coverage_start": "2025-05-01", "basis": "official_rollout"},
    "khmelnytskyi": {"display_name": "Хмельницький", "oblast": "Хмельницька область", "raion": "Хмельницький район", "coverage_start": "2025-07-07", "basis": "official_rollout"},
    "poltava": {"display_name": "Полтава", "oblast": "Полтавська область", "raion": "Полтавський район", "coverage_start": "2025-08-01", "basis": "official_rollout"},
    "rivne": {"display_name": "Рівне", "oblast": "Рівненська область", "raion": "Рівненський район", "coverage_start": "2025-08-01", "basis": "official_rollout"},
    "sumy": {"display_name": "Суми", "oblast": "Сумська область", "raion": "Сумський район", "coverage_start": "2025-08-06", "basis": "official_rollout"},
    "vinnytsia": {"display_name": "Вінниця", "oblast": "Вінницька область", "raion": "Вінницький район", "coverage_start": "2025-08-21", "basis": "official_rollout"},
    "kherson": {"display_name": "Херсон", "oblast": "Херсонська область", "raion": "Херсонський район", "coverage_start": "2025-08-30", "basis": "source_observed"},
    "kropyvnytskyi": {"display_name": "Кропивницький", "oblast": "Кіровоградська область", "raion": "Кропивницький район", "coverage_start": "2025-09-01", "basis": "official_permanent_rollout"},
    "lviv": {"display_name": "Львів", "oblast": "Львівська область", "raion": "Львівський район", "coverage_start": "2025-09-01", "basis": "official_rollout"},
    "chernihiv": {"display_name": "Чернігів", "oblast": "Чернігівська область", "raion": "Чернігівський район", "coverage_start": "2025-09-03", "basis": "official_permanent_rollout"},
    "odesa": {"display_name": "Одеса", "oblast": "Одеська область", "raion": "Одеський район", "coverage_start": "2025-11-04", "basis": "official_rollout"},
    "lutsk": {"display_name": "Луцьк", "oblast": "Волинська область", "raion": "Луцький район", "coverage_start": "2025-11-06", "basis": "source_observed"},
    "uzhhorod": {"display_name": "Ужгород", "oblast": "Закарпатська область", "raion": "Ужгородський район", "coverage_start": "2025-11-06", "basis": "source_observed"},
    "ivano_frankivsk": {"display_name": "Івано-Франківськ", "oblast": "Івано-Франківська область", "raion": "Івано-Франківський район", "coverage_start": "2025-11-06", "basis": "source_observed"},
    "chernivtsi": {"display_name": "Чернівці", "oblast": "Чернівецька область", "raion": "Чернівецький район", "coverage_start": "2025-11-06", "basis": "source_observed"},
}

SPECIAL_CASES = {
    "mykolaiv": "Official 2025 system distinguishes Mykolaiv city from the rest of the oblast; Mykolaiv raion is not a defensible city proxy.",
    "ternopil": "Regional alert logic frequently covers the whole oblast; Ternopil raion does not provide a meaningful narrower city proxy.",
    "donetsk": "National raion rollout logic is not directly applicable; requires separate methodology.",
    "luhansk": "National raion rollout logic is not directly applicable; requires separate methodology.",
}

OUT_DIR = Path("data")
OUT_CSV = OUT_DIR / "proxy_union_evaluation.csv"
OUT_JSON = OUT_DIR / "proxy_union_evaluation.json"


def parse_dt(value: str) -> datetime:
    x = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)


def start_utc(date_str: str) -> datetime:
    local_midnight = datetime.fromisoformat(date_str).replace(tzinfo=KYIV_TZ)
    return local_midnight.astimezone(timezone.utc)


def merge(intervals):
    xs = sorted(intervals)
    if not xs:
        return []
    out = [list(xs[0])]
    for a, b in xs[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def clip(intervals, start, end=None):
    if end is None:
        end = datetime.max.replace(tzinfo=timezone.utc)
    out = []
    for a, b in intervals:
        aa, bb = max(a, start), min(b, end)
        if aa < bb:
            out.append((aa, bb))
    return merge(out)


def intersect(a, b):
    a, b = merge(a), merge(b)
    out = []
    i = j = 0
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return merge(out)


def subtract(a, b):
    a, b = merge(a), merge(b)
    out = []
    for start, end in a:
        cur = start
        for bs, be in b:
            if be <= cur:
                continue
            if bs >= end:
                break
            if bs > cur:
                out.append((cur, min(bs, end)))
            cur = max(cur, be)
            if cur >= end:
                break
        if cur < end:
            out.append((cur, end))
    return merge(out)


def hours(intervals):
    return sum((b - a).total_seconds() for a, b in merge(intervals)) / 3600.0


def metrics(raion, oblast):
    raion = merge(raion)
    oblast = merge(oblast)
    combined = merge(raion + oblast)
    overlap = intersect(raion, oblast)
    oblast_only = subtract(oblast, raion)
    raion_only = subtract(raion, oblast)

    rh = hours(raion)
    oh = hours(oblast)
    ch = hours(combined)
    ovh = hours(overlap)
    obh = hours(oblast_only)
    rah = hours(raion_only)

    return {
        "raion_hours": round(rh, 3),
        "explicit_oblast_hours": round(oh, 3),
        "overlap_hours": round(ovh, 3),
        "oblast_only_hours_added": round(obh, 3),
        "raion_only_hours": round(rah, 3),
        "combined_proxy_hours": round(ch, 3),
        "combined_vs_raion_increase_pct": round((ch - rh) / rh * 100, 2) if rh else None,
        "oblast_only_share_of_combined_pct": round(obh / ch * 100, 2) if ch else None,
        "raion_interval_count": len(raion),
        "combined_interval_count": len(combined),
    }


def main():
    raw = requests.get(SOURCE_URL, timeout=120)
    raw.raise_for_status()
    reader = csv.DictReader(raw.text.splitlines())

    raion_intervals = defaultdict(list)
    oblast_intervals = defaultdict(list)
    latest_finished = None
    by_oblast = {cfg["oblast"]: key for key, cfg in PROXIES.items()}

    for row in reader:
        started = (row.get("started_at") or "").strip()
        finished = (row.get("finished_at") or "").strip()
        if not started or not finished:
            continue
        try:
            a, b = parse_dt(started), parse_dt(finished)
        except Exception:
            continue
        if b <= a:
            continue
        if latest_finished is None or b > latest_finished:
            latest_finished = b

        oblast_name = (row.get("oblast") or "").strip()
        key = by_oblast.get(oblast_name)
        if not key:
            continue
        cfg = PROXIES[key]
        level = (row.get("level") or "").strip()
        raion_name = (row.get("raion") or "").strip()
        if level == "raion" and raion_name == cfg["raion"]:
            raion_intervals[key].append((a, b))
        elif level == "oblast":
            oblast_intervals[key].append((a, b))

    results = []
    for key, cfg in PROXIES.items():
        rollout = start_utc(cfg["coverage_start"])
        end_all = latest_finished or END_2026

        rai_all = clip(raion_intervals[key], rollout, end_all)
        obl_all = clip(oblast_intervals[key], rollout, end_all)
        all_m = metrics(rai_all, obl_all)

        period_2026_start = max(rollout, START_2026)
        rai_26 = clip(raion_intervals[key], period_2026_start, min(END_2026, end_all))
        obl_26 = clip(oblast_intervals[key], period_2026_start, min(END_2026, end_all))
        m26 = metrics(rai_26, obl_26)

        row = {
            "city": key,
            "display_name": cfg["display_name"],
            "oblast": cfg["oblast"],
            "raion": cfg["raion"],
            "coverage_start": cfg["coverage_start"],
            "coverage_start_basis": cfg["basis"],
        }
        for prefix, vals in (("post_rollout", all_m), ("y2026", m26)):
            for name, value in vals.items():
                row[f"{prefix}_{name}"] = value
        results.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    meta = {
        "source": SOURCE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_finished_at": latest_finished.isoformat() if latest_finished else None,
        "definition": "city proxy after rollout = union(eponymous raion alert intervals, explicit oblast alert intervals)",
        "rollout_cutoff_rule": "Official rollout date interpreted as 00:00 Europe/Kyiv when exact clock time is unavailable.",
        "special_cases_excluded": SPECIAL_CASES,
    }
    OUT_JSON.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("city\tstart\tbasis\traion_h\toblast_added_h\tcombined_h\tincrease%\toblast_share%\t2026_raion_h\t2026_added_h\t2026_increase%")
    for r in results:
        print(
            f"{r['display_name']}\t{r['coverage_start']}\t{r['coverage_start_basis']}\t"
            f"{r['post_rollout_raion_hours']}\t{r['post_rollout_oblast_only_hours_added']}\t{r['post_rollout_combined_proxy_hours']}\t"
            f"{r['post_rollout_combined_vs_raion_increase_pct']}\t{r['post_rollout_oblast_only_share_of_combined_pct']}\t"
            f"{r['y2026_raion_hours']}\t{r['y2026_oblast_only_hours_added']}\t{r['y2026_combined_vs_raion_increase_pct']}"
        )


if __name__ == "__main__":
    main()
