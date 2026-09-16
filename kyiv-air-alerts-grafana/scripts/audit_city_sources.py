#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import requests

DATA_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/official_data_uk.csv"
)
TZ = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Event:
    start: datetime
    end: datetime


CITY_CONFIG = [
    {
        "key": "kyiv",
        "display_name": "Київ",
        "oblast": None,
        "raion": None,
        "hromada": None,
        "preferred_source_type": "exact_city",
        "preferred_source_name": "місто Київ",
        "known_coverage_start": None,
        "external_source": True,
        "notes": "Exact city series is maintained from Kyiv municipal open data in update_data.py.",
    },
    {
        "key": "vinnytsia",
        "display_name": "Вінниця",
        "oblast": "Вінницька область",
        "raion": "Вінницький район",
        "hromada": "м. Вінниця та Вінницька територіальна громада",
    },
    {
        "key": "lutsk",
        "display_name": "Луцьк",
        "oblast": "Волинська область",
        "raion": "Луцький район",
        "hromada": "м. Луцьк та Луцька територіальна громада",
    },
    {
        "key": "dnipro",
        "display_name": "Дніпро",
        "oblast": "Дніпропетровська область",
        "raion": "Дніпровський район",
        "hromada": "м. Дніпро та Дніпровська територіальна громада",
    },
    {
        "key": "donetsk",
        "display_name": "Донецьк",
        "oblast": "Донецька область",
        "raion": "Донецький район",
        "hromada": "м. Донецьк та Донецька територіальна громада",
        "preferred_source_type": "oblast",
        "preferred_source_name": "Донецька область",
        "notes": "National raion-level rollout did not apply to Donetsk oblast; oblast is the default fallback.",
    },
    {
        "key": "zhytomyr",
        "display_name": "Житомир",
        "oblast": "Житомирська область",
        "raion": "Житомирський район",
        "hromada": "м. Житомир та Житомирська територіальна громада",
    },
    {
        "key": "uzhhorod",
        "display_name": "Ужгород",
        "oblast": "Закарпатська область",
        "raion": "Ужгородський район",
        "hromada": "м. Ужгород та Ужгородська територіальна громада",
    },
    {
        "key": "zaporizhzhia",
        "display_name": "Запоріжжя",
        "oblast": "Запорізька область",
        "raion": "Запорізький район",
        "hromada": "м. Запоріжжя та Запорізька територіальна громада",
        "preferred_source_type": "exact_city",
        "preferred_source_name": "м. Запоріжжя та Запорізька територіальна громада",
        "known_coverage_start": "2025-03-19",
        "notes": "Validated exact-city stream already used by the dashboard.",
    },
    {
        "key": "ivano_frankivsk",
        "display_name": "Івано-Франківськ",
        "oblast": "Івано-Франківська область",
        "raion": "Івано-Франківський район",
        "hromada": "м. Івано-Франківськ та Івано-Франківська територіальна громада",
    },
    {
        "key": "kropyvnytskyi",
        "display_name": "Кропивницький",
        "oblast": "Кіровоградська область",
        "raion": "Кропивницький район",
        "hromada": "м. Кропивницький та Кропивницька територіальна громада",
    },
    {
        "key": "luhansk",
        "display_name": "Луганськ",
        "oblast": "Луганська область",
        "raion": "Луганський район",
        "hromada": "м. Луганськ та Луганська територіальна громада",
        "preferred_source_type": "oblast",
        "preferred_source_name": "Луганська область",
        "notes": "National raion-level rollout did not apply to Luhansk oblast; oblast is the default fallback.",
    },
    {
        "key": "lviv",
        "display_name": "Львів",
        "oblast": "Львівська область",
        "raion": "Львівський район",
        "hromada": "м. Львів та Львівська територіальна громада",
    },
    {
        "key": "mykolaiv",
        "display_name": "Миколаїв",
        "oblast": "Миколаївська область",
        "raion": "Миколаївський район",
        "hromada": "м. Миколаїв та Миколаївська територіальна громада",
    },
    {
        "key": "odesa",
        "display_name": "Одеса",
        "oblast": "Одеська область",
        "raion": "Одеський район",
        "hromada": "м. Одеса та Одеська територіальна громада",
        "known_coverage_start": "2025-11-04",
        "notes": "Official city-channel evidence confirms separate Odesa-raion alerts from 2025-11-04.",
    },
    {
        "key": "poltava",
        "display_name": "Полтава",
        "oblast": "Полтавська область",
        "raion": "Полтавський район",
        "hromada": "м. Полтава та Полтавська територіальна громада",
    },
    {
        "key": "rivne",
        "display_name": "Рівне",
        "oblast": "Рівненська область",
        "raion": "Рівненський район",
        "hromada": "м. Рівне та Рівненська територіальна громада",
        "known_coverage_start": "2025-08-01",
        "notes": "Rivne OVA officially switched to separate raion alerts on 2025-08-01.",
    },
    {
        "key": "sumy",
        "display_name": "Суми",
        "oblast": "Сумська область",
        "raion": "Сумський район",
        "hromada": "м. Суми та Сумська територіальна громада",
    },
    {
        "key": "ternopil",
        "display_name": "Тернопіль",
        "oblast": "Тернопільська область",
        "raion": "Тернопільський район",
        "hromada": "м. Тернопіль та Тернопільська територіальна громада",
    },
    {
        "key": "kharkiv",
        "display_name": "Харків",
        "oblast": "Харківська область",
        "raion": "Харківський район",
        "hromada": "м. Харків та Харківська територіальна громада",
        "preferred_source_type": "exact_city",
        "preferred_source_name": "м. Харків та Харківська територіальна громада",
        "known_coverage_start": "2025-02-17",
        "notes": "Validated exact-city stream already used by the dashboard.",
    },
    {
        "key": "kherson",
        "display_name": "Херсон",
        "oblast": "Херсонська область",
        "raion": "Херсонський район",
        "hromada": "м. Херсон та Херсонська територіальна громада",
    },
    {
        "key": "khmelnytskyi",
        "display_name": "Хмельницький",
        "oblast": "Хмельницька область",
        "raion": "Хмельницький район",
        "hromada": "м. Хмельницький та Хмельницька територіальна громада",
    },
    {
        "key": "cherkasy",
        "display_name": "Черкаси",
        "oblast": "Черкаська область",
        "raion": "Черкаський район",
        "hromada": "м. Черкаси та Черкаська територіальна громада",
    },
    {
        "key": "chernivtsi",
        "display_name": "Чернівці",
        "oblast": "Чернівецька область",
        "raion": "Чернівецький район",
        "hromada": "м. Чернівці та Чернівецька територіальна громада",
    },
    {
        "key": "chernihiv",
        "display_name": "Чернігів",
        "oblast": "Чернігівська область",
        "raion": "Чернігівський район",
        "hromada": "м. Чернігів та Чернігівська територіальна громада",
    },
]


