#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
QA_FILE = ROOT / "data" / "dashboard_qa.json"
WARNING_PANEL_ID = 99001
FRESH_AFTER_HOURS = 36.0
UTC = timezone.utc


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def bridge_status(data: dict) -> dict | None:
    bridge = data.get("multicity_meta", {}).get("official_ukrainealarm_bridge")
    if not isinstance(bridge, dict):
        return None
    last_fetch = parse_iso(bridge.get("last_successful_fetch_at"))
    if last_fetch is None:
        return None
    age_hours = (datetime.now(UTC) - last_fetch).total_seconds() / 3600
    required = list(bridge.get("required_rows") or [])
    covered = list(bridge.get("continuity_verified_rows") or [])
    uncovered = list(bridge.get("continuity_unverified_rows") or [])
    return {
        "source": "official UkraineAlarm API regionHistory bridge",
        "last_successful_fetch_at": last_fetch.isoformat(),
        "fetch_age_hours": round(age_hours, 2),
        "fresh": age_hours <= FRESH_AFTER_HOURS,
        "required_rows": required,
        "covered_rows": covered,
        "uncovered_rows": uncovered,
        "fully_continuous": bool(required) and not uncovered,
    }


def labels_for(data: dict, keys: list[str]) -> list[str]:
    mm = data.get("multicity_meta", {}).get("cities", {})
    cities = data.get("cities", {})
    return [
        mm.get(key, {}).get("label")
        or cities.get(key, {}).get("meta", {}).get("city_label")
        or key
        for key in keys
    ]


def replace_freshness_note(obj: dict, message: str) -> None:
    methodology = next(
        (
            panel for panel in obj.get("panels", [])
            if panel.get("type") == "text" and "методолог" in str(panel.get("title", "")).lower()
        ),
        None,
    )
    if methodology is None:
        return
    options = methodology.setdefault("options", {})
    content = str(options.get("content", ""))
    content = re.sub(r"\n\n\*\*Freshness upstream\.\*\*.*\Z", "", content, flags=re.S)
    content = re.sub(r"\n\n\*\*Freshness джерел\.\*\*.*\Z", "", content, flags=re.S)
    options["content"] = content.rstrip() + "\n\n**Freshness джерел.** " + message


def remove_warning_panel(obj: dict) -> bool:
    panels = obj.get("panels", [])
    index = next((i for i, panel in enumerate(panels) if panel.get("id") == WARNING_PANEL_ID), None)
    if index is None:
        return False
    panels.pop(index)
    # postprocess_dashboard_qa.py reserves exactly two rows for this panel.
    for panel in panels:
        grid = panel.get("gridPos")
        if isinstance(grid, dict) and isinstance(grid.get("y"), int) and grid["y"] >= 2:
            grid["y"] -= 2
    return True


def set_warning_panel(obj: dict, message: str) -> None:
    panel = next((p for p in obj.get("panels", []) if p.get("id") == WARNING_PANEL_ID), None)
    if panel is None:
        return
    panel["title"] = "Стан джерел районних та city-level даних"
    panel.setdefault("options", {})["mode"] = "markdown"
    panel["options"]["content"] = message


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    status = bridge_status(data)
    if status is None:
        print("No successful official UkraineAlarm bridge fetch recorded; leaving upstream warning unchanged")
        return

    if status["fresh"] and status["fully_continuous"]:
        message = (
            "Vadimkin `official_data_uk.csv` зараз stale, але всі ряди, що від нього залежали, "
            "дочитуються з **офіційного UkraineAlarm API**. Безперервність від frozen upstream "
            f"перевірена для всіх {len(status['required_rows'])} рядів; останній успішний API fetch — "
            f"{status['last_successful_fetch_at']} (≈ {status['fetch_age_hours']:.1f} год тому). "
            "Київ і Севастополь мають окремі незалежні джерела."
        )
        remove_warning_panel(obj)
        replace_freshness_note(obj, message)
        effective = {**status, "status": "official_api_bridge_fresh", "warning": False}
        print("Official UkraineAlarm bridge fully covers stale upstream-dependent rows; warning removed")
    else:
        uncovered_labels = labels_for(data, status["uncovered_rows"])
        if not status["fresh"]:
            message = (
                "⚠️ **Офіційний UkraineAlarm API bridge не є свіжим.** "
                f"Останній успішний fetch був ≈ {status['fetch_age_hours']:.1f} год тому. "
                "Vadimkin upstream також stale, тому кінцеві нулі не слід трактувати як гарантовану відсутність тривог."
            )
            effective_status = "official_api_bridge_stale"
        else:
            message = (
                "⚠️ **Офіційний UkraineAlarm API bridge підключений, але historical continuity підтверджена не для всіх рядів.** "
                f"Покрито {len(status['covered_rows'])}/{len(status['required_rows'])}; "
                f"непідтверджені: {', '.join(uncovered_labels) if uncovered_labels else 'невідомо'}. "
                "Для них правий край графіка може залишатися неповним; нулі після frozen upstream не є доказом відсутності тривог."
            )
            effective_status = "official_api_bridge_partial"
        set_warning_panel(obj, message)
        replace_freshness_note(obj, message)
        effective = {**status, "status": effective_status, "warning": True}
        print(message)

    data.setdefault("multicity_meta", {})["effective_freshness"] = effective
    if QA_FILE.exists():
        qa = json.loads(QA_FILE.read_text(encoding="utf-8"))
        qa["effective_freshness"] = effective
        QA_FILE.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
