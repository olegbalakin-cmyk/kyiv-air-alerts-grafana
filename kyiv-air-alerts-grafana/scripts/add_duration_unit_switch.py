#!/usr/bin/env python3
from __future__ import annotations

import copy
import csv
import io
import json
from datetime import date, datetime
from pathlib import Path
from statistics import mean

from update_data import Alert, TZ, build_outputs, daterange, http_session, round3, union_daily_seconds

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"
KYIV_ALERTS_FILE = ROOT / "data" / "alerts_combined.json"
CITY_SOURCE_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/official_data_uk.csv"
)

CITY_CONFIG = {
    "kharkiv": {
        "label": "Харків",
        "hromada": "м. Харків та Харківська територіальна громада",
    },
    "zaporizhzhia": {
        "label": "Запоріжжя",
        "hromada": "м. Запоріжжя та Запорізька територіальна громада",
    },
}
CITY_LABELS = {
    "kyiv": "Київ",
    "kharkiv": "Харків",
    "zaporizhzhia": "Запоріжжя",
}
CITY_KEYS = ["kyiv", "kharkiv", "zaporizhzhia"]

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


def set_query(panel, root, columns):
    for target in panel.get("targets", []):
        target["root_selector"] = root
        target["columns"] = columns


def neutralize_units(panel):
    panel.get("fieldConfig", {}).get("defaults", {})["unit"] = "short"
    for override in panel.get("fieldConfig", {}).get("overrides", []):
        for prop in override.get("properties", []):
            if prop.get("id") == "unit":
                prop["value"] = "short"
            elif prop.get("id") == "custom.axisLabel":
                prop["value"] = "Тривалість"


def parse_source_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        raise ValueError(f"Expected timezone-aware timestamp, got {value!r}")
    return dt.astimezone(TZ)


def fetch_city_alerts() -> dict[str, list[Alert]]:
    session = http_session()
    response = session.get(CITY_SOURCE_URL, timeout=120)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")

    hromada_to_key = {cfg["hromada"]: key for key, cfg in CITY_CONFIG.items()}
    found: dict[str, list[Alert]] = {key: [] for key in CITY_CONFIG}
    seen: dict[str, set[tuple[str, str]]] = {key: set() for key in CITY_CONFIG}

    for row in csv.DictReader(io.StringIO(text)):
        if (row.get("level") or "").strip() != "hromada":
            continue
        key = hromada_to_key.get((row.get("hromada") or "").strip())
        if not key:
            continue
        s = (row.get("started_at") or "").strip()
        e = (row.get("finished_at") or "").strip()
        if not s or not e or (s, e) in seen[key]:
            continue
        try:
            start = parse_source_dt(s)
            end = parse_source_dt(e)
        except ValueError:
            continue
        if end <= start:
            continue
        seen[key].add((s, e))
        found[key].append(Alert(start=start, end=end, source="vadimkin_official"))

    for key, alerts in found.items():
        alerts.sort(key=lambda a: a.start)
        if not alerts:
            raise RuntimeError(f"No city-level alerts found for {CITY_LABELS[key]}")
    return found


def enrich_weekly(output: dict, alerts: list[Alert]) -> None:
    for row in output.get("weekly", []):
        ws = date.fromisoformat(row["week_start"])
        we = date.fromisoformat(row["week_end"])
        daily_seconds = union_daily_seconds(alerts, ws, we)
        row["avg_daily_alert_hours"] = round3(
            sum(daily_seconds.get(d, 0.0) for d in daterange(ws, we)) / 7.0 / 3600.0
        )
        event_durations = [
            alert.duration_seconds / 60.0
            for alert in alerts
            if ws <= alert.start.astimezone(TZ).date() <= we
        ]
        row["avg_alert_duration_min"] = round3(mean(event_durations) if event_durations else None)


