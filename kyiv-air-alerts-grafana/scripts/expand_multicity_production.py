#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from statistics import mean

from update_data import Alert, TZ, build_outputs, daterange, http_session, round3, union_daily_seconds

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"
CITY_SOURCE_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/official_data_uk.csv"
)

# Production set: only exact-city series or externally validated raion rollouts.
# Cities whose rollout date/source logic is still only source-observed are intentionally deferred.
PROXY_CONFIG = {
    "cherkasy": {"label": "Черкаси", "oblast": "Черкаська область", "raion": "Черкаський район", "coverage_start": "2025-01-10", "coverage_basis": "official_rollout"},
    "zhytomyr": {"label": "Житомир", "oblast": "Житомирська область", "raion": "Житомирський район", "coverage_start": "2025-01-23", "coverage_basis": "official_test_rollout"},
    "dnipro": {"label": "Дніпро", "oblast": "Дніпропетровська область", "raion": "Дніпровський район", "coverage_start": "2025-05-01", "coverage_basis": "official_rollout"},
    "khmelnytskyi": {"label": "Хмельницький", "oblast": "Хмельницька область", "raion": "Хмельницький район", "coverage_start": "2025-07-07", "coverage_basis": "official_rollout"},
    "poltava": {"label": "Полтава", "oblast": "Полтавська область", "raion": "Полтавський район", "coverage_start": "2025-08-01", "coverage_basis": "official_rollout"},
    "rivne": {"label": "Рівне", "oblast": "Рівненська область", "raion": "Рівненський район", "coverage_start": "2025-08-01", "coverage_basis": "official_rollout"},
    "sumy": {"label": "Суми", "oblast": "Сумська область", "raion": "Сумський район", "coverage_start": "2025-08-06", "coverage_basis": "official_rollout"},
    "vinnytsia": {"label": "Вінниця", "oblast": "Вінницька область", "raion": "Вінницький район", "coverage_start": "2025-08-21", "coverage_basis": "official_rollout"},
    "kropyvnytskyi": {"label": "Кропивницький", "oblast": "Кіровоградська область", "raion": "Кропивницький район", "coverage_start": "2025-09-01", "coverage_basis": "official_permanent_rollout"},
    "lviv": {"label": "Львів", "oblast": "Львівська область", "raion": "Львівський район", "coverage_start": "2025-09-01", "coverage_basis": "official_rollout"},
    "chernihiv": {"label": "Чернігів", "oblast": "Чернігівська область", "raion": "Чернігівський район", "coverage_start": "2025-09-03", "coverage_basis": "official_permanent_rollout"},
    "odesa": {"label": "Одеса", "oblast": "Одеська область", "raion": "Одеський район", "coverage_start": "2025-11-04", "coverage_basis": "official_rollout"},
}

DEFERRED = {
    "kherson": "raion stream is stable, but rollout date is not externally validated",
    "lutsk": "raion stream is stable, but rollout date is not externally validated",
    "uzhhorod": "raion stream is stable, but rollout date is not externally validated",
    "ivano_frankivsk": "raion stream is stable, but rollout date is not externally validated",
    "chernivtsi": "raion stream is stable, but rollout date is not externally validated",
    "mykolaiv": "official system distinguishes Mykolaiv city from the rest of the oblast; raion is not a defensible city proxy",
    "ternopil": "regional alert logic does not provide a meaningfully narrower city proxy",
    "donetsk": "requires separate methodology",
    "luhansk": "requires separate methodology",
}

EXACT_KEYS = ["kyiv", "kharkiv", "zaporizhzhia"]
PROXY_KEYS = list(PROXY_CONFIG)
CITY_KEYS = EXACT_KEYS + PROXY_KEYS
CITY_LABELS = {
    "kyiv": "Київ",
    "kharkiv": "Харків",
    "zaporizhzhia": "Запоріжжя",
    **{key: cfg["label"] for key, cfg in PROXY_CONFIG.items()},
}

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


def parse_source_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        raise ValueError(f"Expected timezone-aware timestamp, got {value!r}")
    return dt.astimezone(TZ)


def coverage_start_dt(date_str: str) -> datetime:
    return datetime.combine(date.fromisoformat(date_str), time.min, tzinfo=TZ)