def parse_dt(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def merge_intervals(events: Iterable[Event]) -> list[tuple[datetime, datetime]]:
    raw = sorted(((e.start, e.end) for e in events if e.end > e.start), key=lambda x: x[0])
    merged: list[list[datetime]] = []
    for start, end in raw:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(s, e) for s, e in merged]


def clip_intervals(
    intervals: Iterable[tuple[datetime, datetime]], start: datetime | None
) -> list[tuple[datetime, datetime]]:
    if start is None:
        return list(intervals)
    out = []
    for a, b in intervals:
        if b <= start:
            continue
        out.append((max(a, start), b))
    return out


def interval_seconds(intervals: Iterable[tuple[datetime, datetime]]) -> float:
    return sum((b - a).total_seconds() for a, b in intervals)


def overlap_seconds(
    a: list[tuple[datetime, datetime]], b: list[tuple[datetime, datetime]]
) -> float:
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            total += (end - start).total_seconds()
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return total


def event_has_overlap(event: Event, intervals: list[tuple[datetime, datetime]]) -> bool:
    for start, end in intervals:
        if end <= event.start:
            continue
        if start >= event.end:
            return False
        if min(event.end, end) > max(event.start, start):
            return True
    return False


def first_event(events: list[Event]) -> datetime | None:
    return min((e.start for e in events), default=None)


def last_event(events: list[Event]) -> datetime | None:
    return max((e.start for e in events), default=None)


def max_start_gap_days(events: list[Event]) -> float | None:
    starts = sorted({e.start for e in events})
    if len(starts) < 2:
        return None
    return max((b - a).total_seconds() / 86400.0 for a, b in zip(starts, starts[1:]))


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def local_date(dt: datetime | None) -> str | None:
    return dt.astimezone(TZ).date().isoformat() if dt else None