def trim_first_partial_periods(output: dict, first_day: date) -> None:
    output["monthly"] = [
        row
        for row in output.get("monthly", [])
        if date.fromisoformat(row["month"] + "-01") > first_day
    ]
    output["weekly"] = [
        row
        for row in output.get("weekly", [])
        if date.fromisoformat(row["week_start"]) > first_day
    ]
    output.setdefault("meta", {})["first_city_level_date"] = first_day.isoformat()
    output["meta"]["first_complete_month"] = output["monthly"][0]["month"] if output.get("monthly") else None
    output["meta"]["first_complete_week_start"] = output["weekly"][0]["week_start"] if output.get("weekly") else None


def build_comparison(cities: dict, period: str) -> list[dict]:
    by_city = {
        key: {row["time"]: row for row in cities[key].get(period, [])}
        for key in CITY_KEYS
    }
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


def build_city_data() -> dict:
    dashboard_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    kyiv_raw = json.loads(KYIV_ALERTS_FILE.read_text(encoding="utf-8"))
    kyiv_alerts = [
        Alert(
            start=datetime.fromisoformat(row["start"]).astimezone(TZ),
            end=datetime.fromisoformat(row["end"]).astimezone(TZ),
            source=row.get("source", "kyiv_combined"),
        )
        for row in kyiv_raw
    ]
    if not kyiv_alerts:
        raise RuntimeError("Kyiv audit file contains no alerts")

    now_local = datetime.now(TZ)
    source_alerts = fetch_city_alerts()

    kyiv_view = copy.deepcopy(
        {
            "meta": dashboard_data.get("meta", {}),
            "kpis": dashboard_data.get("kpis", []),
            "monthly": dashboard_data.get("monthly", []),
            "weekly": dashboard_data.get("weekly", []),
            "daily28": dashboard_data.get("daily28", []),
        }
    )
    kyiv_first = min(a.start.astimezone(TZ).date() for a in kyiv_alerts)
    kyiv_view.setdefault("meta", {}).update(
        {
            "city": "kyiv",
            "city_label": "Київ",
            "city_level_only": True,
            "first_city_record": min(a.start for a in kyiv_alerts).isoformat(),
            "data_source_kind": "Kyiv municipal open data + Kyiv Digital fallback",
        }
    )
    trim_first_partial_periods(kyiv_view, kyiv_first)

    cities = {"kyiv": kyiv_view}
    for key in ["kharkiv", "zaporizhzhia"]:
        alerts = source_alerts[key]
        first = min(a.start for a in alerts)
        meta = {
            "city": key,
            "city_label": CITY_LABELS[key],
            "city_level_only": True,
            "hromada": CITY_CONFIG[key]["hromada"],
            "city_source_url": CITY_SOURCE_URL,
            "city_completed_alerts": len(alerts),
            "first_city_record": first.isoformat(),
            "latest_city_record_start": max(a.start for a in alerts).isoformat(),
            "latest_city_record_end": max(a.end for a in alerts).isoformat(),
            "data_source_kind": "official city-level hromada records",
        }
        output = build_outputs(alerts, now_local, meta)
        enrich_weekly(output, alerts)
        trim_first_partial_periods(output, first.astimezone(TZ).date())
        cities[key] = output

    dashboard_data["cities"] = cities
    dashboard_data["comparison"] = {
        "monthly": build_comparison(cities, "monthly"),
        "weekly": build_comparison(cities, "weekly"),
    }
    dashboard_data["multicity_meta"] = {
        "city_source_url": CITY_SOURCE_URL,
        "city_level_only": True,
        "cities": {
            key: {
                "label": CITY_LABELS[key],
                "first_city_level_date": cities[key]["meta"].get("first_city_level_date"),
                "first_complete_month": cities[key]["meta"].get("first_complete_month"),
                "first_complete_week_start": cities[key]["meta"].get("first_complete_week_start"),
            }
            for key in CITY_KEYS
        },
    }
    DATA_FILE.write_text(json.dumps(dashboard_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dashboard_data


def custom_variable(name: str, label: str, options: list[tuple[str, str]], default: str) -> dict:
    selected_text = next(text for text, value in options if value == default)
    return {
        "name": name,
        "label": label,
        "type": "custom",
        "query": ", ".join(f"{text} : {value}" for text, value in options),
        "current": {"selected": True, "text": selected_text, "value": default},
        "options": [
            {"selected": value == default, "text": text, "value": value}
            for text, value in options
        ],
        "includeAll": False,
        "multi": False,
        "hide": 0,
        "skipUrlSync": False,
    }


def comparison_columns(metric: str) -> list[dict]:
    return [TIME_COL] + [
        {"selector": f"{key}_{metric}", "text": CITY_LABELS[key], "type": "number"}
        for key in CITY_KEYS
    ]


def style_comparison_panel(panel: dict, unit: str = "short", axis_label: str = "") -> None:
    defaults = panel.setdefault("fieldConfig", {}).setdefault("defaults", {})
    defaults["unit"] = unit
    defaults["decimals"] = 2
    defaults.setdefault("custom", {})["axisLabel"] = axis_label
    panel["fieldConfig"]["overrides"] = []
    options = panel.setdefault("options", {})
    options.setdefault("legend", {})["showLegend"] = True
    options["legend"]["placement"] = "bottom"
    options.setdefault("tooltip", {})["mode"] = "multi"


def comparison_description(data: dict) -> str:
    monthly = data.get("comparison", {}).get("monthly", [])
    weekly = data.get("comparison", {}).get("weekly", [])
    monthly_start = monthly[0]["time"][:10] if monthly else "—"
    weekly_start = weekly[0]["time"][:10] if weekly else "—"
    return (
        "Порівнюються тільки city-level дані. Обласні тривоги не підмішуються. "
        f"Спільний повний місячний ряд починається {monthly_start}; "
        f"спільний повний тижневий ряд — {weekly_start}."
    )


def add_comparison_panels(obj: dict, by_id: dict, data: dict) -> None:
    panels = [p for p in obj.get("panels", []) if p.get("id") not in {40, 41, 42, 43}]
    methodology = next((p for p in panels if p.get("id") == 30), None)
    if methodology:
        row_y = methodology.get("gridPos", {}).get("y", 0)
    else:
        row_y = max(
            (p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0) for p in panels),
            default=0,
        )

    for panel in panels:
        gp = panel.get("gridPos", {})
        if gp.get("y", 0) >= row_y:
            gp["y"] = gp.get("y", 0) + 28

    row = {
        "id": 40,
        "type": "row",
        "title": "Порівняння міст",
        "collapsed": False,
        "panels": [],
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": row_y},
    }

    alerts = copy.deepcopy(by_id[10])
    alerts["id"] = 41
    alerts["title"] = "Порівняння міст — середня кількість тривог на день (${comparison_period:text})"
    alerts["description"] = comparison_description(data)
    alerts["gridPos"] = {"h": 9, "w": 24, "x": 0, "y": row_y + 1}
    set_query(alerts, "$.comparison.${comparison_period}", comparison_columns("alerts_per_day"))
    style_comparison_panel(alerts, "suffix: тривог/день", "Тривог на день")

    daily_time = copy.deepcopy(by_id[12])
    daily_time["id"] = 42
    daily_time["title"] = "Порівняння міст — середній час під тривогою на добу (${comparison_period:text}, ${duration_unit:text})"
    daily_time["description"] = comparison_description(data)
    daily_time["gridPos"] = {"h": 9, "w": 24, "x": 0, "y": row_y + 10}
    daily_root = (
        '$.comparison.${comparison_period}.{' 
        '"time": time, '
        '"kyiv": "${duration_unit}" = "minutes" ? kyiv_avg_daily_alert_hours * 60 : kyiv_avg_daily_alert_hours, '
        '"kharkiv": "${duration_unit}" = "minutes" ? kharkiv_avg_daily_alert_hours * 60 : kharkiv_avg_daily_alert_hours, '
        '"zaporizhzhia": "${duration_unit}" = "minutes" ? zaporizhzhia_avg_daily_alert_hours * 60 : zaporizhzhia_avg_daily_alert_hours}'
    )
    set_query(
        daily_time,
        daily_root,
        [TIME_COL] + [
            {"selector": key, "text": CITY_LABELS[key], "type": "number"}
            for key in CITY_KEYS
        ],
    )
    style_comparison_panel(daily_time, "short", "Тривалість")

    duration = copy.deepcopy(by_id[13])
    duration["id"] = 43
    duration["title"] = "Порівняння міст — середня тривалість однієї тривоги (${comparison_period:text}, ${duration_unit:text})"
    duration["description"] = comparison_description(data)
    duration["gridPos"] = {"h": 9, "w": 24, "x": 0, "y": row_y + 19}
    duration_root = (
        '$.comparison.${comparison_period}.{' 
        '"time": time, '
        '"kyiv": "${duration_unit}" = "hours" ? kyiv_avg_alert_duration_min / 60 : kyiv_avg_alert_duration_min, '
        '"kharkiv": "${duration_unit}" = "hours" ? kharkiv_avg_alert_duration_min / 60 : kharkiv_avg_alert_duration_min, '
        '"zaporizhzhia": "${duration_unit}" = "hours" ? zaporizhzhia_avg_alert_duration_min / 60 : zaporizhzhia_avg_alert_duration_min}'
    )
    set_query(
        duration,
        duration_root,
        [TIME_COL] + [
            {"selector": key, "text": CITY_LABELS[key], "type": "number"}
            for key in CITY_KEYS
        ],
    )
    style_comparison_panel(duration, "short", "Тривалість")

    panels.extend([row, alerts, daily_time, duration])
    panels.sort(key=lambda p: (p.get("gridPos", {}).get("y", 0), p.get("gridPos", {}).get("x", 0)))
    obj["panels"] = panels


def update_methodology(panel: dict, data: dict) -> None:
    city_meta = data["multicity_meta"]["cities"]
    panel["title"] = "Джерела та методологія"
    panel.setdefault("options", {})["mode"] = "markdown"
    panel["options"]["content"] = (
        "**Джерела.** Київ: [Портал відкритих даних Києва]"
        "(https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download) "
        "+ [Kyiv Digital — live-історія](https://kyiv.digital/storage/air-alert/stats.html) як fallback для свіжих завершених подій.  \n"
        "Харків і Запоріжжя: [official_data_uk.csv]"
        f"({CITY_SOURCE_URL}) — використовуються тільки записи рівня `hromada` для відповідної міської громади.  \n\n"
        "**Початок city-level рядів:** "
        f"Київ — {city_meta['kyiv']['first_city_level_date']}; "
        f"Харків — {city_meta['kharkiv']['first_city_level_date']}; "
        f"Запоріжжя — {city_meta['zaporizhzhia']['first_city_level_date']}. "
        "Обласні дані не використовуються для заповнення попередніх періодів.  \n\n"
        "Поточний календарний день завжди виключено. Перший неповний місяць і перший неповний тиждень кожного city-level ряду не включаються до довгих агрегатів. "
        "Тривоги через північ розподіляються між календарними добами в часовому поясі Europe/Kyiv; перекриття інтервалів зливаються, щоб не подвоювати час.  \n\n"
        "Пропозиції надсилати @olbalakin в телеграм"
    )


def main():
    data = build_city_data()

    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    obj["title"] = "Повітряні тривоги — міста України"
    by_id = {p.get("id"): p for p in obj.get("panels", [])}

    variables = obj.setdefault("templating", {}).setdefault("list", [])
    variables[:] = [
        v for v in variables if v.get("name") not in {"city", "duration_unit", "comparison_period"}
    ]
    variables[:0] = [
        custom_variable(
            "city",
            "Місто",
            [("Київ", "kyiv"), ("Харків", "kharkiv"), ("Запоріжжя", "zaporizhzhia")],
            "kyiv",
        ),
        custom_variable(
            "duration_unit",
            "Одиниці часу",
            [("Хвилини", "minutes"), ("Години", "hours")],
            "minutes",
        ),
        custom_variable(
            "comparison_period",
            "Порівняння",
            [("Місяці", "monthly"), ("Тижні", "weekly")],
            "monthly",
        ),
    ]

    city_base = "$.cities.${city}"
    specs = {
        1: (
            "${city:text}: тривог за останні 28 завершених днів",
            f"{city_base}.kpis",
            [{"selector": "alerts_28d", "text": "Тривог", "type": "number"}],
        ),
        2: (
            "${city:text}: час під тривогою за останні 28 завершених днів — ${duration_unit:text}",
            f'{city_base}.kpis.{{"value": "${{duration_unit}}" = "minutes" ? alert_hours_28d * 60 : alert_hours_28d}}',
            [{"selector": "value", "text": "Час під тривогою", "type": "number"}],
        ),
        3: (
            "${city:text}: середня тривалість тривоги за останні 28 завершених днів — ${duration_unit:text}",
            f'{city_base}.kpis.{{"value": "${{duration_unit}}" = "hours" ? avg_alert_duration_min_28d / 60 : avg_alert_duration_min_28d}}',
            [{"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        10: (
            "${city:text}: середня кількість тривог на день — за місяцями",
            f"{city_base}.monthly",
            [TIME_COL, {"selector": "alerts_per_day", "text": "Тривог на день", "type": "number"}],
        ),
        11: (
            "${city:text}: середня кількість тривог на день — за повними тижнями",
            f"{city_base}.weekly",
            [TIME_COL, {"selector": "alerts_per_day", "text": "Тривог на день", "type": "number"}],
        ),
        12: (
            "${city:text}: середній час під тривогою на добу — за місяцями (${duration_unit:text})",
            f'{city_base}.monthly.{{"time": time, "value": "${{duration_unit}}" = "minutes" ? avg_daily_alert_hours * 60 : avg_daily_alert_hours}}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою на добу", "type": "number"}],
        ),
        13: (
            "${city:text}: середня тривалість однієї тривоги — за місяцем старту (${duration_unit:text})",
            f'{city_base}.monthly.{{"time": time, "value": "${{duration_unit}}" = "hours" ? avg_alert_duration_min / 60 : avg_alert_duration_min}}',
            [TIME_COL, {"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        14: (
            "${city:text}: середній час під тривогою на добу — за повними тижнями (${duration_unit:text})",
            f'{city_base}.weekly.{{"time": time, "value": "${{duration_unit}}" = "minutes" ? avg_daily_alert_hours * 60 : avg_daily_alert_hours}}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою на добу", "type": "number"}],
        ),
        15: (
            "${city:text}: середня тривалість однієї тривоги — за повними тижнями (${duration_unit:text})",
            f'{city_base}.weekly.{{"time": time, "value": "${{duration_unit}}" = "hours" ? avg_alert_duration_min / 60 : avg_alert_duration_min}}',
            [TIME_COL, {"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        20: (
            "${city:text}: останні 28 завершених днів — сумарний час під тривогою (${duration_unit:text})",
            f'{city_base}.daily28.{{"time": time, "value": "${{duration_unit}}" = "minutes" ? total_alert_duration_minutes : total_alert_duration_hours}}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою", "type": "number"}],
        ),
        21: (
            "${city:text}: останні 28 завершених днів — кількість тривог і середня тривалість (${duration_unit:text})",
            f'{city_base}.daily28.{{"time": time, "alerts_started": alerts_started, "avg_duration": "${{duration_unit}}" = "hours" ? avg_alert_duration_minutes / 60 : avg_alert_duration_minutes}}',
            [
                TIME_COL,
                {"selector": "alerts_started", "text": "Кількість тривог", "type": "number"},
                {"selector": "avg_duration", "text": "Середня тривалість", "type": "number"},
            ],
        ),
    }

    for panel_id, (title, root, columns) in specs.items():
        panel = by_id.get(panel_id)
        if not panel:
            continue
        panel["title"] = title
        set_query(panel, root, columns)
        if panel_id in {2, 3, 12, 13, 14, 15, 20, 21}:
            neutralize_units(panel)

    add_comparison_panels(obj, by_id, data)

    by_id = {p.get("id"): p for p in obj.get("panels", [])}
    if 30 in by_id:
        update_methodology(by_id[30], data)

    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added city switch, duration-unit switch, multicity data and comparison panels to", DASHBOARD)


if __name__ == "__main__":
    main()
