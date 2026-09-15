#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"


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


def make_panel(query_template: dict, y: int) -> dict:
    datasource = dict(query_template.get("datasource", {}))
    target = {
        "columns": [
            {
                "selector": "time",
                "text": "Місяць",
                "type": "timestamp",
                "timestampFormat": "2006-01-02T15:04:05Z07:00",
            },
            {"selector": "deaths", "text": "Загиблих", "type": "number"},
        ],
        "computed_columns": [],
        "datasource": datasource,
        "filters": [],
        "format": "table",
        "global_query_id": "",
        "parser": "backend",
        "refId": "A",
        "root_selector": "$.casualties.monthly",
        "source": "url",
        "type": "json",
        "url": query_template["url"],
        "url_options": {"data": "", "method": "GET"},
    }
    return {
        "id": 951,
        "type": "timeseries",
        "title": "Київ: загиблі від повітряних атак РФ за місяцями",
        "description": (
            "Київ (місто). Ракетні, дронові та інші повітряні атаки. "
            "Пізні смерті від отриманих під час атаки поранень віднесені до місяця самої атаки. "
            "Наземні бої та артилерійські обстріли 2022 року не включені."
        ),
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": y},
        "datasource": datasource,
        "targets": [target],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "decimals": 0,
                "custom": {
                    "drawStyle": "bars",
                    "lineInterpolation": "linear",
                    "barAlignment": 0,
                    "lineWidth": 1,
                    "fillOpacity": 65,
                    "gradientMode": "none",
                    "spanNulls": False,
                    "insertNulls": False,
                    "showPoints": "never",
                    "pointSize": 5,
                    "stacking": {"mode": "none", "group": "A"},
                    "axisPlacement": "auto",
                    "axisLabel": "Кількість загиблих",
                    "axisColorMode": "text",
                    "axisBorderShow": False,
                    "scaleDistribution": {"type": "linear"},
                    "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                    "thresholdsStyle": {"mode": "off"},
                },
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
        "options": {
            "tooltip": {"mode": "single", "sort": "none", "hideZeros": False},
            "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []},
        },
    }


def add_disclaimer(methodology: dict) -> None:
    content = methodology.setdefault("options", {}).get("content", "")
    disclaimer = (
        "\n\n**Загиблі від повітряних атак.** Ряд побудований на публічно доступних повідомленнях "
        "офіційних органів і медіа. Незалежних інструментів для повної верифікації кожного випадку "
        "немає, тому ці дані слід трактувати як реконструкцію на основі доступних відкритих джерел. "
        "Для 2025 року використовується подієва реконструкція 166 смертей; КМВА повідомляла річний "
        "накопичувальний підсумок 171, але додаткові п’ять смертей не вдалося надійно прив’язати до "
        "конкретних атак у публічних джерелах."
    )
    if "Незалежних інструментів для повної верифікації" not in content:
        methodology["options"]["content"] = content + disclaimer


def main() -> None:
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    obj["panels"] = [p for p in obj.get("panels", []) if p.get("id") not in {950, 951}]

    methodology = next((p for p in obj["panels"] if p.get("id") == 900), None)
    if methodology is None:
        raise RuntimeError("Methodology panel id=900 not found")

    insert_y = methodology.get("gridPos", {}).get("y", 0)
    row = {
        "id": 950,
        "type": "row",
        "title": "Загиблі від повітряних атак — Київ",
        "collapsed": False,
        "panels": [],
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": insert_y},
    }
    panel = make_panel(find_query_template(obj), insert_y + 1)

    shift = 11
    for existing in obj["panels"]:
        gp = existing.get("gridPos", {})
        if gp.get("y", 0) >= insert_y:
            gp["y"] = gp.get("y", 0) + shift

    add_disclaimer(methodology)
    obj["panels"].extend([row, panel])
    obj["panels"].sort(key=lambda p: (p.get("gridPos", {}).get("y", 0), p.get("gridPos", {}).get("x", 0)))

    # The air-alert dashboard originally started at 2022-02-28. The casualty
    # series begins in February 2022, and its month-start timestamp is midnight
    # Europe/Kyiv (= 2022-01-31 22:00 UTC). Extend the global range just enough
    # to keep that first monthly point visible. Existing alert panels are not
    # backfilled because their underlying data remain unchanged.
    obj.setdefault("time", {})["from"] = "2022-01-31T22:00:00.000Z"
    obj["time"].setdefault("to", "now")

    obj["version"] = 1
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added Kyiv casualty row, monthly panel and public-data verification disclaimer")


if __name__ == "__main__":
    main()
