from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SOURCE_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_uk.csv"
OUT_DIR = Path("data")
OUT_CSV = OUT_DIR / "raion_stable_start_candidates.csv"
OUT_JSON = OUT_DIR / "raion_stable_start_candidates.json"

CITIES = {
    "vinnytsia": ("Вінниця", "Вінницька область", "Вінницький район"),
    "lutsk": ("Луцьк", "Волинська область", "Луцький район"),
    "dnipro": ("Дніпро", "Дніпропетровська область", "Дніпровський район"),
    "zhytomyr": ("Житомир", "Житомирська область", "Житомирський район"),
    "uzhhorod": ("Ужгород", "Закарпатська область", "Ужгородський район"),
    "ivano_frankivsk": ("Івано-Франківськ", "Івано-Франківська область", "Івано-Франківський район"),
    "kropyvnytskyi": ("Кропивницький", "Кіровоградська область", "Кропивницький район"),
    "lviv": ("Львів", "Львівська область", "Львівський район"),
    "mykolaiv": ("Миколаїв", "Миколаївська область", "Миколаївський район"),
    "odesa": ("Одеса", "Одеська область", "Одеський район"),
    "poltava": ("Полтава", "Полтавська область", "Полтавський район"),
    "rivne": ("Рівне", "Рівненська область", "Рівненський район"),
    "sumy": ("Суми", "Сумська область", "Сумський район"),
    "ternopil": ("Тернопіль", "Тернопільська область", "Тернопільський район"),
    "kherson": ("Херсон", "Херсонська область", "Херсонський район"),
    "khmelnytskyi": ("Хмельницький", "Хмельницька область", "Хмельницький район"),
    "cherkasy": ("Черкаси", "Черкаська область", "Черкаський район"),
    "chernivtsi": ("Чернівці", "Чернівецька область", "Чернівецький район"),
    "chernihiv": ("Чернігів", "Чернігівська область", "Чернігівський район"),
}

KNOWN = {
    "odesa": "2025-11-04",
    "rivne": "2025-08-01",
}


def parse_dt(v: str) -> datetime:
    x = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)


def infer(starts, latest):
    starts = sorted(set(starts))
    if not starts:
        return None
    # Candidate is the event immediately after the last >=90-day hiatus,
    # provided the following segment is substantial and reaches near the dataset end.
    viable = []
    for i in range(1, len(starts)):
        gap_days = (starts[i] - starts[i - 1]).total_seconds() / 86400
        if gap_days < 90:
            continue
        tail = starts[i:]
        if len(tail) < 20:
            continue
        if (latest - tail[-1]).total_seconds() / 86400 > 45:
            continue
        viable.append((i, gap_days))
    if viable:
        i, preceding_gap = viable[-1]
    else:
        i, preceding_gap = 0, None
    tail = starts[i:]
    gaps = [
        (tail[j] - tail[j - 1]).total_seconds() / 86400
        for j in range(1, len(tail))
    ]
    return {
        "candidate": tail[0],
        "preceding_gap_days": round(preceding_gap, 2) if preceding_gap is not None else None,
        "post_candidate_events": len(tail),
        "post_candidate_max_gap_days": round(max(gaps), 2) if gaps else None,
        "first_observed": starts[0],
        "last_observed": starts[-1],
    }


def main():
    resp = requests.get(SOURCE_URL, timeout=120)
    resp.raise_for_status()
    rows = csv.DictReader(resp.text.splitlines())
    starts = defaultdict(list)
    latest = None
    lookup = {(oblast, raion): key for key, (_, oblast, raion) in CITIES.items()}
    for row in rows:
        if (row.get("level") or "").strip() != "raion":
            continue
        oblast = (row.get("oblast") or "").strip()
        raion = (row.get("raion") or "").strip()
        key = lookup.get((oblast, raion))
        if not key:
            continue
        s = (row.get("started_at") or "").strip()
        f = (row.get("finished_at") or "").strip()
        if not s:
            continue
        try:
            sd = parse_dt(s)
            fd = parse_dt(f) if f else sd
        except Exception:
            continue
        starts[key].append(sd)
        latest = fd if latest is None or fd > latest else latest

    results = []
    for key, (city, oblast, raion) in CITIES.items():
        inf = infer(starts[key], latest) if latest else None
        results.append({
            "city": key,
            "display_name": city,
            "oblast": oblast,
            "raion": raion,
            "first_observed_event": inf["first_observed"].date().isoformat() if inf else None,
            "stable_start_candidate": inf["candidate"].date().isoformat() if inf else None,
            "preceding_gap_days": inf["preceding_gap_days"] if inf else None,
            "post_candidate_events": inf["post_candidate_events"] if inf else 0,
            "post_candidate_max_gap_days": inf["post_candidate_max_gap_days"] if inf else None,
            "last_observed_event": inf["last_observed"].date().isoformat() if inf else None,
            "known_validated_start": KNOWN.get(key),
            "candidate_matches_known": (inf["candidate"].date().isoformat() == KNOWN[key]) if inf and key in KNOWN else None,
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "meta": {
            "source": SOURCE_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "latest_event_end": latest.isoformat() if latest else None,
            "method": "event after last >=90-day hiatus, if post-hiatus segment has >=20 events and reaches within 45 days of dataset end; otherwise first observed event",
            "warning": "diagnostic candidate only; low-alert regions may have genuine long quiet periods, so external validation remains required",
        },
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print("city\tfirst\tcandidate\tpre_gap\tpost_n\tpost_max_gap\tknown\tmatch")
    for r in results:
        print(f"{r['display_name']}\t{r['first_observed_event']}\t{r['stable_start_candidate']}\t{r['preceding_gap_days']}\t{r['post_candidate_events']}\t{r['post_candidate_max_gap_days']}\t{r['known_validated_start']}\t{r['candidate_matches_known']}")


if __name__ == "__main__":
    main()
