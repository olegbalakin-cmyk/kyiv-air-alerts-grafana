#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"


def find_query_template(obj: dict) -> dict:
    for panel in obj.get("panels", []):
        for target in panel.get("targets", []):
            if target.get("type") == "json" and target.get("source") == "url" and target.get("url"):
                return target
        for child in panel.get("panels", []):
            for target in child.get("targets", []):
                if target.get("type") == "json" and target.get("source") == "url" and target.get("url"):
                    return target
    raise RuntimeError("Could not find an Infinity JSON query to reuse")


def city_label(data: dict, key: str, series: dict) -> str:
    meta = series.get("meta") or {}
    mm = (data.get("multicity_meta") or {}).get("cities", {}).get(key, {})
    cm = (data.get("cities") or {}).get(key, {}).get("meta", {})
    return str(meta.get("city") or mm.get("label") or cm.get("city_label") or key)


def make_panel(query_template: dict, panel_id: int, city_label: str, root_selector: str, source_url: str, x: int, y: int) -> dict:
    datasource = dict(query_template.get("datasource", {}))
    target = {
        "columns": [
            {"selector": "month", "text": "Місяць", "type": "string"},
            {"selector": "time", "text": "Дата", "type": "timestamp", "timestampFormat": "2006-01-02T15:04:05Z07:00"},
            {"selector": "deaths", "text": "Загиблих", "type": "number"},
        ],
        "computed_columns": [],
        "datasource": datasource,
        "filters": [],
        "format": "table",
        "global_query_id": "",
        "parser": "backend",
        "refId": "A",
        "root_selector": root_selector,
        "source": "url",
        "type": "json",
        "url": source_url,
        "url_options": {"data": "", "method": "GET"},
    }
    return {
        "id": panel_id,
        "type": "barchart",
        "title": f"{city_label}: загиблі від повітряних атак РФ",
        "description": (
            f"{city_label} (місто). Ракетні, дронові та інші повітряні атаки. "
            "Пізні смерті від отриманих під час атаки поранень віднесені до місяця самої атаки. "
            "Наземні бої та артилерійські обстріли не включені. 2026-09 — поточний неповний місяць."
        ),
        "gridPos": {"h": 10, "w": 12, "x": x, "y": y},
        "datasource": datasource,
        "targets": [target],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "decimals": 0,
                "custom": {
                    "axisPlacement": "auto",
                    "axisLabel": "Кількість загиблих",
                    "axisColorMode": "text",
                    "axisBorderShow": False,
                    "axisCenteredZero": False,
                    "scaleDistribution": {"type": "linear"},
                    "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                    "fillOpacity": 65,
                    "gradientMode": "none",
                    "lineWidth": 1,
                    "thresholdsStyle": {"mode": "off"},
                },
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "Дата"},
                    "properties": [{"id": "custom.hideFrom", "value": {"tooltip": True, "viz": True, "legend": True}}],
                }
            ],
        },
        "options": {
            "orientation": "auto",
            "xField": "Місяць",
            "xTickLabelRotation": 0,
            "xTickLabelSpacing": 90,
            "xTickLabelMaxLength": 12,
            "groupWidth": 0.72,
            "barWidth": 0.9,
            "barRadius": 0,
            "fullHighlight": True,
            "showValue": "never",
            "stacking": "none",
            "tooltip": {"mode": "single", "sort": "none", "hideZeros": False},
            "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []},
        },
    }


def ensure_site_link_panel(obj: dict) -> None:
    panel_id = 949
    existing = next((p for p in obj.get("panels", []) if p.get("id") == panel_id), None)
    panel = {
        "id": panel_id,
        "type": "text",
        "title": "Актуальна версія сайту",
        "description": "Посилання на актуальну вебверсію проєкту.",
        "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
        "options": {
            "mode": "markdown",
            "content": (
                "## Актуальна версія сайту\n\n"
                "Повна актуальна версія з інтерактивними графіками та порівнянням міст:  "
                "[ukraine-air-alerts.netlify.app](https://ukraine-air-alerts.netlify.app/)"
            ),
        },
    }
    if existing is None:
        for item in obj.get("panels", []):
            gp = item.get("gridPos", {})
            gp["y"] = int(gp.get("y", 0)) + panel["gridPos"]["h"]
        obj.setdefault("panels", []).append(panel)
    else:
        panel["gridPos"] = existing.get("gridPos", panel["gridPos"])
        obj["panels"] = [panel if p.get("id") == panel_id else p for p in obj.get("panels", [])]


def iter_targets(panels: list[dict]):
    for panel in panels:
        for target in panel.get("targets", []):
            yield target
        yield from iter_targets(panel.get("panels", []))


