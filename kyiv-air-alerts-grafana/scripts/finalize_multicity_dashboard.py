#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"

CITY_PANELS = [1, 2, 3, 10, 11, 12, 13, 14, 15, 20, 21]


def load_city_config() -> list[tuple[str, str, int]]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = data.get("multicity_meta", {})
    keys = meta.get("production_city_keys") or ["kyiv", "kharkiv", "zaporizhzhia"]
    cities = meta.get("cities", {})
    out = []
    for idx, key in enumerate(keys, start=1):
        label = cities.get(key, {}).get("label") or data.get("cities", {}).get(key, {}).get("meta", {}).get("city_label") or key
        out.append((key, label, idx * 100))
    return out


def replace_hours(expr: str) -> str:
    replacements = {
        '"${duration_unit}" = "minutes" ? alert_hours_28d * 60 : alert_hours_28d': 'alert_hours_28d',
        '"${duration_unit}" = "hours" ? avg_alert_duration_min_28d / 60 : avg_alert_duration_min_28d': 'avg_alert_duration_min_28d / 60',
        '"${duration_unit}" = "minutes" ? avg_daily_alert_hours * 60 : avg_daily_alert_hours': 'avg_daily_alert_hours',
        '"${duration_unit}" = "hours" ? avg_alert_duration_min / 60 : avg_alert_duration_min': 'avg_alert_duration_min / 60',
        '"${duration_unit}" = "minutes" ? total_alert_duration_minutes : total_alert_duration_hours': 'total_alert_duration_hours',
        '"${duration_unit}" = "hours" ? avg_alert_duration_minutes / 60 : avg_alert_duration_minutes': 'avg_alert_duration_minutes / 60',
    }
    for old, new in replacements.items():
        expr = expr.replace(old, new)
    expr = re.sub(
        r'"\$\{duration_unit\}" = "minutes" \? ([A-Za-z0-9_]+) \* 60 : \1',
        r'\1',
        expr,
    )
    expr = re.sub(
        r'"\$\{duration_unit\}" = "hours" \? ([A-Za-z0-9_]+) / 60 : \1',
        r'\1 / 60',
        expr,
    )
    return expr


def fix_title(title: str, city_label: str | None = None) -> str:
    if city_label is not None:
        title = title.replace("${city:text}", city_label)
    title = title.replace("${duration_unit:text}", "години")
    return title


def set_hour_labels(panel: dict) -> None:
    panel_id = panel.get("id")
    duration_only = panel_id in {2, 3, 12, 13, 14, 15, 20}
    if duration_only:
        panel.setdefault("fieldConfig", {}).setdefault("defaults", {})["unit"] = "suffix: год"
        for override in panel.get("fieldConfig", {}).get("overrides", []):
            for prop in override.get("properties", []):
                if prop.get("id") == "unit":
                    prop["value"] = "suffix: год"
                elif prop.get("id") == "custom.axisLabel":
                    prop["value"] = "Години"
    elif panel_id == 21:
        for override in panel.get("fieldConfig", {}).get("overrides", []):
            matcher = override.get("matcher", {})
            if matcher.get("options") == "Середня тривалість":
                for prop in override.get("properties", []):
                    if prop.get("id") == "unit":
                        prop["value"] = "suffix: год"
                    elif prop.get("id") == "custom.axisLabel":
                        prop["value"] = "Години"


def make_city_panel(source: dict, city_key: str, city_label: str, new_id: int, y_offset: int) -> dict:
    panel = copy.deepcopy(source)
    original_id = panel["id"]
    panel["id"] = new_id
    panel["title"] = fix_title(panel.get("title", ""), city_label)
    panel["gridPos"]["y"] = panel["gridPos"].get("y", 0) + y_offset
    for target in panel.get("targets", []):
        root = target.get("root_selector")
        if isinstance(root, str):
            root = root.replace("${city}", city_key)
            target["root_selector"] = replace_hours(root)
    panel["id"] = original_id
    set_hour_labels(panel)
    panel["id"] = new_id
    return panel


