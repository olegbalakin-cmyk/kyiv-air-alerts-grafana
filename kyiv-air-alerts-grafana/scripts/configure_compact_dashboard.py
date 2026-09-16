#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import expand_multicity_production as production

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"

TIME_COL = {
    "selector": "time",
    "text": "Дата",
    "type": "timestamp",
    "timestampFormat": "2006-01-02T15:04:05Z07:00",
}


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


def explicit_proxy_labels(data: dict) -> dict[str, str]:
    meta = data.setdefault("multicity_meta", {})
    keys = list(meta.get("production_city_keys", []))
    cities_meta = meta.setdefault("cities", {})
    labels: dict[str, str] = {}

    for key in keys:
        city = data.get("cities", {}).get(key, {})
        city_meta = city.setdefault("meta", {})
        item = cities_meta.setdefault(key, {})
        source_type = item.get("source_type") or city_meta.get("source_type")
        label = item.get("label") or city_meta.get("city_label") or key
        raion = item.get("proxy_raion") or city_meta.get("proxy_raion")
        if source_type == "raion_proxy" and raion and "(" not in label:
            label = f"{label} ({raion})"
        item["label"] = label
        city_meta["city_label"] = label
        labels[key] = label
    return labels


def configure_variables(obj: dict, keys: list[str], labels: dict[str, str]) -> None:
    variables = obj.setdefault("templating", {}).setdefault("list", [])
    by_name = {v.get("name"): v for v in variables if v.get("name")}

    city_options = [(labels[key], key) for key in keys]
    city_var = custom_variable("city", "Місто", city_options, "kyiv")

    defaults = [key for key in ("kyiv", "kharkiv", "zaporizhzhia") if key in keys]
    while len(defaults) < 3:
        defaults.append(keys[len(defaults)])

    compare_vars = [
        custom_variable("compare_city_a", "Порівняння A", city_options, defaults[0]),
        custom_variable("compare_city_b", "Порівняння B", city_options, defaults[1]),
        custom_variable("compare_city_c", "Порівняння C", city_options, defaults[2]),
    ]

    duration = by_name.get("duration_unit")
    if duration is None:
        duration = custom_variable(
            "duration_unit", "Одиниці часу", [("Хвилини", "minutes"), ("Години", "hours")], "hours"
        )
    comparison_period = by_name.get("comparison_period")
    if comparison_period is None:
        comparison_period = custom_variable(
            "comparison_period", "Період порівняння", [("Місяці", "monthly"), ("Тижні", "weekly")], "monthly"
        )
    else:
        comparison_period["label"] = "Період порівняння"

    preserved = [
        v for v in variables
        if v.get("name") not in {
            "city", "compare_city_a", "compare_city_b", "compare_city_c",
            "duration_unit", "comparison_period",
        }
    ]
    variables[:] = [city_var, *compare_vars, duration, comparison_period, *preserved]


def set_query(panel: dict, root: str, columns: list[dict]) -> None:
    for target in panel.get("targets", []):
        target["root_selector"] = root
        target["columns"] = columns


def comparison_columns() -> list[dict]:
    # Grafana externally shared dashboards do not interpolate ${var:text}
    # inside Infinity column display names. Keep the legend stable and put
    # the resolved city names in the panel title instead.
    return [
        TIME_COL,
        {"selector": "city_a", "text": "A", "type": "number"},
        {"selector": "city_b", "text": "B", "type": "number"},
        {"selector": "city_c", "text": "C", "type": "number"},
    ]


def comparison_title(metric: str) -> str:
    return (
        f"{metric} (${{comparison_period:text}}) — "
        "A: ${compare_city_a:text} · B: ${compare_city_b:text} · C: ${compare_city_c:text}"
    )


def style_comparison_slots(panel: dict) -> None:
    # Stable slot colors make shared-view comparisons easier to follow even
    # though the public dashboard cannot expose the selector controls.
    overrides = panel.setdefault("fieldConfig", {}).setdefault("overrides", [])
    overrides[:] = [
        o for o in overrides
        if o.get("matcher", {}).get("options") not in {"A", "B", "C"}
    ]
    slot_colors = {"A": "blue", "B": "green", "C": "yellow"}
    for name, color in slot_colors.items():
        overrides.append({
            "matcher": {"id": "byName", "options": name},
            "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": color}},
                {"id": "custom.lineWidth", "value": 2},
            ],
        })


