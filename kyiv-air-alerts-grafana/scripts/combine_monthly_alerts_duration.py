#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"

CITY_CONFIG = {
    "kyiv": {
        "monthly_rate": 104,
        "monthly_hours": 106,
        "duration": 107,
        "short": 111,
        "label": "Київ",
    },
    "kharkiv": {
        "monthly_rate": 204,
        "monthly_hours": 206,
        "duration": 207,
        "short": 211,
        "label": "Харків",
    },
    "zaporizhzhia": {
        "monthly_rate": 304,
        "monthly_hours": 306,
        "duration": 307,
        "short": 311,
        "label": "Запоріжжя",
    },
}

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


def walk_with_parent(panels: list[dict]):
    for panel in list(panels):
        yield panels, panel
        children = panel.get("panels", [])
        if children:
            yield from walk_with_parent(children)


def walk_panels(panels: list[dict]):
    for _, panel in walk_with_parent(panels):
        yield panel


def find_panel(panels: list[dict], panel_id: int) -> dict:
    for panel in walk_panels(panels):
        if panel.get("id") == panel_id:
            return panel
    raise RuntimeError(f"Panel {panel_id} not found")


def configure_daily_intensity_combo(panel: dict, city_key: str, city_label: str) -> None:
    """Combine monthly alerts/day and alert-hours/day into one dual-axis panel."""
    panel["title"] = (
        f"{city_label}: середня кількість тривог на день і час під тривогою на добу — за місяцями"
    )
    panel["description"] = (
        "Повні календарні місяці; поточний неповний місяць виключено. "
        "Стовпчики — середній час під тривогою на одну календарну добу; "
        "лінія — середня кількість тривог на день. Тривоги через північ "
        "розподілено між календарними добами, перекриття не подвоюються."
    )

    if not panel.get("targets"):
        raise RuntimeError(f"Monthly alerts/day panel missing target for {city_label}")
    target = panel["targets"][0]
    target["columns"] = [
        TIME_COL,
        {
            "selector": "alert_hours_per_day",
            "text": "Час під тривогою на добу",
            "type": "number",
        },
        {
            "selector": "alerts_per_day",
            "text": "Тривог на день",
            "type": "number",
        },
    ]
    target["root_selector"] = (
        f'$.cities.{city_key}.monthly.{{"time": time, '
        '"alert_hours_per_day": avg_daily_alert_hours, '
        '"alerts_per_day": alerts_per_day}'
    )

    defaults = panel.setdefault("fieldConfig", {}).setdefault("defaults", {})
    defaults["unit"] = "short"
    defaults["decimals"] = 2
    panel["fieldConfig"]["overrides"] = [
        {
            "matcher": {"id": "byName", "options": "Час під тривогою на добу"},
            "properties": [
                {"id": "custom.drawStyle", "value": "bars"},
                {"id": "custom.fillOpacity", "value": 65},
                {"id": "custom.lineWidth", "value": 1},
                {"id": "custom.showPoints", "value": "never"},
                {"id": "custom.axisPlacement", "value": "left"},
                {"id": "custom.axisLabel", "value": "Години на добу"},
                {"id": "unit", "value": "suffix: год/день"},
                {"id": "decimals", "value": 2},
            ],
        },
        {
            "matcher": {"id": "byName", "options": "Тривог на день"},
            "properties": [
                {"id": "custom.drawStyle", "value": "line"},
                {"id": "custom.lineWidth", "value": 3},
                {"id": "custom.showPoints", "value": "auto"},
                {"id": "custom.pointSize", "value": 5},
                {"id": "custom.axisPlacement", "value": "right"},
                {"id": "custom.axisLabel", "value": "Тривог на день"},
                {"id": "unit", "value": "suffix: тривог/день"},
                {"id": "decimals", "value": 2},
            ],
        },
    ]
    options = panel.setdefault("options", {})
    options.setdefault("tooltip", {})["mode"] = "multi"
    legend = options.setdefault("legend", {})
    legend["showLegend"] = True
    legend.setdefault("displayMode", "list")
    legend.setdefault("placement", "bottom")


