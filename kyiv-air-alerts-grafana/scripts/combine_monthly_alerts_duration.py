#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"

CITY_CONFIG = {
    "kyiv": {"monthly_rate": 104, "duration": 107, "short": 111, "label": "Київ"},
    "kharkiv": {"monthly_rate": 204, "duration": 207, "short": 211, "label": "Харків"},
    "zaporizhzhia": {"monthly_rate": 304, "duration": 307, "short": 311, "label": "Запоріжжя"},
}

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


def walk_panels(panels: list[dict]):
    for panel in panels:
        yield panel
        children = panel.get("panels", [])
        if children:
            yield from walk_panels(children)


def find_panel(panels: list[dict], panel_id: int) -> dict:
    for panel in walk_panels(panels):
        if panel.get("id") == panel_id:
            return panel
    raise RuntimeError(f"Panel {panel_id} not found")


def assert_monthly_rate_panel(panel: dict, city_key: str, city_label: str) -> None:
    """Fail loudly if the normalized monthly alerts/day panel disappears or is retargeted."""
    panel["title"] = f"{city_label}: середня кількість тривог на день — за місяцями"
    if not panel.get("targets"):
        raise RuntimeError(f"Monthly alerts/day panel missing target for {city_label}")
    target = panel["targets"][0]
    columns = target.get("columns", [])
    if not any(col.get("selector") == "alerts_per_day" for col in columns):
        raise RuntimeError(f"Monthly alerts/day panel no longer reads alerts_per_day for {city_label}")
    expected_root = f"$.cities.{city_key}.monthly"
    if target.get("root_selector") != expected_root:
        raise RuntimeError(
            f"Monthly alerts/day panel root changed for {city_label}: {target.get('root_selector')!r}"
        )


def configure_duration_combo(panel: dict, short_panel: dict, city_key: str, city_label: str) -> None:
    panel["title"] = (
        f"{city_label}: кількість тривог і середня тривалість однієї тривоги — за місяцями"
    )
    panel["description"] = (
        "Повні календарні місяці; поточний неповний місяць виключено. "
        "Стовпчики — абсолютна кількість завершених тривог за місяцем старту; "
        "лінія — середня повна тривалість тривог, що стартували цього місяця. "
        "Окремий графік вище показує нормалізовану кількість тривог на день."
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

    # Reuse the short-horizon dual-axis defaults, but force the monthly
    # presentation explicitly so Grafana cannot render both series as lines.
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


def main() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = dashboard.get("panels", [])

    for city_key, cfg in CITY_CONFIG.items():
        monthly_rate = find_panel(panels, cfg["monthly_rate"])
        assert_monthly_rate_panel(monthly_rate, city_key, cfg["label"])

        duration = find_panel(panels, cfg["duration"])
        short = find_panel(panels, cfg["short"])
        configure_duration_combo(duration, short, city_key, cfg["label"])

    DASHBOARD.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Preserved monthly alerts/day panels and added monthly alert-count bars to duration panels")


if __name__ == "__main__":
    main()