def configure_comparison_panels(obj: dict) -> None:
    by_id = {p.get("id"): p for p in obj.get("panels", [])}
    row = by_id.get(40)
    if row:
        row["title"] = "Порівняння обраних міст"
        row["collapsed"] = False

    common_description = (
        "Легенда використовує стабільні позначення A/B/C; відповідні назви міст показані в заголовку графіка. "
        "Назва з районом у дужках означає районний proxy, а не exact-city. "
        "У звичайній Grafana міста можна змінювати перемикачами; externally shared view показує збережені значення."
    )

    alerts = by_id.get(41)
    if alerts:
        alerts["title"] = comparison_title("Порівняння — середня кількість тривог на день")
        alerts["description"] = common_description
        root = (
            '$.comparison.${comparison_period}.{' 
            '"time": time, '
            '"city_a": $lookup($, "${compare_city_a}_alerts_per_day"), '
            '"city_b": $lookup($, "${compare_city_b}_alerts_per_day"), '
            '"city_c": $lookup($, "${compare_city_c}_alerts_per_day")}'
        )
        set_query(alerts, root, comparison_columns())
        style_comparison_slots(alerts)

    daily = by_id.get(42)
    if daily:
        daily["title"] = comparison_title("Порівняння — середній час під тривогою на добу")
        daily["description"] = common_description
        root = (
            '$.comparison.${comparison_period}.{' 
            '"time": time, '
            '"city_a": "${duration_unit}" = "minutes" ? $lookup($, "${compare_city_a}_avg_daily_alert_hours") * 60 : $lookup($, "${compare_city_a}_avg_daily_alert_hours"), '
            '"city_b": "${duration_unit}" = "minutes" ? $lookup($, "${compare_city_b}_avg_daily_alert_hours") * 60 : $lookup($, "${compare_city_b}_avg_daily_alert_hours"), '
            '"city_c": "${duration_unit}" = "minutes" ? $lookup($, "${compare_city_c}_avg_daily_alert_hours") * 60 : $lookup($, "${compare_city_c}_avg_daily_alert_hours")}'
        )
        set_query(daily, root, comparison_columns())
        style_comparison_slots(daily)

    duration = by_id.get(43)
    if duration:
        duration["title"] = comparison_title("Порівняння — середня тривалість однієї тривоги")
        duration["description"] = common_description
        root = (
            '$.comparison.${comparison_period}.{' 
            '"time": time, '
            '"city_a": "${duration_unit}" = "hours" ? $lookup($, "${compare_city_a}_avg_alert_duration_min") / 60 : $lookup($, "${compare_city_a}_avg_alert_duration_min"), '
            '"city_b": "${duration_unit}" = "hours" ? $lookup($, "${compare_city_b}_avg_alert_duration_min") / 60 : $lookup($, "${compare_city_b}_avg_alert_duration_min"), '
            '"city_c": "${duration_unit}" = "hours" ? $lookup($, "${compare_city_c}_avg_alert_duration_min") / 60 : $lookup($, "${compare_city_c}_avg_alert_duration_min")}'
        )
        set_query(duration, root, comparison_columns())
        style_comparison_slots(duration)


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    keys = list(data.get("multicity_meta", {}).get("production_city_keys", []))
    expected = [*production.CITY_KEYS, "sevastopol"]
    missing = [key for key in expected if key not in keys]
    unexpected = [key for key in keys if key not in expected]
    if missing or unexpected:
        raise RuntimeError(f"Unexpected production set before compact UI; missing={missing}, unexpected={unexpected}")

    labels = explicit_proxy_labels(data)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    configure_variables(obj, keys, labels)
    configure_comparison_panels(obj)
    obj["title"] = "Повітряні тривоги — міста України"
    obj["version"] = 1
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Configured compact dashboard for", len(keys), "rows")
    print("City selector:", ", ".join(labels[key] for key in keys))
    print("Comparison defaults: Київ, Харків, Запоріжжя")


if __name__ == "__main__":
    main()