def make_comparison_panel(source: dict, period: str, period_label: str, new_id: int) -> dict:
    panel = copy.deepcopy(source)
    original_id = panel["id"]
    panel["id"] = new_id
    title = panel.get("title", "")
    title = title.replace("${comparison_period:text}", period_label)
    title = title.replace("${duration_unit:text}", "години")
    panel["title"] = title
    for target in panel.get("targets", []):
        root = target.get("root_selector")
        if not isinstance(root, str):
            continue
        root = root.replace("${comparison_period}", period)
        root = replace_hours(root)
        target["root_selector"] = root
    if original_id in {42, 43}:
        panel.setdefault("fieldConfig", {}).setdefault("defaults", {})["unit"] = "suffix: год"
        panel["fieldConfig"]["defaults"].setdefault("custom", {})["axisLabel"] = "Години"
    return panel


def collapsed_row(row_id: int, title: str, y: int, panels: list[dict]) -> dict:
    return {
        "id": row_id,
        "type": "row",
        "title": title,
        "collapsed": True,
        "panels": panels,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
    }


def main() -> None:
    city_config = load_city_config()
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    by_id = {p.get("id"): p for p in obj.get("panels", [])}
    missing = [pid for pid in CITY_PANELS + [30, 41, 42, 43] if pid not in by_id]
    if missing:
        raise RuntimeError(f"Expected source panels missing: {missing}")

    obj["templating"] = {"list": []}
    panels: list[dict] = []

    first_key, first_label, first_base = city_config[0]
    panels.append({
        "id": first_base,
        "type": "row",
        "title": first_label,
        "collapsed": False,
        "panels": [],
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
    })
    for idx, pid in enumerate(CITY_PANELS, start=1):
        panels.append(make_city_panel(by_id[pid], first_key, first_label, first_base + idx, 1))

    first_end = max(p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0) for p in panels)
    compact_y = first_end

    for city_key, city_label, row_base in city_config[1:]:
        nested = []
        for idx, pid in enumerate(CITY_PANELS, start=1):
            child = make_city_panel(by_id[pid], city_key, city_label, row_base + idx, 0)
            child["gridPos"]["y"] = by_id[pid]["gridPos"].get("y", 0)
            nested.append(child)
        panels.append(collapsed_row(row_base, city_label, compact_y, nested))
        compact_y += 1

    description = by_id[41].get("description", "")
    compare_base = (len(city_config) + 1) * 100
    for offset, (period, period_label) in enumerate([("monthly", "місяці"), ("weekly", "тижні")]):
        row_id = compare_base + offset * 100
        nested = []
        for idx, pid in enumerate([41, 42, 43], start=1):
            child = make_comparison_panel(by_id[pid], period, period_label, row_id + idx)
            child["gridPos"]["y"] = (idx - 1) * 9
            if description:
                child["description"] = description
            nested.append(child)
        panels.append(collapsed_row(row_id, f"Порівняння міст — {period_label}", compact_y, nested))
        compact_y += 1

    methodology = copy.deepcopy(by_id[30])
    methodology["id"] = compare_base + 200
    methodology["gridPos"]["y"] = compact_y
    panels.append(methodology)

    obj["panels"] = panels
    obj["title"] = "Повітряні тривоги — міста України"
    obj["version"] = 1

    rendered = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    bad = [token for token in ("${city}", "${city:text}", "${duration_unit}", "${duration_unit:text}", "${comparison_period}", "${comparison_period:text}") if token in rendered]
    if bad:
        raise RuntimeError(f"Final dashboard still contains unsupported template variables: {bad}")

    DASHBOARD.write_text(rendered, encoding="utf-8")
    print("Finalized dashboard for", len(city_config), "production cities:", ", ".join(label for _, label, _ in city_config))


if __name__ == "__main__":
    main()
