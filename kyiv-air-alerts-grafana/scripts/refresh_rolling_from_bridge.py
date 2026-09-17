#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import add_duration_unit_switch as exactmod
import apply_rolling_7d as rolling
import apply_ukrainealarm_bridge as bridge
from update_data import TZ

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    if not all(key in cities for key in exactmod.CITY_KEYS):
        raise RuntimeError("Expected three production city rows")

    base_alerts = exactmod.fetch_city_alerts()
    merged_alerts, covered_keys = bridge.bridged_exact_alerts(base_alerts)
    yesterday = datetime.now(TZ).date() - timedelta(days=1)

    for key in ["kharkiv", "zaporizhzhia"]:
        if key not in covered_keys:
            print(f"{key}: continuity not verified; keeping conservative rolling row")
            continue
        city = cities[key]
        meta = city.setdefault("meta", {})
        first_day = date.fromisoformat(meta["first_city_level_date"])
        rows = rolling.rolling_rows(merged_alerts[key], first_day, yesterday)
        city["weekly"] = rows
        rolling.update_rolling_meta(meta, rows, yesterday)
        mm = data.setdefault("multicity_meta", {}).setdefault("cities", {}).setdefault(key, {})
        mm["weekly_mode"] = "rolling_7d"
        mm["latest_rolling_7d_end"] = rows[-1]["week_end"] if rows else None
        mm["rolling_7d_analysis_end"] = yesterday.isoformat()
        mm["rolling_7d_source"] = "official UkraineAlarm API bridge"

    data.setdefault("comparison", {})["weekly"] = exactmod.build_comparison(cities, "weekly")
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    covered = sorted(covered_keys)
    print("Rolling API refresh complete; continuity verified for:", ", ".join(covered) or "none")


if __name__ == "__main__":
    main()