def configure_compact_feeds(obj: dict) -> tuple[str, str, str]:
    base = (
        "https://raw.githubusercontent.com/olegbalakin-cmyk/"
        "kyiv-air-alerts-grafana/multicity-wip-2026-09-16/"
        "kyiv-air-alerts-grafana/data/grafana"
    )
    city_url = base + "/cities/${city}.json"
    comparison_url = base + "/comparison.json"
    casualties_url = base + "/casualties.json"

    for target in iter_targets(obj.get("panels", [])):
        if target.get("source") != "url" or target.get("type") != "json":
            continue
        selector = str(target.get("root_selector") or "")
        if selector.startswith("$.cities.${city}"):
            target["url"] = city_url
            target["root_selector"] = selector.replace("$.cities.${city}", "$", 1)
        elif selector.startswith("$.comparison"):
            target["url"] = comparison_url
        elif selector.startswith("$['casualties_by_city']"):
            target["url"] = casualties_url

    return city_url, comparison_url, casualties_url


def sync_city_variables(obj: dict, data: dict) -> None:
    keys = list((data.get("multicity_meta") or {}).get("production_city_keys") or [])
    if not keys:
        return

    labels = {
        key: str(
            (data.get("multicity_meta") or {}).get("cities", {}).get(key, {}).get("label")
            or (data.get("cities") or {}).get(key, {}).get("meta", {}).get("city_label")
            or key
        )
        for key in keys
    }
    keys.sort(key=lambda key: (0 if key == "kyiv" else 1, labels[key].casefold()))
    query = ", ".join(f"{labels[key]} : {key}" for key in keys)

    defaults = {
        "city": "kyiv",
        "compare_city_a": "kyiv",
        "compare_city_b": "kharkiv",
        "compare_city_c": "zaporizhzhia",
    }
    for var in (obj.get("templating") or {}).get("list", []):
        name = var.get("name")
        if name not in defaults:
            continue
        current_value = str((var.get("current") or {}).get("value") or defaults[name])
        if current_value not in keys:
            current_value = defaults[name]
        var["query"] = query
        var["options"] = [
            {
                "selected": key == current_value,
                "text": labels[key],
                "value": key,
            }
            for key in keys
        ]
        var["current"] = {
            "selected": True,
            "text": labels[current_value],
            "value": current_value,
        }


def add_disclaimer(methodology: dict, count: int) -> None:
    content = methodology.setdefault("options", {}).get("content", "")
    marker = "**Загиблі від повітряних атак.**"
    disclaimer = (
        f"\n\n{marker} На тестовому dashboard доступні місячні реконструкції для {count} міст. "
        "Пізні смерті від поранень віднесені до місяця атаки; географія — адміністративні межі міста. "
        "Невирішені review-кейси не включаються до confirmed-рядів. "
        "2026-09 є поточним неповним місяцем."
    )
    if marker in content:
        content = content.split(marker, 1)[0].rstrip()
    methodology["options"]["content"] = content + disclaimer


def main() -> None:
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    _, _, casualties_url = configure_compact_feeds(obj)
    sync_city_variables(obj, data)
    series_by_city = data.get("casualties_by_city") or {}
    if not series_by_city:
        raise RuntimeError("casualties_by_city is empty")

    obj["panels"] = [
        p for p in obj.get("panels", [])
        if not (950 <= int(p.get("id") or -1) < 1000)
    ]

    ensure_site_link_panel(obj)

    methodology = next(
        (
            p
            for p in obj["panels"]
            if p.get("title") == "Джерела та методологія"
            or "**Географія та джерела.**" in p.get("options", {}).get("content", "")
        ),
        None,
    )
    if methodology is None:
        raise RuntimeError("Methodology panel not found")

    production = (data.get("multicity_meta") or {}).get("production_city_keys") or []
    keys = [key for key in production if key in series_by_city]
    keys.extend(sorted(key for key in series_by_city if key not in keys))

    query_template = find_query_template(obj)
    nested = []
    for idx, key in enumerate(keys):
        label = city_label(data, key, series_by_city[key])
        x = 0 if idx % 2 == 0 else 12
        y = (idx // 2) * 10
        selector = f"$['casualties_by_city']['{key}']['monthly']"
        nested.append(make_panel(query_template, 951 + idx, label, selector, casualties_url, x, y))

    insert_y = methodology.get("gridPos", {}).get("y", 0)
    for existing in obj["panels"]:
        gp = existing.get("gridPos", {})
        if gp.get("y", 0) >= insert_y:
            gp["y"] = gp.get("y", 0) + 1

    row = {
        "id": 950,
        "type": "row",
        "title": f"Загиблі від повітряних атак — {len(keys)} міст",
        "collapsed": True,
        "panels": nested,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": insert_y},
    }

    add_disclaimer(methodology, len(keys))
    obj["panels"].append(row)
    obj["panels"].sort(key=lambda p: (p.get("gridPos", {}).get("y", 0), p.get("gridPos", {}).get("x", 0)))

    obj.setdefault("time", {})["from"] = "2022-01-31T22:00:00.000Z"
    obj["time"].setdefault("to", "now")
    obj["version"] = 1
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added casualty panels for", len(keys), "cities:", ", ".join(keys))


if __name__ == "__main__":
    main()
