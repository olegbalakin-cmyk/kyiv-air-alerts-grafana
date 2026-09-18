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


def make_panel(query_template: dict, y: int, panel_id: int, city_label: str, root_selector: str) -> dict:
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
        "url": query_template["url"],
        "url_options": {"data": "", "method": "GET"},
    }
    return {
        "id": panel_id,
        "type": "barchart",
        "title": f"{city_label}: загиблі від повітряних атак РФ за місяцями",
        "description": (
            f"{city_label} (місто). Ракетні, дронові та інші повітряні атаки. "
            "Пізні смерті від отриманих під час атаки поранень віднесені до місяця самої атаки. "
            "Наземні бої та артилерійські обстріли 2022 року не включені. "
            "Вісь X є категоріальною (YYYY-MM). Технічне поле дати збережене у frame "
            "для сумісності зі shared/public renderer Grafana."
        ),
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": y},
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
    obj["panels"] = [p for p in obj.get("panels", []) if p.get("id") not in {950, 951, 952}]

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

    insert_y = methodology.get("gridPos", {}).get("y", 0)
    row = {
        "id": 950,
        "type": "row",
        "title": "Загиблі від повітряних атак — Київ та Одеса",
        "collapsed": False,
        "panels": [],
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": insert_y},
    }
    query_template = find_query_template(obj)
    kyiv_panel = make_panel(query_template, insert_y + 1, 951, "Київ", "$.casualties.monthly")
    odesa_panel = make_panel(query_template, insert_y + 11, 952, "Одеса", "$.casualties_by_city.odesa.monthly")

    shift = 21
    for existing in obj["panels"]:
        gp = existing.get("gridPos", {})
        if gp.get("y", 0) >= insert_y:
            gp["y"] = gp.get("y", 0) + shift

    add_disclaimer(methodology)
    obj["panels"].extend([row, kyiv_panel, odesa_panel])
    obj["panels"].sort(key=lambda p: (p.get("gridPos", {}).get("y", 0), p.get("gridPos", {}).get("x", 0)))

    obj.setdefault("time", {})["from"] = "2022-01-31T22:00:00.000Z"
    obj["time"].setdefault("to", "now")

    obj["version"] = 1
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added categorical Kyiv and Odesa casualty panels with shared-dashboard time compatibility")


if __name__ == "__main__":
    main()
