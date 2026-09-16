from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

CSV_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_uk.csv"
STATES_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/processors/states.json"

START_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
START_2026 = datetime(2026, 1, 1, tzinfo=timezone.utc)
END_2026 = datetime(2027, 1, 1, tzinfo=timezone.utc)

CITIES = {
    "vinnytsia": ("Вінниця", "Вінницька область", "Вінницький район"),
    "lutsk": ("Луцьк", "Волинська область", "Луцький район"),
    "dnipro": ("Дніпро", "Дніпропетровська область", "Дніпровський район"),
    "donetsk": ("Донецьк", "Донецька область", "Донецький район"),
    "zhytomyr": ("Житомир", "Житомирська область", "Житомирський район"),
    "uzhhorod": ("Ужгород", "Закарпатська область", "Ужгородський район"),
    "zaporizhzhia": ("Запоріжжя", "Запорізька область", "Запорізький район"),
    "ivano_frankivsk": ("Івано-Франківськ", "Івано-Франківська область", "Івано-Франківський район"),
    "kropyvnytskyi": ("Кропивницький", "Кіровоградська область", "Кропивницький район"),
    "luhansk": ("Луганськ", "Луганська область", "Луганський район"),
    "lviv": ("Львів", "Львівська область", "Львівський район"),
    "mykolaiv": ("Миколаїв", "Миколаївська область", "Миколаївський район"),
    "odesa": ("Одеса", "Одеська область", "Одеський район"),
    "poltava": ("Полтава", "Полтавська область", "Полтавський район"),
    "rivne": ("Рівне", "Рівненська область", "Рівненський район"),
    "sumy": ("Суми", "Сумська область", "Сумський район"),
    "ternopil": ("Тернопіль", "Тернопільська область", "Тернопільський район"),
    "kharkiv": ("Харків", "Харківська область", "Харківський район"),
    "kherson": ("Херсон", "Херсонська область", "Херсонський район"),
    "khmelnytskyi": ("Хмельницький", "Хмельницька область", "Хмельницький район"),
    "cherkasy": ("Черкаси", "Черкаська область", "Черкаський район"),
    "chernivtsi": ("Чернівці", "Чернівецька область", "Чернівецький район"),
    "chernihiv": ("Чернігів", "Чернігівська область", "Чернігівський район"),
}

OUT_DIR = Path("data")
OUT_CSV = OUT_DIR / "exact_city_hromada_audit.csv"
OUT_JSON = OUT_DIR / "exact_city_hromada_audit.json"


def dt(v: str) -> datetime:
    x = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)


