#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"

CITY_CONFIG = {
    "kyiv": {"combo": 104, "duration": 107, "short": 111, "label": "Київ"},
    "kharkiv": {"combo": 204, "duration": 207, "short": 211, "label": "Харків"},
    "zaporizhzhia": {"combo": 304, "duration": 307, "short": 311, "label": "Запоріжжя"},
}

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


def walk_with_parent(panels: list[dict]):
    for panel in panels:
        yield panels, panel
        children = panel.get("panels", [])
        if children:
            yield from walk_with_parent(children)


def find_panel(panels: list[dict], panel_id: int) -> dict:
    for _, panel in walk_with_parent(panels):
        if panel.get("id") == panel_id:
            return panel
    raise RuntimeError(f"Panel {panel_id} not found")


def configure_combo(panel: dict, short_panel: dict, city_key: str, city_label: str) -> None:
    panel["title"] = (
        f"{city_label}: кількість тривог і середня тривалість однієї тривоги — за місяцями"
    )
    panel["description"] = (
        "Повні календарні місяці; поточний неповний місяць виключено. "
        "Стовпчики — кількість завершених тривог за місяцем старту; "
        "лінія — середня повна тривалість тривог, що стартували цього місяця."
    )

    if not panel.get("targets"):
        raise RuntimeError(f"Monthly panel {panel.get('id')} has no target")
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

    # Reuse the proven dual-axis styling from the short-horizon panel:
    # count as bars on the left, average duration as a line on the right.
    panel["fieldConfig"] = copy.deepcopy(short_panel["fieldConfig"])
    panel["options"] = copy.deepcopy(short_panel["options"])
    panel.pop("timeFrom", None)


def remove_panel_and_compact(panels: list[dict], panel_id: int) -> int:
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
        return removed_h
    raise RuntimeError(f"Panel {panel_id} not found for removal")


def main() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = dashboard.get("panels", [])

    # Configure all three city monthly panels before removing anything.
    for city_key, cfg in CITY_CONFIG.items():
        combo = find_panel(panels, cfg["combo"])
        short = find_panel(panels, cfg["short"])
        configure_combo(combo, short, city_key, cfg["label"])

    # Remove the now-redundant monthly-duration panels. For nested collapsed city
    # rows this compacts the child layout; for Kyiv this also frees vertical space.
    kyiv_duration = find_panel(panels, CITY_CONFIG["kyiv"]["duration"])
    kyiv_removed_y = kyiv_duration.get("gridPos", {}).get("y", 0)
    kyiv_removed_h = kyiv_duration.get("gridPos", {}).get("h", 0)

    remove_panel_and_compact(panels, CITY_CONFIG["kharkiv"]["duration"])
    remove_panel_and_compact(panels, CITY_CONFIG["zaporizhzhia"]["duration"])

    # Kyiv panels are top-level; removing one must also shift every later top-level
    # section (collapsed cities, comparisons, methodology) upward.
    panels[:] = [p for p in panels if p.get("id") != CITY_CONFIG["kyiv"]["duration"]]
    for panel in panels:
        gp = panel.get("gridPos", {})
        if gp.get("y", 0) > kyiv_removed_y:
            gp["y"] = max(0, gp.get("y", 0) - kyiv_removed_h)

    dashboard["panels"] = panels
    DASHBOARD.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Combined monthly alert count and average duration panels; removed redundant duration panels")


if __name__ == "__main__":
    main()
