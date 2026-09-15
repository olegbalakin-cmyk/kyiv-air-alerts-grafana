#!/usr/bin/env python3
import json
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1] / "grafana" / "dashboard.json"

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


def main():
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    by_id = {p.get("id"): p for p in obj.get("panels", [])}

    # Make it explicit that all top KPIs exclude the current calendar day.
    if 1 in by_id:
        by_id[1]["title"] = "Тривог за останні 28 завершених днів"

    variables = obj.setdefault("templating", {}).setdefault("list", [])
    variables[:] = [v for v in variables if v.get("name") != "duration_unit"]
    variables.insert(0, {
        "name": "duration_unit",
        "label": "Одиниці часу",
        "type": "custom",
        "query": "Хвилини : minutes, Години : hours",
        "current": {"selected": True, "text": "Хвилини", "value": "minutes"},
        "options": [
            {"selected": True, "text": "Хвилини", "value": "minutes"},
            {"selected": False, "text": "Години", "value": "hours"},
        ],
        "includeAll": False,
        "multi": False,
        "hide": 0,
        "skipUrlSync": False,
    })

    specs = {
        2: (
            "Час під тривогою за останні 28 завершених днів — ${duration_unit:text}",
            '$.kpis.{"value": "${duration_unit}" = "minutes" ? alert_hours_28d * 60 : alert_hours_28d}',
            [{"selector": "value", "text": "Час під тривогою", "type": "number"}],
        ),
        3: (
            "Середня тривалість тривоги за останні 28 завершених днів — ${duration_unit:text}",
            '$.kpis.{"value": "${duration_unit}" = "hours" ? avg_alert_duration_min_28d / 60 : avg_alert_duration_min_28d}',
            [{"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        12: (
            "Середній час під тривогою на добу — за місяцями (${duration_unit:text})",
            '$.monthly.{"time": time, "value": "${duration_unit}" = "minutes" ? avg_daily_alert_hours * 60 : avg_daily_alert_hours}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою на добу", "type": "number"}],
        ),
        13: (
            "Середня тривалість однієї тривоги — за місяцем старту (${duration_unit:text})",
            '$.monthly.{"time": time, "value": "${duration_unit}" = "hours" ? avg_alert_duration_min / 60 : avg_alert_duration_min}',
            [TIME_COL, {"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        14: (
            "Середній час під тривогою на добу — за повними тижнями (${duration_unit:text})",
            '$.weekly.{"time": time, "value": "${duration_unit}" = "minutes" ? avg_daily_alert_hours * 60 : avg_daily_alert_hours}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою на добу", "type": "number"}],
        ),
        15: (
            "Середня тривалість однієї тривоги — за повними тижнями (${duration_unit:text})",
            '$.weekly.{"time": time, "value": "${duration_unit}" = "hours" ? avg_alert_duration_min / 60 : avg_alert_duration_min}',
            [TIME_COL, {"selector": "value", "text": "Середня тривалість", "type": "number"}],
        ),
        20: (
            "Останні 28 завершених днів — сумарний час під тривогою (${duration_unit:text})",
            '$.daily28.{"time": time, "value": "${duration_unit}" = "minutes" ? total_alert_duration_minutes : total_alert_duration_hours}',
            [TIME_COL, {"selector": "value", "text": "Час під тривогою", "type": "number"}],
        ),
        21: (
            "Останні 28 завершених днів — кількість тривог і середня тривалість (${duration_unit:text})",
            '$.daily28.{"time": time, "alerts_started": alerts_started, "avg_duration": "${duration_unit}" = "hours" ? avg_alert_duration_minutes / 60 : avg_alert_duration_minutes}',
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
        neutralize_units(panel)

    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added global hours/minutes switch and clarified 28-day KPI titles in", DASHBOARD)


if __name__ == "__main__":
    main()