def source_defaults(cfg: dict) -> tuple[str, str]:
    if cfg.get("preferred_source_type"):
        return cfg["preferred_source_type"], cfg["preferred_source_name"]
    if cfg.get("raion"):
        return "raion_proxy", cfg["raion"]
    if cfg.get("oblast"):
        return "oblast", cfg["oblast"]
    return "unavailable", ""


def source_events(cfg: dict, grouped: dict) -> tuple[list[Event], str, str]:
    source_type, source_name = source_defaults(cfg)
    oblast = cfg.get("oblast")
    if source_type == "exact_city":
        events = grouped["hromada"].get((oblast, cfg.get("hromada")), [])
    elif source_type == "raion_proxy":
        events = grouped["raion"].get((oblast, cfg.get("raion")), [])
    elif source_type == "oblast":
        events = grouped["oblast"].get(oblast, [])
    else:
        events = []
    return events, source_type, source_name


def read_rows(input_path: Path | None) -> Iterable[dict[str, str]]:
    if input_path:
        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)
        return

    response = requests.get(
        DATA_URL,
        timeout=180,
        headers={"User-Agent": "kyiv-air-alerts-grafana city-source audit"},
    )
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")
    yield from csv.DictReader(io.StringIO(text))


def collect(input_path: Path | None) -> dict:
    wanted_oblasts = {c["oblast"] for c in CITY_CONFIG if c.get("oblast")}
    wanted_raions = {(c["oblast"], c["raion"]) for c in CITY_CONFIG if c.get("raion")}
    wanted_hromadas = {(c["oblast"], c["hromada"]) for c in CITY_CONFIG if c.get("hromada")}

    grouped = {
        "oblast": defaultdict(list),
        "raion": defaultdict(list),
        "hromada": defaultdict(list),
    }
    seen = {"oblast": set(), "raion": set(), "hromada": set()}

    for row in read_rows(input_path):
        level = (row.get("level") or "").strip()
        oblast = (row.get("oblast") or "").strip()
        raion = (row.get("raion") or "").strip()
        hromada = (row.get("hromada") or "").strip()
        if oblast not in wanted_oblasts:
            continue
        start = parse_dt(row.get("started_at") or "")
        end = parse_dt(row.get("finished_at") or "")
        if not start or not end or end <= start:
            continue
        event = Event(start, end)
        sig = (start, end)

        if level == "oblast" and oblast in wanted_oblasts and (oblast, sig) not in seen["oblast"]:
            grouped["oblast"][oblast].append(event)
            seen["oblast"].add((oblast, sig))
        elif level == "raion" and (oblast, raion) in wanted_raions:
            key = (oblast, raion)
            if (key, sig) not in seen["raion"]:
                grouped["raion"][key].append(event)
                seen["raion"].add((key, sig))
        elif level == "hromada" and (oblast, hromada) in wanted_hromadas:
            key = (oblast, hromada)
            if (key, sig) not in seen["hromada"]:
                grouped["hromada"][key].append(event)
                seen["hromada"].add((key, sig))

    for level in grouped:
        for events in grouped[level].values():
            events.sort(key=lambda e: e.start)
    return grouped


