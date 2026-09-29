#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
APP = ROOT / "pages-preview" / "app.js"
INDEX = ROOT / "pages-preview" / "index.html"

EXPECTED = {
    "kyiv": 454,
    "kharkiv": 339,
    "sevastopol": 22,
    "cherkasy": 2,
    "zhytomyr": 12,
    "dnipro": 214,
    "khmelnytskyi": 10,
    "poltava": 84,
    "rivne": 1,
    "sumy": 158,
    "vinnytsia": 31,
    "kropyvnytskyi": 9,
    "lviv": 29,
    "chernihiv": 105,
    "mykolaiv": 106,
    "lutsk": 10,
    "uzhhorod": 0,
    "ivano-frankivsk": 3,
    "ternopil": 41,
    "chernivtsi": 5,
    "odesa": 171,
    "zaporizhzhia": 316,
    "kherson": 163,
}


def strip_casualties(value: dict) -> dict:
    clone = json.loads(json.dumps(value))
    clone.pop("casualties", None)
    clone.pop("casualties_by_city", None)
    return clone


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    series = data.get("casualties_by_city") or {}
    assert set(series) == set(EXPECTED), (sorted(series), sorted(EXPECTED))

    totals = {}
    for key, expected in EXPECTED.items():
        rows = series[key].get("monthly") or []
        assert rows, key
        months = [row.get("month") for row in rows]
        assert len(months) == len(set(months)), (key, "duplicate months")
        assert all(int(row.get("deaths") or 0) >= 0 for row in rows), (key, "negative deaths")
        totals[key] = sum(int(row.get("deaths") or 0) for row in rows)
        assert totals[key] == expected, (key, totals[key], expected)

    assert series["kyiv"] == data.get("casualties"), "Kyiv compatibility series diverged"
    assert totals["uzhhorod"] == 0 and len(series["uzhhorod"]["monthly"]) > 0

    before_path = os.environ.get("CASUALTY_PROOF_BEFORE")
    if before_path:
        before = json.loads(Path(before_path).read_text(encoding="utf-8"))
        assert strip_casualties(before) == strip_casualties(data), "non-casualty dashboard content changed"

    app = APP.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    assert 'state.data.casualties_by_city?.[key] || (key === "kyiv" ? state.data.casualties : null)' in app
    assert 'if (!rows.length)' in app
    assert 'if (key !== "kyiv"' not in app
    assert 'id="casualtyCityEyebrow"' in index
    assert 'id="casualtySourceNote"' in index

    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    rows = [panel for panel in dashboard.get("panels", []) if panel.get("id") == 950 and panel.get("type") == "row"]
    assert len(rows) == 1, len(rows)
    panels = rows[0].get("panels") or []
    assert len(panels) == 23, len(panels)
    selectors = {
        panel["targets"][0]["root_selector"]
        for panel in panels
    }
    expected_selectors = {
        f"$['casualties_by_city']['{key}']['monthly']"
        for key in EXPECTED
    }
    assert selectors == expected_selectors, (selectors, expected_selectors)

    print(json.dumps({
        "ok": True,
        "city_count": len(series),
        "totals": totals,
        "kyiv_compatibility": True,
        "zero_death_series_valid": True,
        "frontend_selected_city_lookup": True,
        "grafana_city_panels": len(panels),
        "non_casualty_semantic_invariance": bool(before_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Proof-only test; no production side effects.
