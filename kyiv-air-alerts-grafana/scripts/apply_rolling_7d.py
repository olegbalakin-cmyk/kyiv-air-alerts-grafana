#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from statistics import mean

from add_duration_unit_switch import CITY_KEYS, CITY_LABELS, build_comparison, fetch_city_alerts, http_session
from update_data import Alert, TZ, daterange, day_counts_and_durations, round3, union_daily_seconds

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
KYIV_ALERTS_FILE = ROOT / "data" / "alerts_combined.json"
WEEKLY_CSV = ROOT / "data" / "weekly.csv"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
SOURCE_COMMIT_API = (
    "https://api.github.com/repos/Vadimkin/ukrainian-air-raid-sirens-dataset/commits"
    "?path=datasets/official_data_uk.csv&per_page=1"
)


def rolling_rows(alerts: list[Alert], first_city_day: date, end_day: date) -> list[dict]:
    """Build one rolling 7-day point for every completed end day.

    The first city-level day is conservatively excluded because city-level coverage
    can begin part-way through that day. Each point is timestamped by the final day
    of its seven-day window.
    """
    first_window_start = first_city_day + timedelta(days=1)
    first_window_end = first_window_start + timedelta(days=6)
    if first_window_end > end_day:
        return []

    counts, durations_by_start = day_counts_and_durations(alerts, end_day)
    daily_seconds = union_daily_seconds(alerts, first_window_start, end_day)

    rows: list[dict] = []
    window_end = first_window_end
    while window_end <= end_day:
        window_start = window_end - timedelta(days=6)
        days = list(daterange(window_start, window_end))
        starts = sum(counts.get(d, 0) for d in days)
        seconds = sum(daily_seconds.get(d, 0.0) for d in days)
        event_durations = [
            duration
            for d in days
            for duration in durations_by_start.get(d, [])
        ]
        rows.append(
            {
                "time": datetime.combine(window_end, time.min, tzinfo=TZ).isoformat(),
                "week_start": window_start.isoformat(),
                "week_end": window_end.isoformat(),
                "alerts_per_day": round3(starts / 7.0),
                "avg_daily_alert_hours": round3(seconds / 7.0 / 3600.0),
                "avg_alert_duration_min": round3(
                    mean(event_durations) if event_durations else None
                ),
                "alerts_started": starts,
            }
        )
        window_end += timedelta(days=1)
    return rows


def upstream_complete_day() -> date | None:
    """Conservative last complete day for the upstream multicity source.

    The source is a periodically committed snapshot. The calendar day before its
    most recent file commit is treated as the latest guaranteed complete day.
    """
    try:
        response = http_session().get(SOURCE_COMMIT_API, timeout=30)
        response.raise_for_status()
        payload = response.json()
        stamp = payload[0]["commit"]["committer"]["date"]
        commit_dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(TZ)
        return commit_dt.date() - timedelta(days=1)
    except Exception as exc:  # keep the production update resilient to GitHub API hiccups
        print(f"Warning: could not determine upstream complete day: {exc}")
        return None


def load_kyiv_alerts() -> list[Alert]:
    raw = json.loads(KYIV_ALERTS_FILE.read_text(encoding="utf-8"))
    return [
        Alert(
            start=datetime.fromisoformat(row["start"]).astimezone(TZ),
            end=datetime.fromisoformat(row["end"]).astimezone(TZ),
            source=row.get("source", "kyiv_combined"),
        )
        for row in raw
    ]


def update_rolling_meta(meta: dict, rows: list[dict], end_day: date) -> None:
    meta["weekly_mode"] = "rolling_7d"
    meta["rolling_7d_analysis_end"] = end_day.isoformat()
    meta["rolling_7d_definition"] = "7 completed calendar days, timestamped by window end"
    if rows:
        meta["first_rolling_7d_start"] = rows[0]["week_start"]
        meta["first_rolling_7d_end"] = rows[0]["week_end"]
        meta["latest_rolling_7d_start"] = rows[-1]["week_start"]
        meta["latest_rolling_7d_end"] = rows[-1]["week_end"]
        # Keep the legacy metadata keys aligned with the data behind $.weekly.
        meta["first_complete_week_start"] = rows[0]["week_start"]
        meta["last_complete_week_start"] = rows[-1]["week_start"]
        meta["last_complete_week_end"] = rows[-1]["week_end"]


def write_weekly_csv(rows: list[dict]) -> None:
    fieldnames = [
        "time",
        "week_start",
        "week_end",
        "alerts_per_day",
        "avg_daily_alert_hours",
        "avg_alert_duration_min",
        "alerts_started",
    ]
    with WEEKLY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def walk_panels(panels: list[dict]):
    for panel in panels:
        yield panel
        children = panel.get("panels", [])
        if children:
            yield from walk_panels(children)


