#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import postprocess_dashboard_qa as legacy

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
QA_FILE = ROOT / "data" / "dashboard_qa.json"
UTC = timezone.utc

EXPECTED_EXACT = {"kyiv", "kharkiv", "zaporizhzhia", "sevastopol"}
EXPECTED_PROXY_COUNT = 19
EXPECTED_TOTAL = 23
EXPECTED_DEFERRED = {"donetsk", "luhansk"}
REQUIRED_VARIABLES = {
    "city",
    "compare_city_a",
    "compare_city_b",
    "compare_city_c",
    "duration_unit",
    "comparison_period",
}


def variable_names(obj: dict) -> set[str]:
    return {
        str(v.get("name"))
        for v in obj.get("templating", {}).get("list", [])
        if v.get("name")
    }


def source_groups(data: dict) -> tuple[list[str], list[str], dict[str, str]]:
    meta = data.get("multicity_meta", {})
    keys = list(meta.get("production_city_keys", []))
    cities_meta = meta.get("cities", {})
    labels: dict[str, str] = {}
    exact: list[str] = []
    proxy: list[str] = []
    for key in keys:
        item = cities_meta.get(key, {})
        city_meta = data.get("cities", {}).get(key, {}).get("meta", {})
        label = item.get("label") or city_meta.get("city_label") or key
        labels[key] = label
        source_type = item.get("source_type") or city_meta.get("source_type")
        if source_type == "exact_city":
            exact.append(key)
        elif source_type == "raion_proxy":
            proxy.append(key)
    return exact, proxy, labels


def patch_methodology(obj: dict, fresh: dict) -> None:
    panel = next(
        (
            p for p in obj.get("panels", [])
            if p.get("type") == "text" and "методолог" in str(p.get("title", "")).lower()
        ),
        None,
    )
    if panel is None:
        return
    content = panel.setdefault("options", {}).get("content", "")
    note = (
        "\n\n**Як користуватися dashboard.** У верхньому перемикачі **«Місто»** обирається один ряд, "
        "який показується в усіх основних панелях. Для порівняння використовуються три окремі "
        "перемикачі **A/B/C**, тому одночасно на графіку є не більше трьох міст. "
        "Назва з районом у дужках означає районний proxy, а не exact-city."
    )
    if "**Як користуватися dashboard.**" not in content:
        content += note
    freshness_note = "\n\n**Freshness upstream.** " + legacy.freshness_markdown(fresh)
    if "**Freshness upstream.**" not in content:
        content += freshness_note
    panel["options"]["content"] = content


def validate(data: dict, obj: dict, exact: list[str], proxy: list[str], labels: dict[str, str]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    meta = data.get("multicity_meta", {})
    keys = list(meta.get("production_city_keys", []))

    if len(keys) != EXPECTED_TOTAL:
        errors.append(f"Expected {EXPECTED_TOTAL} production rows, found {len(keys)}")
    if len(set(keys)) != len(keys):
        errors.append("Production city keys contain duplicates")
    if set(exact) != EXPECTED_EXACT:
        errors.append(f"Exact-city set mismatch: {exact}")
    if len(proxy) != EXPECTED_PROXY_COUNT:
        errors.append(f"Expected {EXPECTED_PROXY_COUNT} proxy rows, found {len(proxy)}")

    deferred = set((meta.get("deferred") or {}).keys())
    if deferred != EXPECTED_DEFERRED:
        errors.append(f"Deferred set mismatch: {sorted(deferred)}")

    missing_city_payloads = [key for key in keys if key not in data.get("cities", {})]
    if missing_city_payloads:
        errors.append("Missing city payloads: " + ", ".join(missing_city_payloads))

    for key in proxy:
        label = labels.get(key, key)
        if "(" not in label or "район" not in label.lower():
            errors.append(f"Proxy label is not explicit: {key} -> {label}")
        city_meta = data.get("cities", {}).get(key, {}).get("meta", {})
        if not city_meta.get("coverage_start"):
            errors.append(f"Proxy coverage_start missing: {key}")

    names = variable_names(obj)
    missing_vars = sorted(REQUIRED_VARIABLES - names)
    if missing_vars:
        errors.append("Missing dashboard variables: " + ", ".join(missing_vars))

    city_rows = [
        p for p in obj.get("panels", [])
        if p.get("type") == "row" and str(p.get("title", "")) in set(labels.values())
    ]
    if city_rows:
        errors.append(f"Found {len(city_rows)} per-city accordion rows; compact dashboard should have none")

    by_id = {p.get("id"): p for p in obj.get("panels", [])}
    for panel_id in (41, 42, 43):
        panel = by_id.get(panel_id)
        if panel is None:
            errors.append(f"Comparison panel {panel_id} missing")
            continue
        rendered = json.dumps(panel, ensure_ascii=False)
        for token in ("${compare_city_a}", "${compare_city_b}", "${compare_city_c}"):
            if token not in rendered:
                errors.append(f"Comparison panel {panel_id} missing selector token {token}")

    rendered = json.dumps(obj, ensure_ascii=False)
    if "$.cities.${city}" not in rendered:
        errors.append("City panels are not driven by the ${city} selector")

    bridge = meta.get("official_ukrainealarm_bridge") or {}
    bridge_required = set(bridge.get("required_rows") or [])
    expected_bridge = set(keys) - {"kyiv", "sevastopol"}
    if bridge_required and bridge_required != expected_bridge:
        errors.append(
            "UkraineAlarm bridge required set mismatch: "
            f"expected={sorted(expected_bridge)}, actual={sorted(bridge_required)}"
        )

    return {
        "production_rows": len(keys),
        "exact_city_rows": len(exact),
        "raion_proxy_rows": len(proxy),
        "deferred_rows": sorted(deferred),
        "compact_city_selector": True,
        "comparison_selector_slots": 3,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    exact, proxy, labels = source_groups(data)
    freshness = legacy.source_freshness(data)
    data.setdefault("multicity_meta", {})["upstream_freshness"] = freshness

    legacy.insert_warning_panel(obj, freshness)
    patch_methodology(obj, freshness)

    qa = validate(data, obj, exact, proxy, labels)
    qa.update({
        "generated_at": datetime.now(UTC).isoformat(),
        "exact_city_labels": [labels[k] for k in exact],
        "raion_proxy_labels": [labels[k] for k in proxy],
        "upstream_freshness": freshness,
    })

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QA_FILE.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qa, ensure_ascii=False, indent=2))
    if not qa["ok"]:
        raise RuntimeError("Compact dashboard QA failed: " + "; ".join(qa["errors"]))


if __name__ == "__main__":
    main()