def configure_duration_combo(panel: dict, short_panel: dict, city_key: str, city_label: str) -> None:
    panel["title"] = (
        f"{city_label}: кількість тривог і середня тривалість однієї тривоги — за місяцями"
    )
    panel["description"] = (
        "Повні календарні місяці; поточний неповний місяць виключено. "
        "Стовпчики — абсолютна кількість завершених тривог за місяцем старту; "
        "лінія — середня повна тривалість тривог, що стартували цього місяця."
    )

    if not panel.get("targets"):
        raise RuntimeError(f"Monthly duration panel {panel.get('id')} has no target")
    target = panel["targets"][0]
    target["columns"] = [
        TIME_COL,
        {"selector": "alerts_started", "text": "Кількість тривог", "type": "number"},
        {"selector": "avg_duration", "text": "Середня тривалість", "type": "number"},
    ]
    target["root_selector"] = (
        f'$.cities.{city_key}.monthly.{{"time": time, '
        '"alerts_started": alerts_started, '
        '"avg_duration": avg_alert_duration_min / 60}'
    )

    panel["fieldConfig"] = copy.deepcopy(short_panel["fieldConfig"])
    panel["options"] = copy.deepcopy(short_panel["options"])
    panel.pop("timeFrom", None)
    panel["fieldConfig"]["overrides"] = [
        {
            "matcher": {"id": "byName", "options": "Кількість тривог"},
            "properties": [
                {"id": "custom.drawStyle", "value": "bars"},
                {"id": "custom.fillOpacity", "value": 70},
                {"id": "custom.lineWidth", "value": 1},
                {"id": "custom.showPoints", "value": "never"},
                {"id": "custom.axisPlacement", "value": "left"},
                {"id": "custom.axisLabel", "value": "Кількість тривог"},
                {"id": "unit", "value": "short"},
                {"id": "decimals", "value": 0},
            ],
        },
        {
            "matcher": {"id": "byName", "options": "Середня тривалість"},
            "properties": [
                {"id": "custom.drawStyle", "value": "line"},
                {"id": "custom.lineWidth", "value": 3},
                {"id": "custom.showPoints", "value": "always"},
                {"id": "custom.pointSize", "value": 5},
                {"id": "custom.axisPlacement", "value": "right"},
                {"id": "custom.axisLabel", "value": "Години"},
                {"id": "unit", "value": "suffix: год"},
                {"id": "decimals", "value": 1},
            ],
        },
    ]
    panel.setdefault("options", {}).setdefault("legend", {})["showLegend"] = True
    panel["options"].setdefault("tooltip", {})["mode"] = "multi"


def remove_panel_and_compact(panels: list[dict], panel_id: int) -> None:
    for parent, panel in walk_with_parent(panels):
        if panel.get("id") != panel_id:
            continue
        removed_y = panel.get("gridPos", {}).get("y", 0)
        removed_h = panel.get("gridPos", {}).get("h", 0)
        parent.remove(panel)
        for sibling in parent:
            gp = sibling.get("gridPos", {})
            if gp.get("y", 0) > removed_y:
                gp["y"] = max(0, gp.get("y", 0) - removed_h)
        return
    raise RuntimeError(f"Panel {panel_id} not found for removal")


def main() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = dashboard.get("panels", [])

    # Configure all panels before removing the now-redundant monthly-hours panel.
    for city_key, cfg in CITY_CONFIG.items():
        monthly_rate = find_panel(panels, cfg["monthly_rate"])
        configure_daily_intensity_combo(monthly_rate, city_key, cfg["label"])

        duration = find_panel(panels, cfg["duration"])
        short = find_panel(panels, cfg["short"])
        configure_duration_combo(duration, short, city_key, cfg["label"])

    for cfg in CITY_CONFIG.values():
        remove_panel_and_compact(panels, cfg["monthly_hours"])

    DASHBOARD.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Combined monthly alerts/day with alert-hours/day and retained monthly count+duration panels"
    )


if __name__ == "__main__":
    main()
