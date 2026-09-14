#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboard.json"


def main() -> None:
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = obj.get("panels", [])

    by_id = {p.get("id"): p for p in panels}
    if 12 not in by_id or 13 not in by_id:
        raise RuntimeError("Expected monthly source panels 12 and 13")

    # Avoid duplicates if this script is ever run twice on the same rendered file.
    panels = [p for p in panels if p.get("id") not in {14, 15}]

    # Make room beneath the monthly long-horizon panels.
    for panel in panels:
        gp = panel.get("gridPos", {})
        if gp.get("y", 0) >= 40:
            gp["y"] = gp.get("y", 0) + 18

    weekly_daily_hours = copy.deepcopy(by_id[12])
    weekly_daily_hours["id"] = 14
    weekly_daily_hours["title"] = "Середній час під тривогою на добу — за повними тижнями"
    weekly_daily_hours["description"] = (
        "Повні календарні тижні понеділок–неділя. Тривоги через північ "
        "розподілено між календарними добами; перекриття не подвоюються."
    )
    weekly_daily_hours["gridPos"]["y"] = 40
    for target in weekly_daily_hours.get("targets", []):
        target["root_selector"] = "$.weekly"

    weekly_alert_duration = copy.deepcopy(by_id[13])
    weekly_alert_duration["id"] = 15
    weekly_alert_duration["title"] = "Середня тривалість однієї тривоги — за повними тижнями"
    weekly_alert_duration["description"] = (
        "Повні календарні тижні понеділок–неділя; повна тривалість завершеної "
        "тривоги віднесена до тижня її старту."
    )
    weekly_alert_duration["gridPos"]["y"] = 49
    for target in weekly_alert_duration.get("targets", []):
        target["root_selector"] = "$.weekly"

    panels.extend([weekly_daily_hours, weekly_alert_duration])
    panels.sort(key=lambda p: (p.get("gridPos", {}).get("y", 0), p.get("gridPos", {}).get("x", 0)))

    for panel in panels:
        if panel.get("id") == 30:
            panel["title"] = "Джерела та методологія"
            panel.setdefault("options", {})["mode"] = "markdown"
            panel["options"]["content"] = (
                "**Основне джерело:** [Портал відкритих даних Києва]"
                "(https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download)  \n"
                "**Fallback для свіжих завершених подій:** [Kyiv Digital — live-історія]"
                "(https://kyiv.digital/storage/air-alert/stats.html)  \n"
                "Поточний календарний день завжди виключено. Тривоги через північ "
                "розподіляються між календарними добами в часовому поясі Europe/Kyiv; "
                "перекриття інтервалів зливаються, щоб не подвоювати час.  \n"
                "Пропозиції надсилати @olbalakin в телеграм"
            )

    obj["panels"] = panels

    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Added weekly long-horizon panels and methodology footer to", DASHBOARD)


if __name__ == "__main__":
    main()