def union_alerts(intervals: list[tuple[datetime, datetime]]) -> list[Alert]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged: list[list[datetime]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [Alert(start=start, end=end, source="vadimkin_raion_or_oblast_union") for start, end in merged]


def fetch_proxy_alerts() -> dict[str, list[Alert]]:
    session = http_session()
    response = session.get(CITY_SOURCE_URL, timeout=120)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")

    by_oblast = {cfg["oblast"]: key for key, cfg in PROXY_CONFIG.items()}
    intervals: dict[str, list[tuple[datetime, datetime]]] = {key: [] for key in PROXY_KEYS}
    seen: dict[str, set[tuple[str, str, str]]] = {key: set() for key in PROXY_KEYS}

    for row in csv.DictReader(io.StringIO(text)):
        oblast = (row.get("oblast") or "").strip()
        key = by_oblast.get(oblast)
        if not key:
            continue
        cfg = PROXY_CONFIG[key]
        level = (row.get("level") or "").strip()
        raion = (row.get("raion") or "").strip()
        if level != "oblast" and not (level == "raion" and raion == cfg["raion"]):
            continue

        s = (row.get("started_at") or "").strip()
        e = (row.get("finished_at") or "").strip()
        if not s or not e:
            continue
        marker = (level, s, e)
        if marker in seen[key]:
            continue
        try:
            start = parse_source_dt(s)
            end = parse_source_dt(e)
        except ValueError:
            continue
        if end <= start:
            continue

        cutoff = coverage_start_dt(cfg["coverage_start"])
        if end <= cutoff:
            continue
        start = max(start, cutoff)
        seen[key].add(marker)
        intervals[key].append((start, end))

    result = {key: union_alerts(intervals[key]) for key in PROXY_KEYS}
    for key, alerts in result.items():
        if not alerts:
            raise RuntimeError(f"No proxy alerts found for {CITY_LABELS[key]}")
    return result


def enrich_weekly(output: dict, alerts: list[Alert]) -> None:
    for row in output.get("weekly", []):
        ws = date.fromisoformat(row["week_start"])
        we = date.fromisoformat(row["week_end"])
        daily_seconds = union_daily_seconds(alerts, ws, we)
        row["avg_daily_alert_hours"] = round3(sum(daily_seconds.get(d, 0.0) for d in daterange(ws, we)) / 7.0 / 3600.0)
        event_durations = [
            alert.duration_seconds / 60.0
            for alert in alerts
            if ws <= alert.start.astimezone(TZ).date() <= we
        ]
        row["avg_alert_duration_min"] = round3(mean(event_durations) if event_durations else None)


def trim_to_complete_coverage(output: dict, coverage_day: date) -> None:
    month_floor = coverage_day.replace(day=1)
    if coverage_day == month_floor:
        first_complete_month = month_floor
    elif month_floor.month == 12:
        first_complete_month = date(month_floor.year + 1, 1, 1)
    else:
        first_complete_month = date(month_floor.year, month_floor.month + 1, 1)

    first_complete_week = coverage_day
    if first_complete_week.weekday() != 0:
        first_complete_week += timedelta(days=7 - first_complete_week.weekday())

    output["monthly"] = [row for row in output.get("monthly", []) if date.fromisoformat(row["month"] + "-01") >= first_complete_month]
    output["weekly"] = [row for row in output.get("weekly", []) if date.fromisoformat(row["week_start"]) >= first_complete_week]
    meta = output.setdefault("meta", {})
    meta["first_city_level_date"] = coverage_day.isoformat()
    meta["first_complete_month"] = output["monthly"][0]["month"] if output.get("monthly") else None
    meta["first_complete_week_start"] = output["weekly"][0]["week_start"] if output.get("weekly") else None


def build_comparison(cities: dict, period: str) -> list[dict]:
    by_city = {key: {row["time"]: row for row in cities[key].get(period, [])} for key in CITY_KEYS}
    shared = set(by_city[CITY_KEYS[0]])
    for key in CITY_KEYS[1:]:
        shared &= set(by_city[key])

    out = []
    for timestamp in sorted(shared):
        row = {"time": timestamp}
        for key in CITY_KEYS:
            source = by_city[key][timestamp]
            row[f"{key}_alerts_per_day"] = source.get("alerts_per_day")
            row[f"{key}_avg_daily_alert_hours"] = source.get("avg_daily_alert_hours")
            row[f"{key}_avg_alert_duration_min"] = source.get("avg_alert_duration_min")
        out.append(row)
    return out


def comparison_columns(metric: str) -> list[dict]:
    return [TIME_COL] + [{"selector": f"{key}_{metric}", "text": CITY_LABELS[key], "type": "number"} for key in CITY_KEYS]


def update_comparison_panels(obj: dict, data: dict) -> None:
    by_id = {p.get("id"): p for p in obj.get("panels", [])}
    monthly = data.get("comparison", {}).get("monthly", [])
    weekly = data.get("comparison", {}).get("weekly", [])
    monthly_start = monthly[0]["time"][:10] if monthly else "—"
    weekly_start = weekly[0]["time"][:10] if weekly else "—"
    description = (
        "Порівняння використовує спільний повний період для всіх показаних міст. "
        "Київ, Харків і Запоріжжя мають exact-city ряди; інші міста — районний proxy після "
        "валідованої дати переходу, з включенням explicit oblast сигналів у перехідному періоді. "
        f"Спільний місячний ряд починається {monthly_start}; тижневий — {weekly_start}."
    )

    panel = by_id.get(41)
    if panel:
        panel["description"] = description
        for target in panel.get("targets", []):
            target["root_selector"] = "$.comparison.${comparison_period}"
            target["columns"] = comparison_columns("alerts_per_day")

    panel = by_id.get(42)
    if panel:
        panel["description"] = description
        fields = ", ".join(
            f'"{key}": "${{duration_unit}}" = "minutes" ? {key}_avg_daily_alert_hours * 60 : {key}_avg_daily_alert_hours'
            for key in CITY_KEYS
        )
        root = '$.comparison.${comparison_period}.{' + '"time": time, ' + fields + '}'
        for target in panel.get("targets", []):
            target["root_selector"] = root
            target["columns"] = [TIME_COL] + [{"selector": key, "text": CITY_LABELS[key], "type": "number"} for key in CITY_KEYS]

    panel = by_id.get(43)
    if panel:
        panel["description"] = description
        fields = ", ".join(
            f'"{key}": "${{duration_unit}}" = "hours" ? {key}_avg_alert_duration_min / 60 : {key}_avg_alert_duration_min'
            for key in CITY_KEYS
        )
        root = '$.comparison.${comparison_period}.{' + '"time": time, ' + fields + '}'
        for target in panel.get("targets", []):
            target["root_selector"] = root
            target["columns"] = [TIME_COL] + [{"selector": key, "text": CITY_LABELS[key], "type": "number"} for key in CITY_KEYS]


def update_city_variable(obj: dict) -> None:
    variables = obj.setdefault("templating", {}).setdefault("list", [])
    city_var = next((v for v in variables if v.get("name") == "city"), None)
    if not city_var:
        return
    options = [{"selected": key == "kyiv", "text": CITY_LABELS[key], "value": key} for key in CITY_KEYS]
    city_var["options"] = options
    city_var["query"] = ", ".join(f"{CITY_LABELS[key]} : {key}" for key in CITY_KEYS)
    city_var["current"] = {"selected": True, "text": "Київ", "value": "kyiv"}


def methodology_content(data: dict) -> str:
    proxy_lines = []
    for key in PROXY_KEYS:
        meta = data["cities"][key]["meta"]
        proxy_lines.append(f"- **{meta['city_label']}**: `{meta['proxy_raion']}`; coverage з {meta['coverage_start']}.")
    return (
        "**Географія та джерела.** Київ використовує міські відкриті дані та Kyiv Digital fallback. "
        "Харків і Запоріжжя використовують exact-city записи рівня `hromada` з "
        f"[official_data_uk.csv]({CITY_SOURCE_URL}).  \n\n"
        "Для решти показаних облцентрів використовується **районний proxy**: після валідованої дати "
        "переходу ряд дорівнює union сигналів відповідного району та explicit `oblast` сигналів. "
        "У 2026 році explicit `oblast` записи в цьому джерелі фактично не додають часу, тому ряд "
        "дорівнює районному. До coverage-start дані не backfill-яться старими обласними тривогами.  \n\n"
        + "\n".join(proxy_lines)
        + "  \n\n"
        "**Відкладені міста.** Миколаїв і Тернопіль не включені через несумісну географію сигналів; "
        "Донецьк і Луганськ потребують окремої методології. Херсон, Луцьк, Ужгород, Івано-Франківськ "
        "і Чернівці поки не включені до production, оскільки стабільний районний ряд є, але точну дату "
        "rollout ще не підтверджено зовнішнім офіційним джерелом.  \n\n"
        "**Агрегація.** Поточний календарний день виключено. Для proxy перекривні районні та обласні "
        "інтервали зливаються в єдині alert episodes до підрахунку і тривалості, і кількості тривог. "
        "Перший неповний місяць та тиждень після coverage-start виключаються. Тривоги через північ "
        "розподіляються між календарними добами в Europe/Kyiv. Порівняння міст використовує лише "
        "спільні повні календарні періоди.  \n\n"
        "Пропозиції надсилати @olbalakin в телеграм"
    )


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    missing_exact = [key for key in EXACT_KEYS if key not in cities]
    if missing_exact:
        raise RuntimeError(f"Expected exact-city data missing after add_duration_unit_switch: {missing_exact}")

    cities["kyiv"].setdefault("meta", {}).update({"source_type": "exact_city", "coverage_start": cities["kyiv"]["meta"].get("first_city_level_date")})
    cities["kharkiv"].setdefault("meta", {}).update({"source_type": "exact_city", "coverage_start": "2025-02-17"})
    cities["zaporizhzhia"].setdefault("meta", {}).update({"source_type": "exact_city", "coverage_start": "2025-03-19"})

    now_local = datetime.now(TZ)
    proxy_alerts = fetch_proxy_alerts()
    for key in PROXY_KEYS:
        cfg = PROXY_CONFIG[key]
        alerts = proxy_alerts[key]
        coverage_day = date.fromisoformat(cfg["coverage_start"])
        first_record = min(a.start for a in alerts)
        meta = {
            "city": key,
            "city_label": cfg["label"],
            "source_type": "raion_proxy",
            "proxy_raion": cfg["raion"],
            "oblast": cfg["oblast"],
            "coverage_start": cfg["coverage_start"],
            "coverage_start_basis": cfg["coverage_basis"],
            "city_source_url": CITY_SOURCE_URL,
            "proxy_completed_alert_episodes": len(alerts),
            "first_proxy_record": first_record.isoformat(),
            "latest_proxy_record_start": max(a.start for a in alerts).isoformat(),
            "latest_proxy_record_end": max(a.end for a in alerts).isoformat(),
            "data_source_kind": "eponymous raion proxy union explicit oblast after validated rollout",
        }
        output = build_outputs(alerts, now_local, meta)
        enrich_weekly(output, alerts)
        trim_to_complete_coverage(output, coverage_day)
        cities[key] = output

    data["cities"] = {key: cities[key] for key in CITY_KEYS}
    data["comparison"] = {
        "monthly": build_comparison(data["cities"], "monthly"),
        "weekly": build_comparison(data["cities"], "weekly"),
    }
    data["multicity_meta"] = {
        "city_source_url": CITY_SOURCE_URL,
        "production_city_keys": CITY_KEYS,
        "deferred": DEFERRED,
        "cities": {
            key: {
                "label": CITY_LABELS[key],
                "source_type": data["cities"][key]["meta"].get("source_type"),
                "coverage_start": data["cities"][key]["meta"].get("coverage_start"),
                "first_complete_month": data["cities"][key]["meta"].get("first_complete_month"),
                "first_complete_week_start": data["cities"][key]["meta"].get("first_complete_week_start"),
                "proxy_raion": data["cities"][key]["meta"].get("proxy_raion"),
            }
            for key in CITY_KEYS
        },
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    update_city_variable(obj)
    update_comparison_panels(obj, data)
    panel30 = next((p for p in obj.get("panels", []) if p.get("id") == 30), None)
    if panel30:
        panel30["title"] = "Джерела та методологія"
        panel30.setdefault("options", {})["mode"] = "markdown"
        panel30["options"]["content"] = methodology_content(data)
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Expanded production multicity set:", ", ".join(CITY_LABELS[k] for k in CITY_KEYS))
    print("Monthly shared comparison starts:", data["comparison"]["monthly"][0]["time"] if data["comparison"]["monthly"] else None)
    print("Weekly shared comparison starts:", data["comparison"]["weekly"][0]["time"] if data["comparison"]["weekly"] else None)


if __name__ == "__main__":
    main()
