#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"

CITY_CONFIG = {
    "kyiv": {"duration": 107, "short": 111, "label": "Київ"},
    "kharkiv": {"duration": 207, "short": 211, "label": "Харків"},
    "zaporizhzhia": {"duration": 307, "short": 311, "label": "Запоріжжя"},
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


def configure_duration_combo(panel: dict, short_panel: dict, city_key: str, city_label: str) -> None:
    panel["title"] = (
        f"{city_label}: кількість тривог і середня тривалість однієї тривоги — за місяцями"
    )
    panel["description"] = (
        "Повні календарні місяці; поточний неповний місяць виключено. "
        "Стовпчики — абсолютна кількість завершених тривог за місяцем старту; "
        "лінія — середня повна тривалість тривог, що стартували цього місяця. "
        "Окремий графік вище зберігає нормалізований показник тривог на день."
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

    # Reuse the proven short-horizon styling: count as bars on the left axis,
    # average duration as a line on the right axis.
    panel["fieldConfig"] = copy.deepcopy(short_panel["fieldConfig"])
    panel["options"] = copy.deepcopy(short_panel["options"])
    panel.pop("timeFrom", None)


def main() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = dashboard.get("panels", [])

    # Keep the existing monthly alerts/day panels untouched. Enrich only the
    # monthly average-duration panels with absolute monthly alert counts.
    for city_key, cfg in CITY_CONFIG.items():
        duration = find_panel(panels, cfg["duration"])
        short = find_panel(panels, cfg["short"])
        configure_duration_combo(duration, short, city_key, cfg["label"])

    DASHBOARD.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Added monthly alert-count bars to monthly average-duration panels")


if __name__ == "__main__":
    main()