def audit_city(cfg: dict, grouped: dict) -> dict:
    if cfg.get("external_source"):
        return {
            "city": cfg["key"],
            "display_name": cfg["display_name"],
            "oblast": None,
            "preferred_source_type": cfg["preferred_source_type"],
            "preferred_source_name": cfg["preferred_source_name"],
            "known_coverage_start": cfg.get("known_coverage_start"),
            "coverage_start_candidate": None,
            "candidate_requires_external_validation": False,
            "notes": cfg.get("notes", ""),
        }

    oblast = cfg["oblast"]
    raion_key = (oblast, cfg.get("raion"))
    hromada_key = (oblast, cfg.get("hromada"))
    oblast_events = grouped["oblast"].get(oblast, [])
    raion_events = grouped["raion"].get(raion_key, [])
    hromada_events = grouped["hromada"].get(hromada_key, [])
    preferred_events, source_type, source_name = source_events(cfg, grouped)

    observed_first = first_event(preferred_events)
    known_start = cfg.get("known_coverage_start")
    coverage_candidate = known_start or local_date(observed_first)
    compare_start = observed_first
    if known_start:
        compare_start = datetime.combine(date.fromisoformat(known_start), datetime.min.time(), tzinfo=TZ).astimezone(UTC)

    src_intervals = clip_intervals(merge_intervals(preferred_events), compare_start)
    oblast_intervals = clip_intervals(merge_intervals(oblast_events), compare_start)
    overlap = overlap_seconds(src_intervals, oblast_intervals)
    src_sec = interval_seconds(src_intervals)
    oblast_sec = interval_seconds(oblast_intervals)

    source_events_after = [e for e in preferred_events if compare_start is None or e.end > compare_start]
    oblast_events_after = [e for e in oblast_events if compare_start is None or e.end > compare_start]
    source_without_oblast = sum(1 for e in source_events_after if not event_has_overlap(e, oblast_intervals))
    oblast_without_source = sum(1 for e in oblast_events_after if not event_has_overlap(e, src_intervals))

    return {
        "city": cfg["key"],
        "display_name": cfg["display_name"],
        "oblast": oblast,
        "preferred_source_type": source_type,
        "preferred_source_name": source_name,
        "known_coverage_start": known_start,
        "coverage_start_candidate": coverage_candidate,
        "candidate_requires_external_validation": known_start is None,
        "preferred_event_count": len(preferred_events),
        "preferred_first_event_utc": iso(observed_first),
        "preferred_first_event_local_date": local_date(observed_first),
        "preferred_last_event_utc": iso(last_event(preferred_events)),
        "preferred_max_inter_event_gap_days": round(max_start_gap_days(preferred_events), 2)
        if max_start_gap_days(preferred_events) is not None
        else None,
        "raion_name": cfg.get("raion"),
        "raion_event_count": len(raion_events),
        "raion_first_event_utc": iso(first_event(raion_events)),
        "raion_first_event_local_date": local_date(first_event(raion_events)),
        "hromada_name": cfg.get("hromada"),
        "hromada_event_count": len(hromada_events),
        "hromada_first_event_utc": iso(first_event(hromada_events)),
        "hromada_first_event_local_date": local_date(first_event(hromada_events)),
        "oblast_event_count": len(oblast_events),
        "oblast_first_event_utc": iso(first_event(oblast_events)),
        "comparison_start_utc": iso(compare_start),
        "preferred_alert_hours_since_comparison_start": round(src_sec / 3600.0, 3),
        "oblast_alert_hours_since_comparison_start": round(oblast_sec / 3600.0, 3),
        "overlap_hours": round(overlap / 3600.0, 3),
        "preferred_only_hours": round(max(0.0, src_sec - overlap) / 3600.0, 3),
        "oblast_only_hours": round(max(0.0, oblast_sec - overlap) / 3600.0, 3),
        "preferred_events_without_oblast_overlap": source_without_oblast,
        "oblast_events_without_preferred_overlap": oblast_without_source,
        "notes": cfg.get("notes", ""),
    }


def write_outputs(rows: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "city_source_audit.json"
    csv_path = output_dir / "city_source_audit.csv"
    payload = {
        "meta": {
            "source_url": DATA_URL,
            "generated_at": datetime.now(UTC).isoformat(),
            "methodology": (
                "Preferred source is exact city where already validated; otherwise eponymous raion proxy; "
                "Donetsk/Luhansk default to oblast because the nationwide raion-level rollout excluded them. "
                "For unvalidated cities coverage_start_candidate is the first observed preferred-source event, "
                "which is a lower-bound observation and requires external validation before dashboard use."
            ),
        },
        "cities": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit city/raion/oblast alert-source coverage.")
    parser.add_argument("--input", type=Path, help="Optional local official_data_uk.csv path")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    grouped = collect(args.input)
    rows = [audit_city(cfg, grouped) for cfg in CITY_CONFIG]
    json_path, csv_path = write_outputs(rows, args.output_dir)

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print("city\tsource\tcoverage_candidate\tfirst_event\tevents\toblast_only_h")
    for row in rows:
        print(
            f"{row['display_name']}\t{row['preferred_source_type']}\t"
            f"{row.get('coverage_start_candidate') or '-'}\t"
            f"{row.get('preferred_first_event_local_date') or '-'}\t"
            f"{row.get('preferred_event_count', '-')}\t"
            f"{row.get('oblast_only_hours', '-')}"
        )


if __name__ == "__main__":
    main()