def patch_dashboard(dashboard: dict, data: dict, upstream_end: date | None) -> None:
    comparison_weekly = data.get("comparison", {}).get("weekly", [])
    comparison_start = comparison_weekly[0]["time"][:10] if comparison_weekly else "—"
    comparison_end = comparison_weekly[-1]["time"][:10] if comparison_weekly else "—"

    for panel in walk_panels(dashboard.get("panels", [])):
        title = panel.get("title", "")
        title = title.replace("за повними тижнями", "за ковзними 7 днями")
        title = title.replace("Порівняння міст — тижні", "Порівняння міст — ковзні 7 днів")
        title = title.replace("(тижні)", "(ковзні 7 днів)")
        panel["title"] = title

        if "за ковзними 7 днями" in title:
            if "середня кількість тривог" in title.lower():
                panel["description"] = (
                    "Кожна точка — ковзне 7-денне вікно завершених календарних днів, "
                    "датоване останнім днем вікна. Кількість тривог, що почалися у вікні, "
                    "поділена на 7."
                )
            elif "середній час під тривогою" in title.lower():
                panel["description"] = (
                    "Кожна точка — ковзне 7-денне вікно завершених календарних днів, "
                    "датоване останнім днем вікна. Сумарний час під тривогою у вікні "
                    "поділено на 7; тривоги через північ розподілено між добами, "
                    "перекриття не подвоюються."
                )
            elif "середня тривалість" in title.lower():
                panel["description"] = (
                    "Кожна точка — ковзне 7-денне вікно завершених календарних днів, "
                    "датоване останнім днем вікна. Показано середню повну тривалість "
                    "тривог, старт яких припав на це вікно."
                )

        if title.startswith("Порівняння міст") and "ковзні 7 днів" in title:
            freshness = (
                f" Харків і Запоріжжя обрізані до {upstream_end.isoformat()} — останнього "
                "гарантовано повного дня перед останнім оновленням upstream-файлу."
                if upstream_end
                else ""
            )
            panel["description"] = (
                "Кожна точка — ковзне 7-денне вікно, датоване останнім днем. "
                "Порівнюються тільки city-level дані; обласні тривоги не підмішуються. "
                f"Спільний ряд вибраних тут міст: {comparison_start}–{comparison_end}."
                + freshness
            )

    methodology = next(
        (p for p in dashboard.get("panels", []) if p.get("id") == 900),
        None,
    )
    if methodology:
        content = methodology.setdefault("options", {}).get("content", "")
        content = content.replace(
            "Поточний календарний день завжди виключено. Перший неповний місяць і перший неповний тиждень кожного city-level ряду не включаються до довгих агрегатів. ",
            "Поточний календарний день завжди виключено. Перший неповний місяць кожного city-level ряду не включається до місячних агрегатів. ",
        )
        rolling_note = (
            "\n\n**Ковзні 7 днів.** Кожна точка охоплює 7 завершених календарних днів "
            "і датована останнім днем вікна. Сусідні точки перекриваються на 6 днів, "
            "тому їх слід читати як rolling-ряд, а не як незалежні календарні тижні. "
            "Вікно, що включає неповний стартовий день city-level покриття, відкидається."
        )
        if upstream_end:
            rolling_note += (
                f" Для Харкова і Запоріжжя rolling-ряд наразі обрізано до {upstream_end.isoformat()} "
                "за датою останнього оновлення upstream-джерела."
            )
        if "**Ковзні 7 днів.**" not in content:
            content += rolling_note
        methodology["options"]["content"] = content


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    if not all(key in cities for key in CITY_KEYS):
        raise RuntimeError("Expected Kyiv, Kharkiv and Zaporizhzhia city data before rolling conversion")

    yesterday = datetime.now(TZ).date() - timedelta(days=1)
    upstream_end = upstream_complete_day()

    alerts_by_city = {"kyiv": load_kyiv_alerts()}
    alerts_by_city.update(fetch_city_alerts())

    for key in CITY_KEYS:
        city = cities[key]
        meta = city.setdefault("meta", {})
        first_day = date.fromisoformat(meta["first_city_level_date"])
        existing_end = date.fromisoformat(meta.get("analysis_end", yesterday.isoformat()))
        end_day = min(yesterday, existing_end)
        if key != "kyiv" and upstream_end is not None:
            end_day = min(end_day, upstream_end)

        rows = rolling_rows(alerts_by_city[key], first_day, end_day)
        city["weekly"] = rows
        update_rolling_meta(meta, rows, end_day)

        multi_meta = data.setdefault("multicity_meta", {}).setdefault("cities", {}).setdefault(key, {})
        multi_meta["weekly_mode"] = "rolling_7d"
        multi_meta["first_rolling_7d_start"] = rows[0]["week_start"] if rows else None
        multi_meta["latest_rolling_7d_end"] = rows[-1]["week_end"] if rows else None
        multi_meta["rolling_7d_analysis_end"] = end_day.isoformat()

    data["weekly"] = cities["kyiv"]["weekly"]
    update_rolling_meta(data.setdefault("meta", {}), data["weekly"], date.fromisoformat(cities["kyiv"]["meta"]["rolling_7d_analysis_end"]))
    data.setdefault("comparison", {})["weekly"] = build_comparison(cities, "weekly")
    data.setdefault("multicity_meta", {})["weekly_mode"] = "rolling_7d"
    if upstream_end:
        data["multicity_meta"]["upstream_last_guaranteed_complete_day"] = upstream_end.isoformat()

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_weekly_csv(data["weekly"])

    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    patch_dashboard(dashboard, data, upstream_end)
    DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "Converted weekly series to rolling 7-day windows:",
        f"Kyiv through {cities['kyiv']['meta']['rolling_7d_analysis_end']};",
        f"Kharkiv through {cities['kharkiv']['meta']['rolling_7d_analysis_end']};",
        f"Zaporizhzhia through {cities['zaporizhzhia']['meta']['rolling_7d_analysis_end']}",
    )


if __name__ == "__main__":
    main()