def merge(xs):
    xs = sorted(xs)
    if not xs:
        return []
    out = [list(xs[0])]
    for a, b in xs[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def clipped(xs, start, end):
    out = []
    for a, b in xs:
        a2, b2 = max(a, start), min(b, end)
        if a2 < b2:
            out.append((a2, b2))
    return merge(out)


def hours(xs):
    return sum((b - a).total_seconds() for a, b in merge(xs)) / 3600


def intersect(a, b):
    a, b = merge(a), merge(b)
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return merge(out)


def union(a, b):
    return merge(list(a) + list(b))


def pct(n, d):
    return round(100 * n / d, 2) if d else None


def find_city_community(states, city, oblast):
    candidates = []
    for st in states.get("states", []):
        if st.get("stateName") != oblast:
            continue
        for district in st.get("districts", []):
            for community in district.get("communities", []):
                name = community.get("communityName", "")
                score = 0
                if name.startswith(f"м. {city} ") or name == f"м. {city}":
                    score = 100
                elif city.lower() in name.lower():
                    score = 50
                if score:
                    candidates.append((score, name, district.get("districtName"), community.get("communityId")))
    candidates.sort(reverse=True)
    return candidates[0] if candidates else (None, None, None, None)


def main():
    states = requests.get(STATES_URL, timeout=60).json()
    community_lookup = {}
    for key, (city, oblast, expected_raion) in CITIES.items():
        score, name, district, cid = find_city_community(states, city, oblast)
        community_lookup[key] = {
            "community": name,
            "community_id": cid,
            "states_raion": district,
            "match_score": score,
            "expected_raion": expected_raion,
        }

    resp = requests.get(CSV_URL, timeout=120)
    resp.raise_for_status()
    reader = csv.DictReader(resp.text.splitlines())

    city_intervals = defaultdict(list)
    raion_intervals = defaultdict(list)
    city_events = defaultdict(list)
    raion_events = defaultdict(list)
    latest_finished = None

    by_oblast = {v[1]: k for k, v in CITIES.items()}
    for row in reader:
        started_s = (row.get("started_at") or "").strip()
        finished_s = (row.get("finished_at") or "").strip()
        if not started_s or not finished_s:
            continue
        try:
            a, b = dt(started_s), dt(finished_s)
        except Exception:
            continue
        if b <= a:
            continue
        latest_finished = b if latest_finished is None or b > latest_finished else latest_finished
        oblast = (row.get("oblast") or "").strip()
        key = by_oblast.get(oblast)
        if not key:
            continue
        level = (row.get("level") or "").strip()
        hromada = (row.get("hromada") or "").strip()
        raion = (row.get("raion") or "").strip()
        cfg = community_lookup[key]
        if level == "hromada" and cfg["community"] and hromada == cfg["community"]:
            city_intervals[key].append((a, b))
            city_events[key].append(a)
        if level == "raion" and raion == CITIES[key][2]:
            raion_intervals[key].append((a, b))
            raion_events[key].append(a)

    cutoff_90 = (latest_finished - timedelta(days=90)) if latest_finished else START_2026
    results = []
    for key, (city, oblast, raion_name) in CITIES.items():
        cfg = community_lookup[key]
        civ_all = merge(city_intervals[key])
        rai_all = merge(raion_intervals[key])
        civ25 = clipped(civ_all, START_2025, END_2026)
        civ26 = clipped(civ_all, START_2026, END_2026)
        rai26 = clipped(rai_all, START_2026, END_2026)
        ov26 = intersect(civ26, rai26)
        un26 = union(civ26, rai26)
        city_h, raion_h, overlap_h, union_h = hours(civ26), hours(rai26), hours(ov26), hours(un26)

        ce25 = [x for x in city_events[key] if START_2025 <= x < START_2026]
        ce26 = [x for x in city_events[key] if START_2026 <= x < END_2026]
        re26 = [x for x in raion_events[key] if START_2026 <= x < END_2026]
        recent_city = [x for x in city_events[key] if x >= cutoff_90]
        recent_raion = [x for x in raion_events[key] if x >= cutoff_90]

        if not cfg["community"]:
            status = "no_states_match"
        elif len(ce26) >= 10 and len(recent_city) >= 2:
            status = "current_exact_city_candidate"
        elif len(ce26) > 0:
            status = "sparse_or_intermittent_2026"
        elif len(ce25) > 0:
            status = "historical_2025_only"
        else:
            status = "no_2025_2026_exact_city_events"

        results.append({
            "city": key,
            "display_name": city,
            "oblast": oblast,
            "states_city_hromada": cfg["community"],
            "states_city_hromada_id": cfg["community_id"],
            "states_raion": cfg["states_raion"],
            "expected_raion": raion_name,
            "states_match_score": cfg["match_score"],
            "status": status,
            "city_events_2025": len(ce25),
            "city_events_2026": len(ce26),
            "city_events_last_90d": len(recent_city),
            "raion_events_2026": len(re26),
            "raion_events_last_90d": len(recent_raion),
            "city_first_event_2025_2026": min(ce25 + ce26).isoformat() if ce25 or ce26 else None,
            "city_last_event": max(city_events[key]).isoformat() if city_events[key] else None,
            "city_alert_hours_2026": round(city_h, 3),
            "raion_alert_hours_2026": round(raion_h, 3),
            "overlap_hours_2026": round(overlap_h, 3),
            "city_covered_by_raion_pct_2026": pct(overlap_h, city_h),
            "raion_matching_city_pct_2026": pct(overlap_h, raion_h),
            "jaccard_pct_2026": pct(overlap_h, union_h),
            "raion_duration_bias_vs_city_pct_2026": round((raion_h - city_h) / city_h * 100, 2) if city_h else None,
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "meta": {
            "csv_source": CSV_URL,
            "states_source": STATES_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "latest_finished_at": latest_finished.isoformat() if latest_finished else None,
            "note": "Status is diagnostic only. Exact-city series must still be validated against official local alert publication before production use.",
        },
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    print("city\tstatus\thromada\t2025\t2026\tlast90\tcity_h26\traion_h26\tcoverage\tprecision\tbias")
    for r in results:
        print(f"{r['display_name']}\t{r['status']}\t{r['states_city_hromada']}\t{r['city_events_2025']}\t{r['city_events_2026']}\t{r['city_events_last_90d']}\t{r['city_alert_hours_2026']}\t{r['raion_alert_hours_2026']}\t{r['city_covered_by_raion_pct_2026']}\t{r['raion_matching_city_pct_2026']}\t{r['raion_duration_bias_vs_city_pct_2026']}")


if __name__ == "__main__":
    main()
