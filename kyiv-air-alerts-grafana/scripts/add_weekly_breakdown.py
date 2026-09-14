#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from statistics import mean

from update_data import Alert, TZ, daterange, round3, union_daily_seconds

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def main() -> None:
    dashboard_path = DATA_DIR / "dashboard_data.json"
    alerts_path = DATA_DIR / "alerts_combined.json"

    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    raw_alerts = json.loads(alerts_path.read_text(encoding="utf-8"))

    alerts = [
        Alert(
            start=datetime.fromisoformat(row["start"]).astimezone(TZ),
            end=datetime.fromisoformat(row["end"]).astimezone(TZ),
            source=row.get("source", "audit"),
        )
        for row in raw_alerts
    ]

    for row in dashboard.get("weekly", []):
        ws = date.fromisoformat(row["week_start"])
        we = date.fromisoformat(row["week_end"])

        daily_seconds = union_daily_seconds(alerts, ws, we)
        row["avg_daily_alert_hours"] = round3(
            sum(daily_seconds.get(d, 0.0) for d in daterange(ws, we)) / 7.0 / 3600.0
        )

        event_durations = [
            alert.duration_seconds / 60.0
            for alert in alerts
            if ws <= alert.start.astimezone(TZ).date() <= we
        ]
        row["avg_alert_duration_min"] = round3(
            mean(event_durations) if event_durations else None
        )

    dashboard_path.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    weekly_path = DATA_DIR / "weekly.csv"
    fieldnames = [
        "time",
        "week_start",
        "week_end",
        "alerts_per_day",
        "avg_daily_alert_hours",
        "avg_alert_duration_min",
        "alerts_started",
    ]
    with weekly_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dashboard.get("weekly", []))

    print(f"Added weekly breakdown metrics to {dashboard_path}")


if __name__ == "__main__":
    main()
